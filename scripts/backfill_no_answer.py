"""過去の観測データに「回答なし（条件を聞き返された）」の判定を入れ直す。

ChatGPTは「神楽坂 撮影スタジオ」のような短いキーワードだと、候補を挙げずに
「用途・日時・予算を教えてください」と聞き返すことがある。これを「言及なし(×)」
として記録していたため、候補に挙げてもらえなかったのと区別できず、
出現率を実態より低く見せていた。

過去のデータには回答本文が残っているので、同じ判定基準で遡って直せる。
回答本文を見て判定するだけで、APIは呼ばない。

    python scripts/backfill_no_answer.py --dry-run   # 変更点だけ出す
    python scripts/backfill_no_answer.py             # 書き換える
"""
from __future__ import annotations

import sys
from collections import Counter

import yaml

from lib_common import OBS_DIR, is_ask_back


def main(argv: list[str]) -> None:
    dry = "--dry-run" in argv
    files = [f for f in sorted(OBS_DIR.glob("*.yml")) if not f.name.endswith("-partial.yml")]
    if not files:
        raise SystemExit(f"観測ファイルがありません: {OBS_DIR}")

    changed_by_engine: Counter[str] = Counter()
    changed_files = 0

    for path in files:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or not data.get("queries"):
            continue

        hits = []
        for entry in data["queries"]:
            if (entry.get("mention_position") or "none") == "no_answer":
                continue
            if not is_ask_back(entry.get("answer_text") or "", entry.get("cited_sources") or []):
                continue
            was = entry.get("mention_position") or "none"
            entry["mention_position"] = "no_answer"
            entry["brand_mentioned"] = False
            entry["was_position"] = was  # 書き換える前の判定を残す
            hits.append(entry)
            changed_by_engine[entry.get("engine", "?")] += 1

        if not hits:
            continue
        changed_files += 1
        print(f"{path.name}: {len(hits)}件")
        for e in hits:
            print(f"    {e.get('engine'):16} {e.get('query_id'):5} "
                  f"{str(e.get('query'))[:28]:30} {e.get('was_position')} → no_answer")
        if not dry:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)

    print()
    print(f"対象ファイル {changed_files}/{len(files)}　書き換えた判定 {sum(changed_by_engine.values())}件")
    for engine, n in changed_by_engine.most_common():
        print(f"  {engine:16} {n}件")
    if dry:
        print("\n--dry-run のため書き換えていません。")


if __name__ == "__main__":
    main(sys.argv[1:])
