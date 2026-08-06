# 週次運用手順（RUNBOOK）

毎週決まった曜日・時間帯（推奨: 火曜午前）に以下を実施します。
検索結果は時間帯やログイン状態でも変わるため、**同じ条件で取ること**が定点観測の生命線です。

## 0. 事前準備（初回のみ）

```bash
pip install -r scripts/requirements.txt
```

- GitHubリポジトリの Settings > Secrets and variables > Actions に、
  `config/config.yml` の `engines.auto` で有効にしたエンジンのキーを登録する:
  - `SERPAPI_KEY` … Google AIモード（google_ai_mode）※本命
  - `GEMINI_API_KEY` … Gemini（Google検索グラウンディング）
  - `PERPLEXITY_API_KEY` … Perplexity（任意）
- キーが無いエンジンは自動でスキップされる（1つだけでも動作する）。

## 1. 自動観測（GitHub Actionsが毎週火曜9時に自動実行）

- `.github/workflows/weekly-aio-check.yml` が自動で実行され、
  `data/observations/<日付>-auto.yml` と `reports/` が更新・コミットされます。
- 手動でも実行可能: Actionsタブ → Weekly AIO Check → Run workflow
- ローカルで実行する場合:

```bash
export GEMINI_API_KEY=...   # 使うキーだけ
python scripts/auto_check.py
```

## 2. Google AIモードもAPIで取得（スクリーンショット不要）

Google AIモードの回答本文と引用元は SerpApi の `google_ai_mode` エンジンで
JSONとして取得できるため、**スクリーンショットもブラウザ操作も不要**。
手順1の自動観測に含まれており、同じワークフローで一緒に実行される。

観測条件はAPIパラメータで固定してあるので、毎週まったく同じ条件で取得される:

| パラメータ | 値 |
|---|---|
| location | Tokyo, Japan |
| hl / gl | ja / jp |
| device | desktop |
| no_cache | true（キャッシュを使わず毎回取得） |

> スクリーンショットでの観測は不要になったが、AIモードの画面そのものを
> 資料として残したい場合のみ手動で撮る。その場合のデータ化手順は
> `docs/PROMPT_screenshot_to_data.md`（現在は任意運用）。

## 3. 施策を実施したら記録

note記事の公開、Yahoo! PRの出稿、サイト更新などを行ったら、その都度
`data/actions.yml` に1件追記します（日付・種別・タイトル・URL・狙いのクエリ）。

これにより「施策 → 何週間後にAI回答が変化したか」をレポート上で突き合わせられます。

## 4. レポート生成とコミット

```bash
python scripts/analyze.py
git add data reports
git commit -m "obs: 週次観測 YYYY-MM-DD"
git push
```

- `reports/summary.md` … 全期間のトレンド表（社内共有用ダッシュボード）
- `reports/weekly/<日付>.md` … その週の詳細

## 観測条件のルール（変えないこと）

| 項目 | 条件 |
|---|---|
| 曜日・時間帯 | 毎週火曜 午前（自動観測は9:00 JST） |
| ブラウザ | シークレットウィンドウ、ログインなし |
| 位置情報 | 東京（VPN等は使わない） |
| クエリ | `config/config.yml` の文言を一字一句そのまま |

クエリを追加したくなったら `config/config.yml` に**追加**する（既存は変更・削除しない。
時系列比較が壊れるため。不要になったクエリはコメントアウトで残す）。
