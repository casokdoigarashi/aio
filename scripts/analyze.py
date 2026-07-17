#!/usr/bin/env python3
"""観測データと施策ログからレポートを生成する。

生成物:
  reports/summary.md            全期間のトレンドサマリー（定点観測ダッシュボード）
  reports/weekly/<日付>.md      最新観測日の詳細レポート

使い方:
  python scripts/analyze.py
"""
from __future__ import annotations

import datetime
from collections import defaultdict

from lib_common import (
    POSITION_LABELS,
    POSITION_SYMBOLS,
    REPORTS_DIR,
    load_actions,
    load_config,
    load_observations,
)

ENGINE_LABELS = {
    "google_ai_mode": "Google AIモード（手動）",
    "perplexity": "Perplexity",
    "gemini": "Gemini（Google検索グラウンディング）",
    "serpapi_google": "Google AI Overview + 通常検索（SerpAPI）",
}


def symbol(entry: dict) -> str:
    return POSITION_SYMBOLS.get(entry.get("mention_position") or "none", "－")


def collect(observations: list[dict]):
    """(engine, query_id, date) -> entry の索引と、日付・クエリの一覧を作る。"""
    index = {}
    dates = []
    engines = []
    for obs in observations:
        date = str(obs["date"])
        if date not in dates:
            dates.append(date)
        for entry in obs["queries"]:
            engine = entry.get("engine", "unknown")
            if engine not in engines:
                engines.append(engine)
            index[(engine, entry.get("query_id") or entry["query"], date)] = entry
    return index, dates, engines


def build_summary(config, observations, actions) -> str:
    index, dates, engines = collect(observations)
    queries = config["queries"]
    brand = config["brand"]["name"]
    today = datetime.date.today().isoformat()

    lines = [
        f"# {brand} AIO定点観測サマリー",
        "",
        f"最終更新: {today} ／ 観測回数: {len(dates)}回 "
        f"({dates[0]} 〜 {dates[-1]})" if dates else "観測データなし",
        "",
        "凡例: ◎ 筆頭で紹介 ／ ○ リスト内で言及 ／ △ 引用リンクのみ ／ × 言及なし ／ － 未観測",
        "",
    ]

    # エンジン別トレンド表（行=クエリ、列=観測日）
    for engine in engines:
        label = ENGINE_LABELS.get(engine, engine)
        lines += [f"## {label}", ""]
        header = "| クエリ | " + " | ".join(dates) + " |"
        sep = "|---" * (len(dates) + 1) + "|"
        lines += [header, sep]
        for q in queries:
            cells = []
            for date in dates:
                entry = index.get((engine, q["id"], date))
                cells.append(symbol(entry) if entry else "－")
            lines.append(f"| {q['text']} | " + " | ".join(cells) + " |")
        lines.append("")

    # 観測日ごとの言及率
    lines += ["## 言及率の推移", ""]
    lines += ["| 観測日 | 言及あり／観測数 | 言及率 | 自社サイト引用 | 関連メディア引用 |", "|---|---|---|---|---|"]
    per_date = defaultdict(list)
    for (engine, qid, date), entry in index.items():
        per_date[date].append(entry)
    for date in dates:
        entries = per_date[date]
        total = len(entries)
        mentioned = sum(1 for e in entries if e.get("brand_mentioned"))
        own = sum(1 for e in entries if e.get("own_site_cited"))
        related = sum(1 for e in entries if e.get("related_cited"))
        rate = f"{mentioned / total * 100:.0f}%" if total else "-"
        lines.append(f"| {date} | {mentioned}/{total} | {rate} | {own}件 | {related}件 |")
    lines.append("")

    # 施策タイムライン
    lines += ["## 施策タイムライン", ""]
    if actions:
        lines += ["| 日付 | 種別 | 内容 | URL |", "|---|---|---|---|"]
        for a in actions:
            url = a.get("url") or ""
            link = f"[link]({url})" if url else ""
            lines.append(f"| {a['date']} | {a.get('type','')} | {a.get('title','')} | {link} |")
    else:
        lines.append("（施策の記録はまだありません。data/actions.yml に追記してください）")
    lines.append("")
    return "\n".join(lines)


def build_weekly(config, observations, actions, target_date: str) -> str:
    brand = config["brand"]["name"]
    obs_list = [o for o in observations if str(o["date"]) == target_date]
    lines = [f"# 週次レポート {target_date} — {brand}", ""]

    # 直近2週間の施策
    d = datetime.date.fromisoformat(target_date)
    recent = [
        a for a in actions
        if 0 <= (d - datetime.date.fromisoformat(str(a["date"]))).days <= 14
    ]
    if recent:
        lines += ["## 直近2週間の施策", ""]
        for a in recent:
            lines.append(f"- {a['date']} 【{a.get('type','')}】{a.get('title','')}")
        lines.append("")

    for obs in obs_list:
        lines += [f"## {obs.get('source', obs.get('method', ''))}", ""]
        for entry in obs["queries"]:
            engine = ENGINE_LABELS.get(entry.get("engine"), entry.get("engine"))
            pos = POSITION_LABELS.get(entry.get("mention_position") or "none", "－")
            lines += [f"### 「{entry['query']}」（{engine}）", "", f"- 判定: {pos}"]
            if entry.get("organic_rank") is not None:
                lines.append(f"- 通常検索の自社順位: {entry['organic_rank']}位")
            if entry.get("mention_text"):
                lines.append(f"- 言及内容: {entry['mention_text']}")
            if entry.get("cited_sources"):
                lines.append("- 引用元: " + " / ".join(str(s) for s in entry["cited_sources"][:8]))
            flags = []
            if entry.get("own_site_cited"):
                flags.append("自社サイト引用あり")
            if entry.get("related_cited"):
                flags.append("関連メディア引用あり")
            if flags:
                lines.append("- " + "、".join(flags))
            if entry.get("competitors_mentioned"):
                lines.append("- 競合の言及: " + "、".join(entry["competitors_mentioned"]))
            if entry.get("notes"):
                lines.append(f"- メモ: {entry['notes']}")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    config = load_config()
    observations = load_observations()
    actions = load_actions()

    if not observations:
        print("観測データがありません (data/observations/)。")
        return

    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "weekly").mkdir(exist_ok=True)

    summary_path = REPORTS_DIR / "summary.md"
    summary_path.write_text(build_summary(config, observations, actions), encoding="utf-8")
    print(f"生成: {summary_path}")

    latest = str(observations[-1]["date"])
    weekly_path = REPORTS_DIR / "weekly" / f"{latest}.md"
    weekly_path.write_text(build_weekly(config, observations, actions, latest), encoding="utf-8")
    print(f"生成: {weekly_path}")


if __name__ == "__main__":
    main()
