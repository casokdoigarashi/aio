#!/usr/bin/env node
/**
 * note の下書きを削除する。
 *
 *   node scripts/note_delete.js <下書きURLまたはID> [...]
 *
 * 取り消しのきかない操作なので、引数で明示されたものだけを消す。
 * 「全部消す」のような指定はできない。
 * ログインは note_draft.js と同じ NOTE_COOKIES_JSON を使う。
 */
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const STATE_PATH = path.join(ROOT, "data", ".note_state.json");
const SHOT_DIR = process.env.NOTE_SHOT_DIR || path.join(ROOT, "data", "note_drafts");

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

function editorUrl(arg) {
  const m = String(arg).match(/\b(n[0-9a-f]{12,})\b/);
  if (!m) throw new Error(`下書きIDを読み取れません: ${arg}`);
  return { id: m[1], url: `https://editor.note.com/notes/${m[1]}/edit/` };
}

/** 画面上のボタンを一覧する。削除メニューが見つからないときの手がかり用。 */
async function listButtons(page) {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll("button, [role=button], a[role=menuitem]"))
      .map((el) => ({
        text: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 24),
        label: el.getAttribute("aria-label") || "",
      }))
      .filter((b) => b.text || b.label)
      .slice(0, 40)
  );
}

async function deleteDraft(page, id, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(6000);

  if (/\/login/.test(page.url())) throw new Error("ログインしていません（Cookieを確認してください）");

  const title = (await page.locator('textarea[placeholder*="タイトル"]').first().inputValue().catch(() => "")) || "(タイトルなし)";
  console.log(`  対象: ${id} — ${title.slice(0, 40)}`);

  // 「…」メニューを開く
  const menuCandidates = [
    page.getByRole("button", { name: /その他|メニュー|操作|more/i }),
    page.locator('button[aria-label*="メニュー"]'),
    page.locator('button[aria-label*="その他"]'),
  ];
  let opened = false;
  for (const candidate of menuCandidates) {
    if (await candidate.count().catch(() => 0)) {
      await candidate.first().click().catch(() => {});
      await page.waitForTimeout(1500);
      if (await page.getByText(/削除/).count().catch(() => 0)) {
        opened = true;
        break;
      }
    }
  }
  if (!opened) {
    console.log("  メニューを開けませんでした。画面上のボタン:");
    console.log("  " + JSON.stringify(await listButtons(page)));
    return false;
  }

  // メニュー内の「削除」
  await page.getByText(/^削除$/).first().click().catch(() => {});
  await page.waitForTimeout(2000);

  // 確認ダイアログの「削除」
  const confirm = page.getByRole("button", { name: /削除/ });
  if (await confirm.count().catch(() => 0)) {
    await confirm.last().click().catch(() => {});
  }
  await page.waitForTimeout(6000);

  // 消えたことを確認する（編集画面に残っていたら失敗扱い）
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(5000);
  const stillThere = await page
    .locator('textarea[placeholder*="タイトル"]')
    .count()
    .catch(() => 0);
  return !stillThere;
}

async function main() {
  const args = process.argv.slice(2);
  if (!args.length) {
    console.error("使い方: node scripts/note_delete.js <下書きURLまたはID> [...]");
    process.exit(2);
  }
  const targets = args.map(editorUrl);
  console.log(`削除する下書き: ${targets.map((t) => t.id).join(", ")}`);

  if (process.env.NOTE_DRY_RUN) {
    console.log("DRY RUN のため削除しません");
    return;
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 1000 },
    storageState: storageStateOption(),
    locale: "ja-JP",
    timezoneId: "Asia/Tokyo",
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
  });
  const page = await context.newPage();
  fs.mkdirSync(SHOT_DIR, { recursive: true });

  const failed = [];
  try {
    for (const { id, url } of targets) {
      let ok = false;
      try {
        ok = await deleteDraft(page, id, url);
      } catch (e) {
        console.log(`  ${id}: ${e.message}`);
      }
      console.log(ok ? `  ${id} を削除しました` : `  ${id} は削除できませんでした`);
      if (!ok) {
        failed.push(id);
        await page.screenshot({ path: path.join(SHOT_DIR, `delete_${id}.png`) }).catch(() => {});
      }
    }
  } finally {
    await browser.close();
  }

  if (failed.length) {
    console.log(`::warning::削除できなかった下書き: ${failed.join(", ")}`);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error("失敗しました: " + e.message);
  process.exit(1);
});
