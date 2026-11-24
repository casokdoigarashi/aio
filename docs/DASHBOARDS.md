# レポートの見る場所

観測結果はリポジトリの `reports/` にもMarkdownで出るが、
普段見るのはこちらのダッシュボード。

| 会社 | ダッシュボード |
|---|---|
| ARIGATO Living | https://claude.ai/artifact/3aCsU27iP5Ex2aHJzAtBVX |
| AiMY（ツカモトコーポレーション） | https://claude.ai/artifact/BPrBRCF6F3TaNyBVBSNpin |

どちらも**既定では本人しか開けない**。他の人に見せるときは、
ページ右上の共有メニューから共有する。共有していないリンクを渡しても相手は開けない。

## 中身の更新

ダッシュボードは観測データのファイルを読んで描いている。
週次観測でデータが増えても、ダッシュボードのファイルは自動では差し替わらない。
新しい週を反映したいときは、その週のデータでファイルを入れ替える。

| 会社 | データの元 |
|---|---|
| ARIGATO Living | `data/observations/*.yml` |
| AiMY | `data/aimy/observations/*.yml` |

## AiMYダッシュボードの注記

初回（2026-11-20）のデータは実行ログから復元したもので、
引用元URLと競合名が入っていない。経緯は RUNBOOK.md の欠測記録を参照。
次回の定期実行から完全な記録になる。
