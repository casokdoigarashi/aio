#!/usr/bin/env node
/**
 * content/note/*.md の原稿を note の下書きとして保存する。
 *
 * 使い方:
 *   node scripts/note_draft.js content/note/2026-10-28_取材対談スタジオ.md
 *
 * ログインの渡し方（どちらか一方）:
 *   A) Cookie（推奨）  NOTE_STORAGE_STATE に Playwright の storageState JSON を入れる
 *                      （または NOTE_STORAGE_STATE_FILE にファイルパス）
 *   B) ID / パスワード NOTE_EMAIL と NOTE_PASSWORD
 *
 * B で一度ログインすると storage-state を data/.note_state.json に書き出すので、
 * 次回以降は A として使い回せる（二段階認証の確認を毎回出さないため）。
 * このファイルは .gitignore 済み。コミットしないこと。
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
  await page.waitForTimeout(6000);

  if (/\/login/.test(page.url())) {
    const shown = (await page.innerText("body")).replace(/\s+/g, " ").slice(0, 400);
    throw new Error(
      "ログインが完了しませんでした。二段階認証・新端末確認・入力誤りのいずれかです。画面の表示: " + shown
    );
  }
}

// --- 下書き作成 ---------------------------------------------------------

async function writeDraft(page, context, title, html) {
  if (!/\/notes\/new/.test(page.url()) && !/\/notes\/.+\/edit/.test(page.url())) {
    await page.goto("https://note.com/notes/new", { waitUntil: "domcontentloaded", timeout: 60000 });
  }
  await page.waitForTimeout(4000);

  const titleField = page.locator('textarea[placeholder*="タイトル"], input[placeholder*="タイトル"]').first();
  await titleField.waitFor({ timeout: 30000 });
  await titleField.fill(title);

  const bodyField = page.locator('div[contenteditable="true"]').first();
  await bodyField.waitFor({ timeout: 30000 });
  await bodyField.click();

  // 見出し・太字・リンクを残すため、HTMLとしてクリップボード経由で貼り付ける。
  // プレーンテキストで打ち込むと全部ただの段落になる。
  await context.grantPermissions(["clipboard-read", "clipboard-write"], {
    origin: "https://note.com",
  });
  await page.evaluate(async (payload) => {
    const plain = payload.replace(/<[^>]+>/g, "");
    await navigator.clipboard.write([
      new ClipboardItem({
        "text/html": new Blob([payload], { type: "text/html" }),
        "text/plain": new Blob([plain], { type: "text/plain" }),
      }),
    ]);
  }, html);
  await page.keyboard.press("ControlOrMeta+V");
  await page.waitForTimeout(3000);

  // note は自動保存されるが、保存ボタンがあれば明示的に押す
  const saveBtn = page.getByRole("button", { name: /下書き保存|保存/ }).first();
  if (await saveBtn.count()) {
    await saveBtn.click().catch(() => {});
  }
  await page.waitForTimeout(6000);
  return page.url();
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
  const html = toHtml(body);
  console.log(`原稿: ${path.relative(ROOT, mdPath)}`);
  console.log(`タイトル: ${title}`);
  console.log(`本文: ${html.length} 文字（HTML換算）`);

  if (process.env.NOTE_DRY_RUN) {
    console.log("--- DRY RUN: 変換結果 ---");
    console.log(html);
    return;
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 1000 },
    storageState: storageStateOption(),
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

    const url = await writeDraft(page, context, title, html);
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
