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
from collections import Counter, defaultdict

from lib_common import (
    POSITION_LABELS,
    POSITION_SYMBOLS,
    REPORTS_DIR,
    load_actions,
    load_config,
    load_observations,
)

ENGINE_LABELS = {
    "google_ai_mode": "Google AIモード",
    "claude": "Claude（web search）",
    "chatgpt": "ChatGPT（web search）",
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
            key = (engine, entry.get("query_id") or entry["query"], date)
            if key in index:
                # 同日・同クエリ・同エンジンが重複（手動観測とAPI観測が併存した等）。
                # 目視で判定した手動観測を優先し、取りこぼしに気づけるよう警告する。
                existing_manual = index[key].get("_method") == "manual_screenshot"
                print(f"警告: 観測が重複しています {key}。"
                      f"{'手動' if existing_manual else '後勝ち'}の値を採用します")
                if existing_manual:
                    continue
            entry["_method"] = obs.get("method")
            index[key] = entry
    return index, dates, engines


def _domain_class(domain: str, config: dict) -> str:
    """引用元ドメインを 自社 / 関連メディア / その他 に分類する。"""
    own = config["brand"].get("own_domains", [])
    related = config["brand"].get("related_domains", [])
    if any(d in domain for d in own):
        return "自社"
    if any(d in domain for d in related):
        return "関連メディア"
    return "その他"


def build_citation_ranking(entries: list[dict], config: dict, date) -> list[str]:
    """引用元ドメインのランキング。どの媒体を強化すべきかの判断材料。"""
    counter = Counter()
    for entry in entries:
        # 同一回答内の重複はまとめ、「何クエリで引用されたか」を数える
        for domain in set(str(s) for s in entry.get("cited_sources", []) if s):
            counter[domain] += 1
    lines = [f"## 引用元ランキング（{date}）", ""]
    if not counter:
        return lines + ["（引用元データなし）", ""]
    lines += [
        "AIが情報源にしている媒体。上位ほど「AIが読んでいる場所」なので、",
        "掲載内容の改善が効きやすい。",
        "",
        "| 媒体 | 引用されたクエリ数 | 区分 |",
        "|---|---|---|",
    ]
    for domain, count in counter.most_common(15):
        lines.append(f"| {domain} | {count} | {_domain_class(domain, config)} |")
    return lines + [""]


def build_share_of_voice(entries: list[dict], config: dict, date) -> list[str]:
    """自社と競合の登場回数を並べる（絶対評価では立ち位置が分からないため）。"""
    brand = config["brand"]["name"]
    counts = Counter()
    total = len(entries)
    for entry in entries:
        if entry.get("brand_mentioned"):
            counts[brand] += 1
        for comp in entry.get("competitors_mentioned", []):
            counts[comp] += 1
    lines = [f"## シェア・オブ・ボイス（{date}）", ""]
    if not total:
        return lines + ["（データなし）", ""]
    lines += [
        f"全{total}回答（クエリ×エンジン）のうち、各スタジオが言及された回数。",
        "",
        "| スタジオ | 言及回数 | 占有率 |",
        "|---|---|---|",
    ]
    for name, count in counts.most_common():
        mark = " ★自社" if name == brand else ""
        lines.append(f"| {name}{mark} | {count} | {count / total * 100:.0f}% |")
    return lines + [""]


def build_opportunity_loss(index, queries, engines, date) -> list[str]:
    """機会損失＝自社の情報源は引用されたのに、名前は競合だけが挙がったケース。

    「掲載はされているのにAIが名前を拾わない」という、最も改善余地の大きい状態。
    """
    rows = []
    for q in queries:
        for engine in engines:
            entry = index.get((engine, q["id"], date))
            if not entry:
                continue
            cited = entry.get("own_site_cited") or entry.get("related_cited")
            comps = entry.get("competitors_mentioned", [])
            if cited and not entry.get("brand_mentioned") and comps:
                rows.append(
                    f"| {q['text']} | {ENGINE_LABELS.get(engine, engine)} | "
                    f"{'、'.join(comps)} |"
                )
    lines = [f"## 機会損失クエリ（{date}）", ""]
    if not rows:
        return lines + ["該当なし。", ""]
    lines += [
        "自社が載っている媒体をAIが読んでいるのに、回答で名前が挙がったのは競合だけ、",
        "というクエリ。掲載ページの書き方を直せば取り返せる可能性が高い。",
        "",
        "| クエリ | エンジン | 代わりに挙がった競合 |",
        "|---|---|---|",
        *rows,
    ]
    return lines + [""]


def build_accuracy_check(index, queries, engines, date) -> list[str]:
    """AIの説明が事実として正しいかを人が確認するためのセクション。

    自動判定はできないため、言及内容と誤参照リスクを一覧化して目視に回す。
    """
    lines = [f"## 事実確認（{date}）", "", "AIの説明に誤りがないか目視で確認する。", ""]
    risky, excerpts = [], []
    for q in queries:
        for engine in engines:
            entry = index.get((engine, q["id"], date))
            if not entry or not entry.get("brand_mentioned"):
                continue
            label = ENGINE_LABELS.get(engine, engine)
            # 自社・関連メディアを一切引用せずに語っている＝誤情報の温床
            if not (entry.get("own_site_cited") or entry.get("related_cited")):
                srcs = ", ".join(str(s) for s in entry.get("cited_sources", [])[:5])
                risky.append(f"| {q['text']} | {label} | {srcs or '(引用元なし)'} |")
            if entry.get("mention_text"):
                excerpts.append(f"- **{q['text']}**（{label}）: {entry['mention_text']}")
    if risky:
        lines += [
            "### ⚠ 誤参照リスク",
            "",
            "自社サイトも掲載メディアも引用せずにブランドを語っているケース。",
            "他社との混同や古い情報が混ざりやすい。",
            "",
            "| クエリ | エンジン | 実際の引用元 |",
            "|---|---|---|",
            *risky,
            "",
        ]
    if excerpts:
        lines += ["### AIによる説明（要確認）", "", *excerpts, ""]
    return lines


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

    # 言及率はエンジン別に出す（エンジンごとに露出構造が違うため平均は意味を持たない）
    lines += ["## 言及率の推移（エンジン別）", ""]
    header = "| エンジン | " + " | ".join(dates) + " |"
    lines += [header, "|---" * (len(dates) + 1) + "|"]
    for engine in engines:
        cells = []
        for date in dates:
            entries = [
                index[(e, q["id"], date)]
                for q in queries
                for e in [engine]
                if (e, q["id"], date) in index
            ]
            if not entries:
                cells.append("－")
                continue
            mentioned = sum(1 for e in entries if e.get("brand_mentioned"))
            cells.append(f"{mentioned}/{len(entries)}")
        lines.append(
            f"| {ENGINE_LABELS.get(engine, engine)} | " + " | ".join(cells) + " |"
        )
    lines.append("")

    latest = dates[-1] if dates else None
    latest_entries = [e for (_, _, d), e in index.items() if d == latest]

    lines += build_citation_ranking(latest_entries, config, latest)
    lines += build_share_of_voice(latest_entries, config, latest)
    lines += build_opportunity_loss(index, queries, engines, latest)
    lines += build_accuracy_check(index, queries, engines, latest)

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


POSITION_RANK = {"none": 0, "cited_only": 1, "listed": 2, "featured": 3}


def build_change_report(config, observations, target_date: str) -> list[str]:
    """前回観測との差分。「今週何が変わったか」だけを短くまとめる。"""
    index, dates, engines = collect(observations)
    queries = config["queries"]
    brand = config["brand"]["name"]

    if target_date not in dates or dates.index(target_date) == 0:
        return ["## 今週の変化", "", "前回観測がないため比較できません（初回観測）。", ""]
    prev_date = dates[dates.index(target_date) - 1]

    improved, declined = [], []
    for q in queries:
        for engine in engines:
            now = index.get((engine, q["id"], target_date))
            before = index.get((engine, q["id"], prev_date))
            if not now or not before:
                continue  # 片方しか観測がないクエリは変化として扱わない
            a = POSITION_RANK.get(before.get("mention_position") or "none", 0)
            b = POSITION_RANK.get(now.get("mention_position") or "none", 0)
            if a == b:
                continue
            row = (
                f"- 「{q['text']}」（{ENGINE_LABELS.get(engine, engine)}）: "
                f"{symbol(before)} → {symbol(now)}"
            )
            (improved if b > a else declined).append(row)

    def _cited(date: str) -> set[str]:
        return {
            str(s)
            for (_, _, d), e in index.items()
            if d == date
            for s in e.get("cited_sources", [])
            if s
        }

    new_sources = sorted(_cited(target_date) - _cited(prev_date))
    lost_sources = sorted(_cited(prev_date) - _cited(target_date))

    def _sov(date: str) -> dict:
        counts = Counter()
        for (_, _, d), e in index.items():
            if d != date:
                continue
            if e.get("brand_mentioned"):
                counts[brand] += 1
            for comp in e.get("competitors_mentioned", []):
                counts[comp] += 1
        return counts

    sov_now, sov_prev = _sov(target_date), _sov(prev_date)
    rank_now = [n for n, _ in sov_now.most_common()]
    rank_prev = [n for n, _ in sov_prev.most_common()]

    lines = [f"## 今週の変化（{prev_date} → {target_date}）", ""]
    if not improved and not declined:
        lines += ["判定に変化のあったクエリはありませんでした。", ""]
    if improved:
        lines += [f"### 改善 {len(improved)}件", "", *improved, ""]
    if declined:
        lines += [f"### 低下 {len(declined)}件", "", *declined, ""]

    lines += ["### シェア・オブ・ボイス", ""]
    my_now, my_prev = sov_now.get(brand, 0), sov_prev.get(brand, 0)
    pos_now = rank_now.index(brand) + 1 if brand in rank_now else None
    pos_prev = rank_prev.index(brand) + 1 if brand in rank_prev else None
    lines += [
        f"- 自社の言及回数: {my_prev} → {my_now}（{my_now - my_prev:+d}）",
        f"- 順位: {pos_prev or '圏外'}位 → {pos_now or '圏外'}位",
        "",
    ]

    if new_sources or lost_sources:
        lines += ["### 引用元の入れ替わり", ""]
        if new_sources:
            lines.append("- 新たに引用: " + "、".join(new_sources[:10]))
        if lost_sources:
            lines.append("- 引用されなくなった: " + "、".join(lost_sources[:10]))
        lines.append("")
    return lines


def build_weekly(config, observations, actions, target_date: str) -> str:
    brand = config["brand"]["name"]
    obs_list = [o for o in observations if str(o["date"]) == target_date]
    lines = [f"# 週次レポート {target_date} — {brand}", ""]
    lines += build_change_report(config, observations, target_date)

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

    lines += ["---", "", "## 観測の詳細", ""]
    for obs in obs_list:
        lines += [f"### {obs.get('source', obs.get('method', ''))}", ""]
        for entry in obs["queries"]:
            engine = ENGINE_LABELS.get(entry.get("engine"), entry.get("engine"))
            pos = POSITION_LABELS.get(entry.get("mention_position") or "none", "－")
            lines += [f"#### 「{entry['query']}」（{engine}）", "", f"- 判定: {pos}"]
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
