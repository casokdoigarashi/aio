#!/usr/bin/env python3
"""観測データを Google スプレッドシートに書き込む。

  python scripts/export_sheets.py              # 全期間を書き直す
  python scripts/export_sheets.py 2026-11-24   # その週の分だけ追記する

認証は環境変数 GOOGLE_SERVICE_ACCOUNT_JSON（サービスアカウントの鍵JSONそのもの）。
初回設定の手順は docs/SHEETS_SETUP.md。

シートの構成:
  runs        1行 = 1質問 × 1エンジン × 1試行（生ログ）
  weekly      1行 = 週 × 質問 × エンジン（出現率つき）
  citations   週ごとの引用元ドメイン
  competitors 週ごとの競合の言及
  heatmap     縦に質問・横に週。出現率を色の濃さで見る
  social      Instagram / Googleトレンド（④で実装）
"""
from __future__ import annotations

import collections
import json
import os
import sys
from urllib.parse import urlparse

from lib_common import POSITION_SYMBOLS, load_config, load_observations

SHEET_HEADERS = {
    "runs": [
        "date", "client_id", "query_id", "query_text", "engine", "model", "trial",
        "brand_mentioned", "position", "rank", "rank_total", "own_cited",
        "related_cited", "cited_domains", "competitors", "answer_text", "error",
        "updated_at",
    ],
    "weekly": [
        "date", "client_id", "query_id", "query_text", "intent", "engine",
        "trials", "hits", "hit_rate", "best_position", "mean_rank",
    ],
    "citations": [
        "date", "client_id", "engine", "domain", "domain_class",
        "query_count", "query_ids",
    ],
    "competitors": [
        "date", "client_id", "engine", "competitor", "mention_count", "share_of_voice",
    ],
}

POSITION_ORDER = {"none": 0, "cited_only": 1, "listed": 2, "featured": 3}


def _client():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        print(
            "GOOGLE_SERVICE_ACCOUNT_JSON が未設定です。\n"
            "サービスアカウントの鍵をGitHub Secretsに登録してください"
            "（手順: docs/SHEETS_SETUP.md）。"
        )
        sys.exit(1)
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"GOOGLE_SERVICE_ACCOUNT_JSON がJSONとして読めません: {exc}")
        sys.exit(1)

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _domain(url: str) -> str:
    """URLでもドメイン文字列でもドメインを返す（Geminiはドメインのみを返すため）。"""
    if not url:
        return ""
    if "://" not in url:
        return url.strip().lower()
    return (urlparse(url).netloc or url).lower().removeprefix("www.")


def _domain_class(domain: str, config: dict) -> str:
    own = config["brand"].get("own_domains", [])
    related = config["brand"].get("related_domains", [])
    competitor_domains = [
        d for c in config.get("competitors", []) for d in (c.get("domains") or [])
    ]
    if any(d in domain for d in own):
        return "自社"
    if any(d in domain for d in related):
        return "関連メディア"
    if any(d in domain for d in competitor_domains):
        return "競合"
    return "その他"


def build_rows(observations: list[dict], config: dict) -> dict[str, list[list]]:
    """観測データを、シートごとの行の集まりに変換する。"""
    client_id = config.get("client_id", "default")
    intents = {q["id"]: q.get("intent", "") for q in config["queries"]}
    models = config.get("models", {}) or {}

    rows: dict[str, list[list]] = {name: [] for name in SHEET_HEADERS}
    # (date, engine, query_id) ごとに試行をまとめるための入れ物
    grouped: dict = collections.defaultdict(list)

    for obs in observations:
        date = str(obs["date"])
        updated = str(obs.get("generated_at") or "")
        for entry in obs["queries"]:
            engine = entry.get("engine", "unknown")
            qid = entry.get("query_id") or entry["query"]
            domains = [_domain(s) for s in (entry.get("cited_sources") or []) if s]
            rows["runs"].append([
                date, client_id, qid, entry.get("query", ""), engine,
                models.get(engine, ""), entry.get("trial", 1),
                bool(entry.get("brand_mentioned")),
                entry.get("mention_position", ""),
                entry.get("rank") or "", entry.get("rank_total") or "",
                bool(entry.get("own_site_cited")), bool(entry.get("related_cited")),
                ", ".join(domains),
                ", ".join(entry.get("competitors_mentioned") or []),
                (entry.get("answer_text") or "")[:45000],  # セル上限5万字に対する余裕
                entry.get("error", ""), updated,
            ])
            grouped[(date, engine, qid)].append(entry)

    # weekly: 試行をまとめて出現率にする
    for (date, engine, qid), entries in sorted(grouped.items()):
        hits = sum(1 for e in entries if e.get("brand_mentioned"))
        best = max(
            entries, key=lambda e: POSITION_ORDER.get(e.get("mention_position", "none"), 0)
        )
        ranks = [e["rank"] for e in entries if e.get("rank")]
        rows["weekly"].append([
            date, client_id, qid, entries[0].get("query", ""), intents.get(qid, ""),
            engine, len(entries), hits, round(hits / len(entries), 3),
            best.get("mention_position", ""),
            round(sum(ranks) / len(ranks), 1) if ranks else "",
        ])

    # citations / competitors: 週 × エンジンで集計
    cite_counter: dict = collections.defaultdict(lambda: collections.defaultdict(set))
    comp_counter: dict = collections.defaultdict(collections.Counter)
    for (date, engine, qid), entries in grouped.items():
        for entry in entries:
            for src in entry.get("cited_sources") or []:
                dom = _domain(src)
                if dom:
                    cite_counter[(date, engine)][dom].add(qid)
            for comp in entry.get("competitors_mentioned") or []:
                comp_counter[(date, engine)][comp] += 1

    for (date, engine), domains in sorted(cite_counter.items()):
        for dom, qids in sorted(domains.items(), key=lambda kv: -len(kv[1])):
            rows["citations"].append([
                date, client_id, engine, dom, _domain_class(dom, config),
                len(qids), ", ".join(sorted(qids, key=lambda q: int(q[1:]) if q[1:].isdigit() else 0)),
            ])

    for (date, engine), counts in sorted(comp_counter.items()):
        total = sum(counts.values()) or 1
        for comp, n in counts.most_common():
            rows["competitors"].append([
                date, client_id, engine, comp, n, round(n / total, 3),
            ])

    return rows


def build_heatmap(observations: list[dict], config: dict) -> list[list]:
    """縦に質問、横に週。値は出現率（0〜1）。全エンジンをまとめた値。"""
    dates = sorted({str(o["date"]) for o in observations})
    per: dict = collections.defaultdict(lambda: [0, 0])  # (qid, date) -> [hits, trials]
    for obs in observations:
        date = str(obs["date"])
        for entry in obs["queries"]:
            qid = entry.get("query_id") or entry["query"]
            per[(qid, date)][1] += 1
            if entry.get("brand_mentioned"):
                per[(qid, date)][0] += 1

    out = [["query_id", "query_text", *dates]]
    for q in config["queries"]:
        row = [q["id"], q["text"]]
        for date in dates:
            hits, trials = per.get((q["id"], date), [0, 0])
            row.append(round(hits / trials, 3) if trials else "")
        out.append(row)
    return out


def write_sheet(service, spreadsheet_id: str, name: str, values: list[list]) -> None:
    """シートを一度まるごと消してから書き直す（重複を作らないため）。"""
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=name
    ).execute()
    if not values:
        return
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{name}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    print(f"  {name}: {len(values) - 1}行")


def apply_heatmap_format(service, spreadsheet_id: str, width: int, height: int) -> None:
    """出現率を色の濃さで表す（0=白、1=濃い緑）。"""
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties"
    ).execute()
    sheet_id = next(
        (s["properties"]["sheetId"] for s in meta["sheets"]
         if s["properties"]["title"] == "heatmap"), None
    )
    if sheet_id is None:
        return
    grid = {
        "sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": height,
        "startColumnIndex": 2, "endColumnIndex": width,
    }
    requests = [
        # 既存のルールを消す（毎回入れ直す）
        *[{"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}} for _ in range(5)],
        {"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [grid],
            "gradientRule": {
                "minpoint": {"colorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
                             "type": "NUMBER", "value": "0"},
                "maxpoint": {"colorStyle": {"rgbColor": {"red": 0.25, "green": 0.55, "blue": 0.35}},
                             "type": "NUMBER", "value": "1"},
            },
        }}},
    ]
    for req in requests:
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"requests": [req]}
            ).execute()
        except Exception:
            pass  # 消すルールが無い場合は無視してよい


def main() -> None:
    config = load_config()
    spreadsheet_id = (config.get("sheets") or {}).get("spreadsheet_id")
    if not spreadsheet_id:
        print("config.yml に sheets.spreadsheet_id がありません")
        sys.exit(1)

    observations = load_observations()
    if len(sys.argv) > 1:
        target = sys.argv[1]
        observations = [o for o in observations if str(o["date"]) == target]
        if not observations:
            print(f"{target} の観測データがありません")
            sys.exit(1)
        print(f"{target} の分だけ書き込みます（シートは全期間で作り直されます）")
        observations = load_observations()  # 書き直すので結局は全期間を使う

    print(f"観測 {len(observations)}週分をスプレッドシートに書き込みます")
    service = _client()
    rows = build_rows(observations, config)
    for name, header in SHEET_HEADERS.items():
        write_sheet(service, spreadsheet_id, name, [header, *rows[name]])

    heatmap = build_heatmap(observations, config)
    write_sheet(service, spreadsheet_id, "heatmap", heatmap)
    apply_heatmap_format(service, spreadsheet_id, len(heatmap[0]), len(heatmap))

    print(f"完了: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")


if __name__ == "__main__":
    main()
