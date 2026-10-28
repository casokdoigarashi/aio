# note下書きの自動作成

`content/note/*.md` の原稿を、note の下書きとして自動保存する仕組み。

note に公開投稿APIは無いため、Playwright でブラウザを動かして画面操作している。
原稿は見出し・太字・リンク・箇条書きを保ったHTMLに変換してから貼り付ける
（そのまま打ち込むと全部ただの段落になる）。note に表機能は無いので、
Markdownの表は「項目：内容」の箇条書きに変換される。

## 画像

原稿の中に次の行を置くと、その位置に画像が入る。

```
![キャプション](images/01_メインフロア_自然光.jpg)
```

- パスは**原稿ファイルからの相対パス**。画像はリポジトリにコミットしておく
  （CIで動かすため、手元にあるだけでは届かない）
- 公式サイトの写真は
  `https://www.a-ms2.com/arigatoliving/cms/wp-content/uploads/2023/05/19_st_kagra_slidesNN_L.jpg`
  （NN = 01〜14）から取得できる
- 画像は paste イベントで File として渡す。通らなければ drop、
  それでも駄目なら file input の順に試し、どの方法で入ったかをログに出す
- **キャプションはnote側で手入力が必要**。原稿に書いたキャプションは
  挿入されないので、必要なら下書き画面で入れる
- **見出し画像（サムネイル）も手設定**。自動では設定していない

2026-10-28 に実際に下書き作成まで成功している
（`https://editor.note.com/notes/nbfcb2f597562/edit/`、本文1,691文字、
見出し・太字・箇条書き・リンクすべて保持）。

## ログインは Cookie 方式で渡す

**ID・パスワードでの自動ログインは通らない。**
note のログインフォームには reCAPTCHA Enterprise（invisible）が入っており、
GitHub Actions のIPから自動でログインすると必ずそこで止まる
（2026-10-28に実測。`g-recaptcha-response` が空のまま `/login` に留まる）。

そのため、**人間が自分のブラウザでログインした状態（Cookie）だけを渡す**。

### 手順

1. Chrome で https://note.com/ を開き、普通にログインしておく
2. 拡張機能 **Cookie-Editor** を入れる（Chromeウェブストア）
3. note.com のタブを開いた状態で Cookie-Editor のアイコンをクリック
4. 右下の **Export** → **Export as JSON**（クリップボードにコピーされる）
5. https://github.com/casokdoigarashi/aio/settings/secrets/actions で
   **New repository secret** → Name に `NOTE_COOKIES_JSON`、Secret にそのJSONを貼る

`NOTE_EMAIL` / `NOTE_PASSWORD` は使わないので消してよい。

### 注意

- このCookieは**パスワードと同じ重さ**を持つ。Secrets以外の場所に置かない
- note からログアウトすると無効になる（別端末でのログアウトは影響しない）
- 期限が切れたら同じ手順で取り直す。切れると
  「Cookie が無い/期限切れ」とログに出て止まる
- 一度通ると `data/.note_state.json` にCookieを保存して使い回す（`.gitignore` 済み）

## 実行方法

### Actionsの画面から

Actions → 「note下書き作成」→ Run workflow → 原稿ファイルのパスを入力

### トリガーファイルをpushして

`.github/run-note-draft` の原稿パスの行を書き換えてpushする。

**実行のたびに新しい下書きが増える。** そのため普段は `dry_run` の行を残した
状態にしておき、本当に下書きを作るときだけその行を消してpushする。

### 手元で

```
node scripts/note_draft.js content/note/2026-10-28_取材対談スタジオ.md
NOTE_DRY_RUN=1 node scripts/note_draft.js <原稿>   # 変換確認のみ
```

## 壊れたとき

note の画面構成が変わるとセレクタが合わなくなる。
失敗時は URL・入力欄の属性・本文冒頭をログにダンプし、
スクリーンショットを Actions の Artifact（`note-draft-screenshot`）に残すので、
それを見てセレクタを直す。
