# 週次運用手順（RUNBOOK）

毎週決まった曜日・時間帯（推奨: 火曜午前）に以下を実施します。
検索結果は時間帯やログイン状態でも変わるため、**同じ条件で取ること**が定点観測の生命線です。

## 0. 事前準備（初回のみ）

```bash
pip install -r scripts/requirements.txt
```

- 自動観測を使う場合は、GitHubリポジトリの Settings > Secrets and variables > Actions に
  `PERPLEXITY_API_KEY` / `GEMINI_API_KEY` / `SERPAPI_KEY` のうち使うものを登録する
  （1つだけでも動作します。おすすめは Gemini = Google AIモードに最も近い挙動）。

## 1. 自動観測（GitHub Actionsが毎週火曜9時に自動実行）

- `.github/workflows/weekly-aio-check.yml` が自動で実行され、
  `data/observations/<日付>-auto.yml` と `reports/` が更新・コミットされます。
- 手動でも実行可能: Actionsタブ → Weekly AIO Check → Run workflow
- ローカルで実行する場合:

```bash
export GEMINI_API_KEY=...   # 使うキーだけ
python scripts/auto_check.py
```

## 2. Google AIモードのスクリーンショット取得（Manusが毎週火曜10:00に自動実行）

Google AIモードそのものはAPIが無いため、スクリーンショットで観測する。
この取得作業は Manus のブラウザ自動化タスクで週次自動化済み:

- 毎週火曜 10:00 JST に q1〜q6 を検索し、AIモードの回答を
  [Driveフォルダ「検索結果画面」](https://drive.google.com/drive/folders/1HVmHHnTvWpLEiG3JTV6MOdoPDyBHtZcK)
  へ `YYYY-MM-DD_q1_01.png` 形式で保存（回答が長い場合は複数枚 _01, _02, …）
- ログイン要求・CAPTCHA・AIモード未表示のクエリは「未取得」として報告される

スクショが揃ったら、**データ化**を行う（撮っただけではレポートに反映されない）:

- Claude に「今週のスクショをデータ化して」と依頼する、または
  `docs/PROMPT_screenshot_to_data.md` のプロンプトを他のAIに渡す
- 手で記入する場合は `python scripts/new_observation.py` でテンプレートを生成して記入

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
