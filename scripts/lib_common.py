"""AIO定点観測スクリプト共通処理。"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "config.yml"
OBS_DIR = ROOT / "data" / "observations"
ACTIONS_PATH = ROOT / "data" / "actions.yml"
REPORTS_DIR = ROOT / "reports"

POSITION_SYMBOLS = {
    "featured": "◎",
    "listed": "○",
    "cited_only": "△",
    "none": "×",
}
POSITION_LABELS = {
    "featured": "◎ 筆頭で紹介",
    "listed": "○ リスト内で言及",
    "cited_only": "△ 引用リンクのみ",
    "none": "× 言及なし",
}


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_observations() -> list[dict]:
    """data/observations/*.yml を日付順に読み込む。"""
    files = sorted(OBS_DIR.glob("*.yml"))
    observations = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and data.get("queries"):
            data["_file"] = path.name
            observations.append(data)
    observations.sort(key=lambda o: str(o.get("date", "")))
    return observations


def load_actions() -> list[dict]:
    if not ACTIONS_PATH.exists():
        return []
    with open(ACTIONS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    actions = [a for a in data.get("actions", []) if a.get("date")]
    actions.sort(key=lambda a: str(a["date"]))
    return actions


def normalize(text: str) -> str:
    """表記ゆれ吸収のための正規化（小文字化・空白除去）。"""
    return re.sub(r"[\s　]+", "", (text or "").lower())


def find_brand_mention(text: str, config: dict) -> bool:
    norm = normalize(text)
    return any(normalize(alias) in norm for alias in config["brand"]["aliases"])


def brand_position(text: str, config: dict) -> str:
    """自動観測用のポジション推定。

    回答テキストの前半25%以内に登場すれば featured、
    それ以外で登場すれば listed とみなす（手動観測時は目視で上書き）。
    """
    if not find_brand_mention(text, config):
        return "none"
    norm = normalize(text)
    for alias in config["brand"]["aliases"]:
        idx = norm.find(normalize(alias))
        if idx >= 0 and idx <= len(norm) * 0.25:
            return "featured"
    return "listed"


def classify_citations(urls: list[str], config: dict) -> dict:
    own = config["brand"].get("own_domains", [])
    related = config["brand"].get("related_domains", [])
    return {
        "own_site_cited": any(d in u for u in urls for d in own),
        "related_cited": any(d in u for u in urls for d in related),
    }


def find_competitors(text: str, config: dict) -> list[str]:
    norm = normalize(text)
    found = []
    for comp in config.get("competitors", []):
        names = [comp["name"], *comp.get("aliases", [])]
        if any(normalize(n) in norm for n in names):
            found.append(comp["name"])
    return found
