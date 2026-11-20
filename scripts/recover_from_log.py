"""失敗したジョブのログから観測結果を復元する。

200回のAPI呼び出しはすべて成功していたが、保存先ディレクトリが無く
FileNotFoundError で落ちたため、データがコミットされなかった。
標準出力には1回ごとの判定が残っているので、そこから組み立て直す。

引用元URLと回答本文はログに出ていないため復元できない。
したがって週次集計には混ぜず、-partial.yml として記録だけ残す。
"""
import re
import sys
from pathlib import Path

import yaml

LOG = sys.argv[1]
OUT = Path(sys.argv[2])

raw = open(LOG, encoding="utf-8").read().replace("\\n", "\n")
lines = [re.sub(r"^\S+Z ", "", l) for l in raw.splitlines()]
lines = [l.replace("\\u003e", ">").replace("\\u003c", "<") for l in lines]

CALL = re.compile(r"^\[(?P<engine>[a-z_]+)\] (?P<query>.+?)(?: \(試行 (?P<trial>\d+)/\d+\))?$")
RESULT = re.compile(r"^\s+-> (?P<mention>言及あり|言及なし) \((?P<pos>\w+)\)(?: / (?P<rank>\d+)番目)?$")

cfg = yaml.safe_load(open("/home/user/aio/clients/aimy/config.yml", encoding="utf-8"))
qid = {q["text"]: q["id"] for q in cfg["queries"]}

records = []
pending = None
for line in lines:
    m = RESULT.match(line)
    if m and pending:
        engine, query, trial = pending
        records.append({
            "query_id": qid.get(query, "?"),
            "query": query,
            "engine": engine,
            "trial": int(trial or 1),
            "rank": int(m["rank"]) if m["rank"] else None,
            "rank_total": 0,
            "brand_mentioned": m["mention"] == "言及あり",
            "mention_position": m["pos"],
            "mention_text": "",
            # 引用元URLそのものはログに出ていないが、cited_only は
            # 「自社ドメインか関連メディアが引用された」判定の結果なので、
            # 引用があった事実だけは確実に言える。
            "cited": True if m["pos"] == "cited_only" else None,
            "cited_sources": [],
            "own_site_cited": None,
            "related_cited": None,
            "competitors_mentioned": [],  # ログに残っていない
            "answer_text": "",
            "notes": "ログから復元（引用元・回答本文・競合は復元不可）",
        })
        pending = None
        continue
    m = CALL.match(line)
    if m:
        pending = (m["engine"], m["query"], m["trial"])

unknown = [r for r in records if r["query_id"] == "?"]
print(f"復元した判定: {len(records)}件（質問IDが引けなかったもの: {len(unknown)}件）")

payload = {
    "date": "2026-11-20",
    "method": "api_auto_recovered",
    "source": "自動観測（ジョブログから復元。引用元データなし）",
    "queries": records,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False, width=100)
print(f"保存: {OUT}")
