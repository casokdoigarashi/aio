#!/usr/bin/env python3
"""手動観測（Google AIモードのスクリーンショット記録）用のテンプレートを生成する。

使い方:
  python scripts/new_observation.py            # 今日の日付
  python scripts/new_observation.py 2026-07-22 # 日付指定

生成された data/observations/<日付>.yml を開き、スクショを見ながら
各クエリの brand_mentioned / mention_position などを埋める。
"""
from __future__ import annotations

import datetime
import sys

import yaml

from lib_common import OBS_DIR, load_config


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    out_path = OBS_DIR / f"{date}.yml"
    if out_path.exists():
        print(f"既に存在します: {out_path}")
        sys.exit(1)

    config = load_config()
    entries = []
    for q in config["queries"]:
        entries.append(
            {
                "query_id": q["id"],
                "query": q["text"],
                "engine": "google_ai_mode",
                "brand_mentioned": False,
                # featured / listed / cited_only / none
                "mention_position": "none",
                "mention_text": "",
                "cited": False,
                "cited_sources": [],
                "own_site_cited": False,
                "related_cited": False,
                "competitors_mentioned": [],
                "screenshot": "",
                "notes": "",
            }
        )

    payload = {
        "date": date,
        "method": "manual_screenshot",
        "source": "Google AIモード（手動スクリーンショット）",
        "queries": entries,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False, width=100)
    print(f"テンプレートを作成しました: {out_path}")
    print("スクショを確認しながら各項目を記入してください。")


if __name__ == "__main__":
    main()
