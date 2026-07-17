# ARIGATO Living AIO 定点観測プロジェクト

ハウススタジオ [ARIGATO Living（神楽坂）](https://www.a-ms2.com/arigatoliving/) の
AI検索（Google AIモード・Perplexity・Gemini等）での露出を週次で定点観測し、
**1次情報の発信（note・Yahoo! PR等）がAIO（AI検索最適化）に与える効果**を
データとして検証・レポートするためのリポジトリです。

## 仕組みの全体像

```
┌─ 施策 ──────────────┐      ┌─ 週次観測（毎週火曜） ─────────────┐
│ note記事 / Yahoo!PR │      │ 自動: auto_check.py (GitHub Actions)│
│ サイト更新 など      │      │   Perplexity / Gemini / SerpAPI    │
│  → data/actions.yml │      │ 手動: Google AIモードのスクショ      │
└─────────┬──────────┘      │   → new_observation.py で記録       │
          │                  └────────────┬───────────────────┘
          │                               │ data/observations/*.yml
          └───────────┬───────────────────┘
                      ▼
              analyze.py（レポート生成）
                      ▼
      reports/summary.md（トレンド表・言及率・施策タイムライン）
      reports/weekly/<日付>.md（週次詳細）
```

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `config/config.yml` | ブランド表記ゆれ・観測クエリ・競合・引用元ドメインの定義 |
| `data/observations/` | 週次の観測データ（1観測=1ファイル、YAML） |
| `data/actions.yml` | 施策ログ（note公開・PR出稿などを都度追記） |
| `scripts/auto_check.py` | AI検索APIによる自動観測 |
| `scripts/new_observation.py` | 手動観測（スクショ記録）用テンプレート生成 |
| `scripts/analyze.py` | レポート生成 |
| `reports/` | 生成されたレポート（summary + 週次） |
| `docs/RUNBOOK.md` | 週次運用手順 |
| `docs/METRICS.md` | 指標の定義と読み方 |

## クイックスタート

```bash
pip install -r scripts/requirements.txt

# レポート生成（ベースラインデータ入り）
python scripts/analyze.py

# 自動観測（APIキーのあるエンジンのみ実行される）
export GEMINI_API_KEY=...
python scripts/auto_check.py
```

GitHub Actions（`.github/workflows/weekly-aio-check.yml`）が毎週火曜9:00 JSTに
自動観測とレポート更新を実行します。APIキーはリポジトリのSecretsに登録してください。

## プロジェクトの進め方（フェーズ）

1. **Phase 0（完了）**: ベースライン取得 — 2026-07-15 のGoogle AIモードのスクショを
   `data/observations/2026-07-15.yml` に構造化済み
2. **Phase 1（〜8月）**: 観測の習慣化 — 週次観測を3〜4回まわして観測条件を安定させる。
   並行してnote開設・初回記事公開（公開したら `data/actions.yml` と
   `config/config.yml` の `related_domains` に追記）
3. **Phase 2（8〜9月）**: 施策の投下 — note記事の継続、Yahoo! PR出稿。
   施策ごとに狙いのクエリ（target_queries）を決めてから出す
4. **Phase 3（10月〜）**: 効果検証レポート — 施策タイムラインと言及率・引用元の変化を
   突き合わせ、「どの発信がAI回答に反映されたか」を分析レポートとしてまとめる

詳細な運用手順は [docs/RUNBOOK.md](docs/RUNBOOK.md)、指標の定義は
[docs/METRICS.md](docs/METRICS.md) を参照。
