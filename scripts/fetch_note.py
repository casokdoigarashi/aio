#!/usr/bin/env python3
"""note の公開記事一覧を取得して data/note_articles.yml に保存する。

noteの公開APIから記事のタイトルと公開日を取得し、
AI検索の観測データと突き合わせられる形で保存する。

使い方:
  python scripts/fetch_note.py              # config.yml の note.username を使う
  python scripts/fetch_note.py casokdo_note # ユーザー名を指定
"""
from __future__ import annotations

import sys

import requests
import yaml

from lib_common import ROOT, load_config

API = "https://note.com/api/v2/creators/{user}/contents"
TIMEOUT = 30
OUT_PATH = ROOT / "data" / "note_articles.yml"


def _pick(d: dict, *names, default=""):
    """APIのフィールド名の揺れ（camelCase / snake_case）を吸収する。"""
    for n in names:
        if d.get(n):
            return d[n]
    return default


def fetch_articles(user: str) -> list[dict]:
    articles, page = [], 1
    while True:
        resp = requests.get(
            API.format(user=user),
            params={"kind": "note", "page": page},
            headers={"User-Agent": "aio-observation/1.0"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        contents = data.get("contents", [])
        if not contents:
            break
        for c in contents:
            published = str(_pick(c, "publishAt", "publish_at", "createdAt"))[:10]
            articles.append(
                {
                    "date": published,
                    "title": _pick(c, "name", "title"),
                    "url": _pick(c, "noteUrl", "note_url"),
                }
            )
        if data.get("isLastPage") or page >= 20:  # 念のため上限
            break
        page += 1
    articles.sort(key=lambda a: a["date"])
    return articles


def main() -> None:
    config = load_config()
    user = sys.argv[1] if len(sys.argv) > 1 else config.get("note", {}).get("username")
    if not user:
        print("noteのユーザー名が未設定です（config.yml の note.username）。スキップします。")
        return

    try:
        articles = fetch_articles(user)
    except Exception as exc:
        # note側の仕様変更や一時的な障害で観測全体を止めない
        detail = ""
        resp = getattr(exc, "response", None)
        if resp is not None:
            detail = f" / {resp.text[:200]}"
        print(f"note記事の取得に失敗しました: {exc}{detail}")
        return

    if not articles:
        print(f"note記事が取得できませんでした（ユーザー名 '{user}' を確認してください）。")
        return

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"username": user, "articles": articles},
            f,
            allow_unicode=True,
            sort_keys=False,
        )
    print(f"note記事 {len(articles)}件を保存しました: {OUT_PATH}")
    for a in articles[-5:]:
        print(f"  - {a['date']} {a['title'][:40]}")


if __name__ == "__main__":
    main()
