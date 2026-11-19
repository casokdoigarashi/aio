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

## 手順

画面の文言はGoogleの更新で変わることがある。おおむね同じ位置にあるものを探す。

### 0. 前提

- `igarashi@a-ms2.com` でGoogleにログインした状態で始める
- **クレジットカードの登録は不要。** Sheets APIは無料枠で足りるので、
  「無料トライアルを開始」や「請求先アカウントを有効化」は押さなくてよい

### 1. プロジェクトを作る

1. https://console.cloud.google.com/ を開く
2. 初回は利用規約の画面が出る。国を選び、規約にチェック →「同意して続行」
3. 画面上部の青いバーにある**プロジェクト選択**（「プロジェクトを選択」と出ている箇所）をクリック
4. ダイアログ右上の**「新しいプロジェクト」**
5. プロジェクト名に `aio-observation` と入力。場所は「組織なし」のまま
6. **「作成」**
7. 数秒待つ。上部のプロジェクト選択が `aio-observation` になっているか確認する
   （別のままなら、もう一度クリックして選び直す）

### 2. Google Sheets API を有効にする

1. この直リンクが速い → https://console.cloud.google.com/apis/library/sheets.googleapis.com
   （メニューから行くなら 左上「≡」→「APIとサービス」→「ライブラリ」→ `Google Sheets API` を検索）
2. 上部のプロジェクト名が `aio-observation` になっているか確認
3. 青い**「有効にする」**ボタンを押す
4. 「APIが有効です」の表示になればOK

### 3. サービスアカウントを作る

1. https://console.cloud.google.com/apis/credentials
   （メニューなら「APIとサービス」→「認証情報」）
2. 上部の**「＋ 認証情報を作成」**→**「サービス アカウント」**
3. サービスアカウント名に `aio-writer` と入力（IDは自動で埋まる）→**「作成して続行」**
4. 「このサービス アカウントにプロジェクトへのアクセスを許可する」
   → **何も選ばずに「続行」**（ロールは不要）
5. 「ユーザーにこのサービス アカウントへのアクセスを許可」
   → **空のまま「完了」**

### 4. 鍵（JSON）をダウンロードする

1. 一覧に出てきた `aio-writer@aio-observation-xxxxx.iam.gserviceaccount.com` をクリック
2. 上部タブの**「キー」**
3. **「鍵を追加」→「新しい鍵を作成」**
4. 形式は **JSON** を選んで**「作成」**
5. `aio-observation-xxxxx.json` がダウンロードされる →「閉じる」

**この鍵は再発行できない。** なくしたら作り直しになる。
そして**パスワードと同じ重さがある。チャットに貼らないこと。**

### 5. スプレッドシートに編集権限を渡す

**ここを飛ばすと必ず権限エラーになる。一番よくあるつまずき。**

まず、鍵の中のメールアドレスをクリップボードにコピーする（ターミナル）:

```bash
cat ~/Downloads/aio-observation-*.json \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['client_email'])" \
  | pbcopy
```

（ターミナルを使わないなら、JSONをテキストエディットで開いて
`"client_email": "..."` の値を手でコピーしてもよい）

1. スプレッドシートを開く
   https://docs.google.com/spreadsheets/d/1A76_uywRdOCL9TQ-yX66LbwKK61p3QXzSK_vA9ZJ4LU/edit
2. 右上の**「共有」**
3. 「ユーザーやグループを追加」に **⌘V** で貼り付け
4. 権限を**「編集者」**に変更（既定は閲覧者のことがある）
5. **「通知」のチェックを外す**（プログラム用のアドレスなのでメールは届かない）
6. **「共有」**／「送信」

### 6. GitHub Secrets に登録する

鍵の中身を全部コピーする（ターミナル）:

```bash
cat ~/Downloads/aio-observation-*.json | pbcopy
```

1. https://github.com/casokdoigarashi/aio/settings/secrets/actions
2. **「New repository secret」**
3. Name: `GOOGLE_SERVICE_ACCOUNT_JSON`
4. Secret: **⌘V**（`{` で始まり `}` で終わる。改行はそのままでよい）
5. **「Add secret」**

### 7. 後片付け

ダウンロードした `aio-observation-xxxxx.json` は、消すか安全な場所へ移す。
Downloadsに置きっぱなしにしない。

```bash
rm ~/Downloads/aio-observation-*.json
```

（GitHubに登録済みなら手元の鍵は不要。再度必要になったら手順4でもう一度作れる）

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
