#!/usr/bin/env node
/**
 * content/note/*.md の原稿を note の下書きとして保存する。
 *
 * 使い方:
 *   node scripts/note_draft.js content/note/2026-10-28_取材対談スタジオ.md
 *
 * ログインは NOTE_COOKIES_JSON（ログイン済みブラウザのCookie）で渡す。
 * note のログインフォームには reCAPTCHA があり、ID・パスワードでの
 * 自動ログインは通らない。詳細は content/note/AUTOMATION.md を参照。
 *
 * 原稿中の `![キャプション](images/xxx.jpg)` の行は画像として挿入する。
 * パスは原稿ファイルからの相対パス。
 *
 * note に公開投稿APIは無いため画面操作で行う。note 側のUI変更で壊れる前提の仕組み。
 */
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const STATE_PATH = path.join(ROOT, "data", ".note_state.json");
const SHOT_DIR = process.env.NOTE_SHOT_DIR || path.join(ROOT, "data", "note_drafts");

// --- 原稿の読み込み ------------------------------------------------------

function parseMarkdown(raw) {
  // 社内メモ用のHTMLコメントは貼らない
  const text = raw.replace(/<!--[\s\S]*?-->/g, "").trim();
  const lines = text.split("\n");

  let title = "";
  const bodyLines = [];
  for (const line of lines) {
    if (!title && /^#\s+/.test(line)) {
      title = line.replace(/^#\s+/, "").trim();
      continue;
    }
    bodyLines.push(line);
  }
  if (!title) throw new Error("原稿の先頭に `# タイトル` がありません");
  return { title, body: bodyLines.join("\n").trim() };
}

function inline(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

/** 本文を「HTMLの塊」と「画像」の並びに分解する。
 *  画像行（![説明](パス)）でテキストを区切り、順番どおりに挿入していく。 */
function splitSegments(body, baseDir) {
  const segments = [];
  let buffer = [];
  const flush = () => {
    const text = buffer.join("\n").trim();
    if (text) segments.push({ type: "html", value: toHtml(text) });
    buffer = [];
  };
  for (const line of body.split("\n")) {
    const m = line.trim().match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (m) {
      flush();
      const file = path.resolve(baseDir, m[2]);
      if (!fs.existsSync(file)) throw new Error(`画像が見つかりません: ${file}`);
      segments.push({ type: "image", caption: m[1], file });
    } else {
      buffer.push(line);
    }
  }
  flush();
  return segments;
}

/** HTMLの最後のブロックの文字列。画像を「どの段落の後ろに置くか」の目印にする。 */
function lastBlockText(html) {
  const blocks = html.match(/<(p|h2|h3|li)\b[^>]*>([\s\S]*?)<\/\1>/g) || [];
  const last = blocks[blocks.length - 1] || "";
  return last.replace(/<[^>]+>/g, "").trim();
}

/** 本文のHTML全体と、画像の差し込み位置（直前の段落の文字列）を組み立てる。
 *
 *  画像を入れるとカーソルが画像のキャプション欄に移り、その後に貼った
 *  テキストがキャプションに流し込まれて書式が全部失われる。
 *  そこで「本文を一括で貼ってから、画像を後入れする」順序にしている。 */
function buildPlan(segments) {
  const htmlParts = [];
  const images = [];
  for (const seg of segments) {
    if (seg.type === "html") {
      htmlParts.push(seg.value);
    } else {
      images.push({
        ...seg,
        // 直前の段落の末尾に置く。先頭の画像（直前が無い）は null
        anchor: htmlParts.length ? lastBlockText(htmlParts[htmlParts.length - 1]) : null,
      });
    }
  }
  return { html: htmlParts.join("\n"), images };
}

/** note のエディタが受け取れる範囲のHTMLに変換する。
 *  note に表組みは無いので、表は「項目：内容」の箇条書きに落とす。 */
function toHtml(body) {
  const out = [];
  let list = null; // 'ul' を開いている間だけ中身が入る
  const closeList = () => {
    if (list) {
      out.push(`<ul>${list.join("")}</ul>`);
      list = null;
    }
  };

  const lines = body.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (!line) {
      closeList();
      continue;
    }

    const h = line.match(/^(#{2,3})\s+(.*)$/);
    if (h) {
      closeList();
      out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);
      continue;
    }

    if (/^\|/.test(line)) {
      // 区切り行（|---|---|）と見出し行は落とす
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      if (cells.every((c) => /^:?-+:?$/.test(c))) continue;
      const isHeader = lines[i + 1] && /^\|\s*:?-/.test(lines[i + 1].trim());
      if (isHeader) continue;
      if (!list) list = [];
      list.push(`<li>${inline(cells.join("："))}</li>`);
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      if (!list) list = [];
      list.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }

    closeList();
    out.push(`<p>${inline(line)}</p>`);
  }
  closeList();
  return out.join("\n");
}

// --- ログイン -----------------------------------------------------------

/** ブラウザ拡張（Cookie-Editor など）が吐くCookie配列を
 *  Playwright の storageState 形式に直す。 */
function cookiesToState(list) {
  const sameSite = (v) =>
    ({ no_restriction: "None", lax: "Lax", strict: "Strict", unspecified: "Lax" }[
      String(v || "").toLowerCase()
    ] || (["None", "Lax", "Strict"].includes(v) ? v : "Lax"));
  return {
    cookies: list.map((c) => ({
      name: c.name,
      value: c.value,
      domain: c.domain || ".note.com",
      path: c.path || "/",
      expires: Number(c.expires ?? c.expirationDate ?? -1),
      httpOnly: Boolean(c.httpOnly),
      secure: c.secure !== false,
      sameSite: sameSite(c.sameSite),
    })),
    origins: [],
  };
}

function storageStateOption() {
  const file = process.env.NOTE_STORAGE_STATE_FILE;
  if (file && fs.existsSync(file)) return file;
  const inlineJson = process.env.NOTE_STORAGE_STATE;
  if (inlineJson) return JSON.parse(inlineJson);
  const cookieJson = process.env.NOTE_COOKIES_JSON;
  if (cookieJson) {
    const parsed = JSON.parse(cookieJson);
    return cookiesToState(Array.isArray(parsed) ? parsed : parsed.cookies || []);
  }
  if (fs.existsSync(STATE_PATH)) return STATE_PATH;
  return undefined;
}

async function isLoggedIn(page) {
  await page.goto("https://note.com/notes/new", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  return !/\/login/.test(page.url());
}

async function loginWithPassword(page) {
  const email = process.env.NOTE_EMAIL;
  const password = process.env.NOTE_PASSWORD;
  if (!email || !password) {
    throw new Error(
      "ログイン情報がありません。NOTE_STORAGE_STATE（Cookie）か、NOTE_EMAIL と NOTE_PASSWORD を設定してください。"
    );
  }
  await page.goto("https://note.com/login?redirectPath=/notes/new", {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(2000);

  // 入力欄の name/id は自動生成で毎回変わるため、並び順で取る
  const inputs = page.locator("form input");
  await inputs.nth(0).fill(email);
  await inputs.nth(1).fill(password);

  await page.getByRole("button", { name: /ログイン/ }).first().click();
  await page.waitForTimeout(8000);

  if (!/\/login/.test(page.url())) return;

  // note のログインフォームには reCAPTCHA Enterprise（invisible）が入っている。
  // データセンターのIPから自動でパスワードログインすると、ここで止まる。
  const hasRecaptcha = await page
    .locator('textarea[name="g-recaptcha-response"], iframe[src*="recaptcha"]')
    .count();
  if (hasRecaptcha) {
    throw new Error(
      "noteのログインが reCAPTCHA で止まりました。ID・パスワードでの自動ログインは通りません。" +
        "ログイン済みブラウザのCookieを NOTE_COOKIES_JSON に設定してください（README参照）。"
    );
  }
  const shown = (await page.innerText("body")).replace(/\s+/g, " ").slice(0, 300);
  throw new Error("ログインが完了しませんでした。画面の表示: " + shown);
}

// --- 下書き作成 ---------------------------------------------------------

/** HTMLを paste イベントとしてエディタに渡す。
 *  ヘッドレスChromiumでは navigator.clipboard.write が拒否されるため、
 *  クリップボードを経由せず paste イベントを直接投げる。
 *  エディタ側はコピペと同じ扱いでHTMLを解釈するので、見出し・太字・
 *  リンク・箇条書きが保たれる（プレーンテキストで打つと全部段落になる）。 */
/** カーソルを本文の末尾に置く。
 *  画像を挿入するとカーソルがエディタ内から外れ、その直後の貼り付けが
 *  プレーンテキスト扱いになって見出し・太字が全部失われる。
 *  貼り付けの前に毎回これを呼ぶこと。 */
async function focusEnd(page, bodyField) {
  await bodyField.click();
  await page.keyboard.press("ControlOrMeta+End");
  await page.waitForTimeout(300);
}

async function pasteHtml(bodyField, html) {
  await bodyField.evaluate((el, payload) => {
    const dt = new DataTransfer();
    dt.setData("text/html", payload);
    dt.setData("text/plain", payload.replace(/<[^>]+>/g, ""));
    el.dispatchEvent(
      new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true })
    );
  }, html);
}

/** 画像ファイルを File としてエディタに渡す。
 *  note はアップロードに時間がかかるので、img が増えるまで待つ。 */
async function insertImage(page, bodyField, file, anchor) {
  const countImages = async () => bodyField.locator("img").count().catch(() => 0);
  const before = await countImages();
  const base64 = fs.readFileSync(file).toString("base64");
  const name = path.basename(file);

  const waitForUpload = async (ms) => {
    const deadline = Date.now() + ms;
    while (Date.now() < deadline) {
      if ((await countImages()) > before) return true;
      await page.waitForTimeout(1000);
    }
    return false;
  };

  // 差し込み位置（目印の段落の末尾）にカーソルを置く
  if (anchor) {
    const placed = await bodyField.evaluate((el, text) => {
      const norm = (s) => (s || "").replace(/\s+/g, "");
      const needle = norm(text);
      const blocks = Array.from(el.querySelectorAll("p, h1, h2, h3, li, blockquote"));
      const target = blocks.reverse().find((b) => norm(b.innerText).includes(needle));
      if (!target) return false;
      el.focus();
      const range = document.createRange();
      range.selectNodeContents(target);
      range.collapse(false);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      return true;
    }, anchor);
    if (!placed) {
      console.log(`    位置の目印が見つかりません: ${anchor.slice(0, 20)}…`);
      return null;
    }
    await page.waitForTimeout(500);
  }

  // paste → drop の順に試す。どちらも「人がコピペ/ドラッグした」のと同じ経路。
  for (const kind of ["paste", "drop"]) {
    await bodyField.evaluate(
      (el, { b64, fileName, eventKind }) => {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const dt = new DataTransfer();
        dt.items.add(new File([bytes], fileName, { type: "image/jpeg" }));
        const event =
          eventKind === "paste"
            ? new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true })
            : new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true });
        el.dispatchEvent(event);
      },
      { b64: base64, fileName: name, eventKind: kind }
    );
    if (await waitForUpload(30000)) return kind === "paste" ? "pasteイベント" : "dropイベント";
  }
  return null;
}

async function writeDraft(page, title, plan) {
  // NOTE_DRAFT_URL があれば既存の下書きを上書きする（実行のたびに増やさないため）
  const existing = process.env.NOTE_DRAFT_URL;
  if (existing) {
    console.log(`既存の下書きを上書きします: ${existing}`);
    await page.goto(existing, { waitUntil: "domcontentloaded", timeout: 60000 });
  } else if (!/\/notes\/new/.test(page.url()) && !/\/notes\/.+\/edit/.test(page.url())) {
    await page.goto("https://note.com/notes/new", { waitUntil: "domcontentloaded", timeout: 60000 });
  }
  await page.waitForTimeout(5000);

  const titleField = page.locator('textarea[placeholder*="タイトル"], input[placeholder*="タイトル"]').first();
  await titleField.waitFor({ timeout: 30000 });
  await titleField.fill(title);

  const bodyField = page.locator('div[contenteditable="true"]').first();
  await bodyField.waitFor({ timeout: 30000 });
  await bodyField.click();

  if (existing) {
    // 既存の本文を消してから入れ直す
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.press("Delete");
    await page.waitForTimeout(1500);
  }

  const bodyLength = async () =>
    (await bodyField.innerText().catch(() => "")).replace(/\s+/g, "").length;

  // まず本文を一括で貼る。空のエディタへの一回の貼り付けなら書式が保たれる。
  await pasteHtml(bodyField, plan.html);
  await page.waitForTimeout(3000);
  console.log(`本文を貼り付けました（${await bodyLength()}文字）`);

  // そのうえで画像を、指定した段落の後ろに差し込む
  let inserted = 0;
  const failedImages = [];
  for (const [i, img] of plan.images.entries()) {
    const how = await insertImage(page, bodyField, img.file, img.anchor);
    const label = `[${i + 1}/${plan.images.length}] ${path.basename(img.file)}`;
    if (how) {
      inserted++;
      console.log(`  ${label} を挿入（${how}）`);
    } else {
      failedImages.push(path.basename(img.file));
      console.log(`  ${label} は挿入できませんでした`);
    }
  }

  const imageCount = plan.images.length;
  // 見出しが0なら書式が飛んでいる（プレーンテキストとして入った）
  const headings = await bodyField.locator("h1, h2, h3").count().catch(() => 0);
  console.log(
    `本文 ${await bodyLength()}文字 / 画像 ${inserted}/${imageCount}枚 / 見出し ${headings}個`
  );
  if (headings === 0) {
    console.log("::warning::見出しが検出されません。書式が失われている可能性があります");
  }
  if (failedImages.length) {
    console.log("挿入できなかった画像: " + failedImages.join(", "));
  }

  // アップロード中（blob: のまま）の画像が残っていると保存に失敗する
  for (let i = 0; i < 30; i++) {
    const pending = await bodyField.locator('img[src^="blob:"]').count().catch(() => 0);
    if (!pending) break;
    if (i === 0) console.log("画像のアップロード完了を待っています…");
    await page.waitForTimeout(2000);
  }

  const url = page.url();
  await saveDraft(page);
  await verifySaved(page);
  return url;
}

/** 下書き保存。失敗トーストが出たら間を置いて押し直す。 */
async function saveDraft(page) {
  const saveBtn = page.getByRole("button", { name: /下書き保存/ }).first();
  if (!(await saveBtn.count())) {
    console.log("下書き保存ボタンが見つかりません（自動保存に任せます）");
    await page.waitForTimeout(8000);
    return;
  }
  for (let attempt = 1; attempt <= 3; attempt++) {
    await saveBtn.click().catch(() => {});
    await page.waitForTimeout(6000);
    const failed = await page.getByText(/保存に失敗/).count().catch(() => 0);
    if (!failed) return;
    console.log(`下書き保存に失敗しました（${attempt}回目）。やり直します`);
    await page.waitForTimeout(6000);
  }
  console.log("::warning::下書き保存を3回試しましたが失敗しました");
}

/** 保存されたものを読み直して確かめる。画面上の見た目ではなく保存結果を見る。 */
async function verifySaved(page) {
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(8000);
  const body = page.locator('div[contenteditable="true"]').first();
  const length = (await body.innerText().catch(() => "")).replace(/\s+/g, "").length;
  const images = await body.locator("img").count().catch(() => 0);
  const headings = await body.locator("h1, h2, h3").count().catch(() => 0);
  console.log(`保存の確認（再読み込み後）: 本文${length}文字 / 画像${images}枚 / 見出し${headings}個`);
  if (length < 100) throw new Error("保存された本文が空か極端に短いです");
  return { length, images, headings };
}

/** セレクタが合わなかったときに、画面の構造を調べるための情報を出す。 */
async function dumpState(page) {
  try {
    console.log("--- 画面の状態 ---");
    console.log("URL: " + page.url());
    console.log("title: " + (await page.title()));
    const info = await page.evaluate(() => {
      const list = (sel) =>
        Array.from(document.querySelectorAll(sel)).slice(0, 25).map((el) => ({
          tag: el.tagName.toLowerCase(),
          placeholder: el.getAttribute("placeholder") || "",
          ariaLabel: el.getAttribute("aria-label") || "",
          name: el.getAttribute("name") || "",
          cls: (el.getAttribute("class") || "").slice(0, 60),
          role: el.getAttribute("role") || "",
        }));
      return {
        textareas: list("textarea"),
        inputs: list("input"),
        editables: list('[contenteditable="true"]'),
        iframes: Array.from(document.querySelectorAll("iframe")).map((f) => f.src),
        bodyText: (document.body.innerText || "").replace(/\s+/g, " ").slice(0, 500),
      };
    });
    console.log(JSON.stringify(info, null, 2));
  } catch (e) {
    console.log("画面の状態を取得できませんでした: " + e.message);
  }
}

// --- 実行 ---------------------------------------------------------------

async function main() {
  const target = process.argv[2];
  if (!target) {
    console.error("使い方: node scripts/note_draft.js <原稿のmdファイル>");
    process.exit(2);
  }
  const mdPath = path.isAbsolute(target) ? target : path.join(ROOT, target);
  const { title, body } = parseMarkdown(fs.readFileSync(mdPath, "utf-8"));
  const segments = splitSegments(body, path.dirname(mdPath));
  const plan = buildPlan(segments);
  console.log(`原稿: ${path.relative(ROOT, mdPath)}`);
  console.log(`タイトル: ${title}`);
  console.log(`構成: 本文${plan.html.length}文字（HTML）/ 画像${plan.images.length}枚`);

  if (process.env.NOTE_DRY_RUN) {
    console.log("--- DRY RUN: 本文 ---");
    console.log(plan.html);
    console.log("--- DRY RUN: 画像の差し込み位置 ---");
    for (const img of plan.images) {
      console.log(`${path.basename(img.file)} ← 「${(img.anchor || "本文の先頭").slice(0, 40)}」の直後`);
    }
    return;
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 1000 },
    storageState: storageStateOption(),
    // 渡されたCookieが普段のブラウザと別物と見なされないように寄せる
    locale: "ja-JP",
    timezoneId: "Asia/Tokyo",
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
  });
  const page = await context.newPage();
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  const shot = path.join(SHOT_DIR, path.basename(mdPath, ".md") + ".png");

  try {
    if (!(await isLoggedIn(page))) {
      console.log("Cookie が無い/期限切れのため、ID・パスワードでログインします");
      await loginWithPassword(page);
    } else {
      console.log("保存済みの Cookie でログイン済みです");
    }

    const url = await writeDraft(page, title, plan);
    console.log(`下書きを保存しました: ${url}`);

    fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
    await context.storageState({ path: STATE_PATH });
    console.log(`Cookie を保存しました: ${path.relative(ROOT, STATE_PATH)}（次回はログイン不要）`);
  } catch (e) {
    await dumpState(page);
    throw e;
  } finally {
    // 成否にかかわらず画面を残す（セレクタ調整の手がかりになる）
    await page.screenshot({ path: shot, fullPage: true }).catch(() => {});
    console.log(`確認用スクショ: ${path.relative(ROOT, shot)}`);
    await browser.close();
  }
}

main().catch((e) => {
  console.error("失敗しました: " + e.message);
  process.exit(1);
});
