# スプレッドシートへの自動書き込み：初回設定

毎週の観測結果を GitHub Actions から Google スプレッドシートに直接書き込むための設定。
**初回だけ**必要な作業で、以後は自動で動く。

対象のスプレッドシート:
https://docs.google.com/spreadsheets/d/1A76_uywRdOCL9TQ-yX66LbwKK61p3QXzSK_vA9ZJ4LU/edit

---

## なぜサービスアカウントが要るのか

GitHub Actions は五十嵐さんのGoogleアカウントでログインできない。
代わりに**プログラム用のアカウント（サービスアカウント）**を1つ作り、
そのアカウントにスプレッドシートの編集権限を渡す。

noteのCookieのように期限切れで止まることがない方式なので、
一度設定すれば放っておける。

---

## 手順（10分程度）

### 1. Google Cloud のプロジェクトを作る

1. https://console.cloud.google.com/ を開く
2. 画面上部のプロジェクト選択 →「新しいプロジェクト」
3. 名前は `aio-observation` など。作成

### 2. Sheets API を有効にする

1. 左メニュー「APIとサービス」→「ライブラリ」
2. `Google Sheets API` を検索 → 開く →「有効にする」

### 3. サービスアカウントを作る

1. 「APIとサービス」→「認証情報」
2. 上部「＋認証情報を作成」→「サービスアカウント」
3. 名前は `aio-writer` など → 「作成して続行」
4. ロールは**付けなくてよい**（スプレッドシート側で権限を渡すため）→「完了」

### 4. 鍵（JSON）を作る

1. 作成したサービスアカウントをクリック
2. 上部タブ「キー」→「鍵を追加」→「新しい鍵を作成」
3. **JSON** を選んで「作成」→ ファイルがダウンロードされる

**このJSONはパスワードと同じ重さがある。** チャットに貼らないこと。

### 5. スプレッドシートに編集権限を渡す

1. ダウンロードしたJSONを開き、`"client_email"` の値をコピー
   （`aio-writer@aio-observation-xxxxx.iam.gserviceaccount.com` のような形）
2. スプレッドシートを開く → 右上「共有」
3. その**メールアドレスを貼って「編集者」**にする →「送信」

### 6. GitHub Secrets に入れる

1. https://github.com/casokdoigarashi/aio/settings/secrets/actions
2. 「New repository secret」
3. Name: `GOOGLE_SERVICE_ACCOUNT_JSON`
4. Secret: **ダウンロードしたJSONファイルの中身を全部**貼り付け
   （`{` で始まって `}` で終わる。改行はそのままでよい）
5. Add secret

これで完了。`SPREADSHEET_ID` はリポジトリの `config.yml` に書いてあるので、
Secretに入れる必要はない。

---

## うまくいかないとき

| 症状 | 原因 |
|---|---|
| `403 The caller does not have permission` | 手順5をやっていない。サービスアカウントのメールを共有に追加する |
| `404 Requested entity was not found` | スプレッドシートIDが違う。`config.yml` の `sheets.spreadsheet_id` を確認 |
| `API has not been used in project` | 手順2をやっていない。Sheets API を有効にする |

---

## セキュリティ上の注意

- サービスアカウントには**ロールを付けていない**ので、
  このGoogle Cloudプロジェクトの他のリソースには触れない
- できるのは**共有されたスプレッドシートの編集だけ**
- 他社に展開するときは、**会社ごとに別のスプレッドシート**を作り、
  同じサービスアカウントを共有に追加する（鍵は使い回してよい）
- 鍵を失効させたいときは、Google Cloud の「キー」タブから削除する
