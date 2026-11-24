"""AIO定点観測スクリプト共通処理。"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# 観測対象の会社。環境変数 AIO_CLIENT で切り替える。
#
#   未指定            … ARIGATO Living（2026-07からの既存データ。パスは変えない）
#   AIO_CLIENT=aimy  … clients/aimy/config.yml と data/aimy/ を使う
#
# 会社ごとにデータディレクトリを分けるので、別の会社のデータが混ざらない。
CLIENT = (os.getenv("AIO_CLIENT") or "").strip()

if CLIENT:
    CONFIG_PATH = ROOT / "clients" / CLIENT / "config.yml"
    DATA_DIR = ROOT / "data" / CLIENT
    REPORTS_DIR = ROOT / "reports" / CLIENT
else:
    CONFIG_PATH = ROOT / "config" / "config.yml"
    DATA_DIR = ROOT / "data"
    REPORTS_DIR = ROOT / "reports"

OBS_DIR = DATA_DIR / "observations"
ACTIONS_PATH = DATA_DIR / "actions.yml"
NOTE_ARTICLES_PATH = DATA_DIR / "note_articles.yml"

POSITION_SYMBOLS = {
    "featured": "◎",
    "listed": "○",
    "cited_only": "△",
    "none": "×",
    # 未観測の「－」とは別の記号にする。
    # 「聞き返された（候補が出なかった）」と「観測していない」は原因が違う。
    "no_answer": "？",
}
POSITION_LABELS = {
    "featured": "◎ 筆頭で紹介",
    "listed": "○ リスト内で言及",
    "cited_only": "△ 引用リンクのみ",
    "none": "× 言及なし",
    "no_answer": "－ 回答なし（条件を聞き返された）",
}

# 候補を挙げずに条件を聞き返してくる回答に出てくる言い回し。
# ChatGPTは「神楽坂 撮影スタジオ」のような短いキーワードだと、
# 候補を出さずに「用途・日時・予算を教えてください」と聞き返すことがある。
# これを「言及なし(×)」に混ぜると、候補に挙げてもらえなかったのと
# 区別できなくなり、出現率を実態より低く見せてしまう。
ASK_BACK_PHRASES = (
    "教えてください",
    "お知らせください",
    "お探しでしょうか",
    "いただければ",
    "ご希望を",
    "条件を教え",
    # 英語で聞き返してくることもある。指名クエリで
    # 「ARIGATO Livingとは何を指しますか？」と聞き返す例が出ている。
    # このとき質問文のブランド名が回答に残るため、
    # 判定しないと「筆頭で紹介(◎)」として数えてしまう。
    "what would you like",
    "could you tell me",
    "could you clarify",
    "let me know",
    "not sure what you",
)

# 聞き返しと判定する上限の文字数。
#
# 過去25週・全1,136件で検証した結果、
#   実際に聞き返しだった回答 … 218〜1,222文字（70件、すべてChatGPT）
#   候補を挙げている回答     … 1,591文字以上（7件、Gemini 6・Google AIモード 1）
# と間に差があったため、その間に閾値を置いた。
# 長い回答が引っかかっていたのは「ご希望をお知らせください」のような
# 回答の最後の一言で、本文では候補を挙げていたもの。
ASK_BACK_MAX_CHARS = 1400


def is_ask_back(text: str, citations: list[str] | None) -> bool:
    """候補を挙げず、条件を聞き返しただけの回答かどうか。

    3つすべてを満たすときに真: 引用元が1件もない／聞き返しの言い回しを含む／
    短い。実際に候補を挙げた回答はWeb検索をしているので引用元が付き、
    付かない場合でも候補の説明があるぶん長くなる。
    """
    if citations:
        return False
    body = text or ""
    if len(body) >= ASK_BACK_MAX_CHARS:
        return False
    low = body.lower()
    return any(p in body or p in low for p in ASK_BACK_PHRASES)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"設定ファイルがありません: {CONFIG_PATH}\n"
            + (f"会社ID '{CLIENT}' の設定を clients/{CLIENT}/config.yml に作ってください。"
               if CLIENT else "config/config.yml を確認してください。")
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_observations() -> list[dict]:
    """data/observations/*.yml を日付順に読み込む。

    `*-partial.yml` は動作確認用の部分実行の結果なので除外する。
    一部の質問しか含まれておらず、週次の集計に混ぜると欠測と区別できなくなる。
    """
    files = [f for f in sorted(OBS_DIR.glob("*.yml")) if not f.name.endswith("-partial.yml")]
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


def list_rank(text: str, config: dict) -> tuple[int | None, int]:
    """回答が一覧形式のとき、自社が何番目に挙がっているかを返す。

    戻り値は (順位, 一覧の項目数)。一覧として読めない、または自社が
    一覧に入っていない場合は (None, 項目数) を返す。

    AIは候補を箇条書きや番号付きで並べることが多い。その並び順は
    「何番目に推されたか」そのものなので、◎○△× とは別に記録する。
    """
    items: list[str] = []
    current: list[str] = []
    # 「1.」「1)」「- 」「・」「**名前**」のような行を項目の先頭とみなす
    head = re.compile(r"^\s*(?:\d+[.)、]|[-*・▪]|#{2,6}\s|\*\*[^*]+\*\*\s*[:：]?)")
    for line in (text or "").splitlines():
        if head.match(line):
            if current:
                items.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        items.append("\n".join(current))

    if len(items) < 2:  # 一覧とは呼べない
        return None, 0
    for i, item in enumerate(items, start=1):
        if find_brand_mention(item, config):
            return i, len(items)
    return None, len(items)


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
