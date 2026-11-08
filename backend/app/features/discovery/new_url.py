"""找新網址（ADR-080）：抓不到的來源，由 agent 找現在的官方網址；確認是同一個學程才換。"""

import re

# 主辦單位名稱裡太常見、不能用來辨認的字
GENERIC = frozenset({
    "the", "of", "and", "for", "in", "de", "do", "da", "university", "universities", "universidade",
    "universidad", "universita", "universite", "consortium", "european", "commission", "erasmus", "mundus",
    "programme", "program", "master", "masters", "joint", "school", "institute", "college",
})
MIN_NAME = 4  # 名稱（或縮寫）至少幾個字元才拿來比對，太短容易碰巧出現


def same_programme(names: list[str], provider: str | None, page_text: str) -> bool:
    """新網頁是不是同一個學程：找得到名稱或縮寫，而且（主辦單位有特別的字時）找得到其中一個。

    不分大小寫、忽略標點（「Claude 自行決定」第 12 點）。
    """
    page = f" {_norm(page_text)} "
    candidates = [_norm(name) for name in names]
    # 獎學金名稱常寫成「Erasmus Mundus Scholarship – 縮寫」：破折號後面那段也拿來比
    candidates += [_norm(re.split(r"\s[–—-]\s", name)[-1]) for name in names if re.search(r"\s[–—-]\s", name)]
    if not any(len(c) >= MIN_NAME and f" {c} " in page for c in candidates):
        return False
    distinctive = [w for w in _norm(provider or "").split() if len(w) >= MIN_NAME and w not in GENERIC]
    # 主辦單位只有通用的字（例如 European Commission）時，只看名稱
    return not distinctive or any(f" {w} " in page for w in distinctive)


def _norm(text: str) -> str:
    """小寫、標點和底線都換成空白、空白合成一格。"""
    return " ".join(re.sub(r"[\W_]+", " ", text.lower()).split())
