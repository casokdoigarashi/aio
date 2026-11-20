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
  - `ANTHROPIC_API_KEY` … Claude（web search有効）
  - `OPENAI_API_KEY` … ChatGPT（web search有効）
  - `PERPLEXITY_API_KEY` … Perplexity（任意）
- 使用モデルは `config/config.yml` の `models` で変更できる。
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

## 欠測の記録

レポートを社外公開する際、欠けている箇所は理由を注記する。
後から「なぜここが空なのか」を思い出せなくなるため、起きた時点でここに書く。

| 日付 | 欠けたエンジン | 理由 |
|---|---|---|
| 2026-08-25 〜 09-08 | Claude | Anthropic APIの残高不足。3週間気づかず欠測（この件を受けてエンジン全滅の検知を追加） |
| 2026-10-27 | Gemini | Google AI Studio の前払いクレジット切れ（402 Payment Required）。10-28には復旧 |
| 2026-11-03（予定） | Google AIモード | SerpApi無料枠（月250検索）を使い切り。更新日が11-06のため観測日に間に合わない。11-10から通常に戻る |

### 2026-10-28 に枠を使い切った経緯

`weekly-aio-check.yml` に動作確認用のpushトリガーが残っていたため、
リポジトリへのpushのたびに観測がフル実行され、1日で10回走った。
SerpApiの月枠（250）とAnthropicのクレジットを消費し切った。
トリガーは削除済み。同日の二重実行を防ぐガードも `auto_check.py` に入れた
（取り直す場合のみ `AIO_FORCE=1`）。

なお、この日に生成された `2026-10-28-auto.yml` は水曜の記録で欠損も大きかったため削除した。

## APIの残高・枠の確認先

| サービス | 確認先 | 方式 |
|---|---|---|
| Anthropic（Claude） | https://console.anthropic.com/settings/billing | 都度チャージ。Auto reload推奨 |
| Google（Gemini） | https://ai.studio/projects | 前払いクレジット |
| OpenAI（ChatGPT） | https://platform.openai.com/settings/organization/billing | 都度チャージ |
| SerpApi（Google AIモード） | https://serpapi.com/dashboard | 無料プラン月250検索、毎月リセット |

## SerpApiの無料枠の配分（複数社を観測する場合）

SerpApiの無料枠は**月250検索**で、これが複数社展開の律速になる。
Claude/Gemini/ChatGPTは従量課金なので増やせるが、SerpApiは枠を超えると止まる。

| 会社 | Google AI Modeに回す質問数 | 月の消費 |
|---|---|---|
| ARIGATO Living | 30問（全問） | 130回 |
| AiMY | 12問（`engine_queries` で絞り） | 52回 |
| **合計** | | **182回**（残68回） |

残68回は、再実行・調査・新規1社の立ち上げ分として空けてある。

### 絞り方

`config.yml` に `engine_queries` を書くと、そのエンジンだけ質問を絞れる。
指定のないエンジンは全問打つ。

```yaml
engine_queries:
  google_ai_mode:
    - q1
    - q7
```

絞ったエンジンは、その週に1問も割り当てられなくても欠測扱いにしない。

3社目を足すときは、まずこの表を更新して合計が250に収まるか確認する。
収まらない場合の選択肢は、質問をさらに絞る／隔週にする／有料プラン
（月$75・5,000検索）に上げる。

---

## 欠測: 2026-11-20 AiMY 初回観測（データ復元）

AiMYの初回観測で、200回のAPI呼び出しはすべて成功したが、保存先の
`data/aimy/observations/` が存在せず `FileNotFoundError` で落ち、
2時間24分ぶんの結果がコミットされないまま失われた。

対応:

1. `OBS_DIR.mkdir(parents=True, exist_ok=True)` を追加（新しい会社を
   足したときに同じ事故が起きないようにした）
2. 1問ごとに保存するようにした（最後にまとめて書く作りだったため、
   落ちた時点で全部無駄になっていた）
3. ジョブログの標準出力から判定を復元し、
   `data/aimy/observations/2026-11-20-partial.yml` に残した
   （`scripts/recover_from_log.py`）

復元できたのは ◎○△× の判定・順位・試行回数。
**引用元URL・回答本文・競合名は復元できない**（ログに出力されないため）。
そのため `-partial.yml` として週次集計からは除外し、記録としてのみ残す。
正式なベースラインは次回の定期実行（火曜）で取り直す。
noteは現在0記事で、AIの引用は3週前後遅れるため、火曜でもゼロ地点として有効。
