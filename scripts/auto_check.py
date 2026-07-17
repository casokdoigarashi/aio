#!/usr/bin/env python3
"""AI検索の自動定点観測。

環境変数にAPIキーが設定されているエンジンだけを実行し、
結果を data/observations/<日付>-auto.yml に保存する。

対応エンジン:
  - perplexity      : PERPLEXITY_API_KEY（引用付きAI回答）
  - gemini          : GEMINI_API_KEY（Google検索グラウンディング＝AIモードの近似）
  - serpapi_google  : SERPAPI_KEY（Google AI Overview + オーガニック順位）

使い方:
  python scripts/auto_check.py            # 今日の日付で実行
  python scripts/auto_check.py 2026-07-22 # 日付を指定して実行
"""
from __future__ import annotations

import datetime
import os
import sys
import time

import requests
import yaml

from lib_common import (
    OBS_DIR,
    brand_position,
    classify_citations,
    find_brand_mention,
    find_competitors,
    load_config,
)

TIMEOUT = 120


def check_perplexity(query: str, api_key: str) -> dict:
    resp = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "sonar",
            "messages": [{"role": "user", "content": query}],
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    citations = data.get("citations", []) or [
        r.get("url", "") for r in data.get("search_results", [])
    ]
    return {"text": text, "citations": citations}


GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# 優先順。キーで利用可能なものを自動選択する
GEMINI_MODEL_CANDIDATES = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
_gemini_models: list[str] | None = None  # キーで利用可能なモデル（優先順）
_gemini_exhausted: set[str] = set()  # クォータ切れ(429)になったモデル


def gemini_model_candidates(api_key: str) -> list[str]:
    """このAPIキーで使えるflash系モデルをListModelsから優先順で列挙する。"""
    global _gemini_models
    if _gemini_models is None:
        resp = requests.get(
            f"{GEMINI_BASE}/models",
            headers={"x-goog-api-key": api_key},
            params={"pageSize": 1000},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        available = {
            m["name"].removeprefix("models/")
            for m in resp.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        }
        preferred = [c for c in GEMINI_MODEL_CANDIDATES if c in available]
        others = sorted(
            m for m in available
            if "flash" in m and m not in preferred
            and not any(x in m for x in ("image", "live", "tts", "audio", "lite"))
        )
        _gemini_models = preferred + others
        print(f"  (Gemini候補モデル: {_gemini_models[:6]})")
    return [m for m in _gemini_models if m not in _gemini_exhausted]


def check_gemini(query: str, api_key: str) -> dict:
    """429(クォータ切れ)のモデルは除外しつつ、使えるモデルで検索グラウンディング付き回答を得る。"""
    candidates = gemini_model_candidates(api_key)
    if not candidates:
        raise RuntimeError("全Geminiモデルがクォータ切れ(429)です。課金設定または翌日の回復を確認してください。")
    last_exc: Exception | None = None
    for model in candidates:
        resp = requests.post(
            f"{GEMINI_BASE}/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key},
            json={
                "contents": [{"parts": [{"text": query}]}],
                "tools": [{"google_search": {}}],
            },
            timeout=TIMEOUT,
        )
        if resp.status_code in (404, 429):
            reason = "クォータ切れ" if resp.status_code == 429 else "利用不可"
            print(f"  ({model} は{reason}。次の候補を試します)")
            _gemini_exhausted.add(model)
            last_exc = requests.HTTPError(
                f"{resp.status_code} for {model}", response=resp
            )
            continue
        resp.raise_for_status()
        data = resp.json()
        break
    else:
        raise last_exc or RuntimeError("Gemini呼び出しに失敗しました")
    candidate = data["candidates"][0]
    text = "".join(
        p.get("text", "") for p in candidate.get("content", {}).get("parts", [])
    )
    chunks = candidate.get("groundingMetadata", {}).get("groundingChunks", [])
    citations = [c.get("web", {}).get("uri", "") for c in chunks]
    return {"text": text, "citations": citations}


def check_serpapi(query: str, api_key: str, own_domains: list[str]) -> dict:
    resp = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "q": query,
            "hl": "ja",
            "gl": "jp",
            "api_key": api_key,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    # AI Overview（表示された場合のみ）
    overview = data.get("ai_overview", {})
    text_blocks = overview.get("text_blocks", [])
    text = "\n".join(
        b.get("snippet", "") for b in text_blocks if b.get("snippet")
    )
    citations = [
        r.get("link", "") for r in overview.get("references", []) if r.get("link")
    ]

    # 通常検索での自社順位
    organic_rank = None
    for result in data.get("organic_results", []):
        if any(d in result.get("link", "") for d in own_domains):
            organic_rank = result.get("position")
            break
    return {"text": text, "citations": citations, "organic_rank": organic_rank}


def evaluate(query_cfg: dict, engine: str, raw: dict, config: dict) -> dict:
    text = raw.get("text", "")
    citations = [c for c in raw.get("citations", []) if c]
    cite_flags = classify_citations(citations, config)
    mentioned = find_brand_mention(text, config)
    position = brand_position(text, config)
    if not mentioned and (cite_flags["own_site_cited"] or cite_flags["related_cited"]):
        position = "cited_only"
    entry = {
        "query_id": query_cfg["id"],
        "query": query_cfg["text"],
        "engine": engine,
        "brand_mentioned": mentioned,
        "mention_position": position,
        "mention_text": _brand_excerpt(text, config) if mentioned else "",
        "cited": bool(citations),
        "cited_sources": citations,
        "own_site_cited": cite_flags["own_site_cited"],
        "related_cited": cite_flags["related_cited"],
        "competitors_mentioned": find_competitors(text, config),
        "answer_text": text,
        "notes": "",
    }
    if raw.get("organic_rank") is not None:
        entry["organic_rank"] = raw["organic_rank"]
    return entry


def _brand_excerpt(text: str, config: dict, width: int = 150) -> str:
    """回答テキスト中のブランド言及箇所の前後を抜粋する。"""
    for alias in config["brand"]["aliases"]:
        idx = text.find(alias)
        if idx >= 0:
            start = max(0, idx - width // 2)
            return text[start : start + width].strip()
    return ""


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    config = load_config()
    own_domains = config["brand"].get("own_domains", [])

    engines = {
        "perplexity": os.environ.get("PERPLEXITY_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "serpapi_google": os.environ.get("SERPAPI_KEY"),
    }
    active = {name: key for name, key in engines.items() if key}
    if not active:
        print(
            "APIキーが設定されていません "
            "(PERPLEXITY_API_KEY / GEMINI_API_KEY / SERPAPI_KEY)。"
            "自動観測をスキップします。"
        )
        return

    entries = []
    for query_cfg in config["queries"]:
        query = query_cfg["text"]
        for engine, key in active.items():
            print(f"[{engine}] {query}")
            try:
                if engine == "perplexity":
                    raw = check_perplexity(query, key)
                elif engine == "gemini":
                    raw = check_gemini(query, key)
                else:
                    raw = check_serpapi(query, key, own_domains)
            except Exception as exc:  # 個別失敗は記録して続行
                detail = ""
                resp = getattr(exc, "response", None)
                if resp is not None:
                    detail = f" / {resp.text[:300]}"
                print(f"  -> エラー: {exc}{detail}")
                continue
            entry = evaluate(query_cfg, engine, raw, config)
            mark = "言及あり" if entry["brand_mentioned"] else "言及なし"
            print(f"  -> {mark} ({entry['mention_position']})")
            entries.append(entry)
            time.sleep(5)  # 無料枠のRPM制限対策

    if not entries:
        print("観測結果が1件も取得できませんでした。")
        sys.exit(1)

    out_path = OBS_DIR / f"{date}-auto.yml"
    payload = {
        "date": date,
        "method": "api_auto",
        "source": f"自動観測 ({', '.join(active)})",
        "queries": entries,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False, width=100)
    print(f"保存しました: {out_path}")


if __name__ == "__main__":
    main()
