"""找出重複的獎學金（ADR-048）：只用規則比對網址、提供者和名稱，不花 AI 費用。

用法：uv run python -m app.features.scholarships.dedup
"""

import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select

from app.features.scholarships.models import MAIN_KEY, Scholarship, ScholarshipStatus
from app.features.search.similar import similar_pairs
from app.shared.db import SessionLocal


def normalize_url(url: str) -> str:
    """把寫法不同、其實同一頁的網址變成同一個字串。

    例如 "HTTP://www.Example.eu/Apply/#deadlines" → "https://example.eu/Apply"。
    路徑的大小寫和查詢字串（? 後面）保留，因為它們可能指向不同的頁面。
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme == "http":
        scheme = "https"  # 同一個網站通常 http 會轉到 https
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")  # 結尾的 / 有沒有都是同一頁
    return urlunsplit((scheme, host, path, parts.query, ""))  # 最後的空字串：丟掉 # 錨點


def normalize_name(text: str) -> str:
    """名稱只留文字和數字，方便比對。

    全形轉半形（NFKC）、不分大小寫（casefold），再去掉空白、標點和符號（例如「–」）。
    中文字也算文字，會保留。
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(char for char in text if char.isalnum())


@dataclass(frozen=True)
class Candidate:
    """要比對的一筆獎學金：只放比對需要的欄位。"""

    id: int
    provider: str | None
    name: str
    official_url: str | None
    main: bool = True  # 是不是頁面的主角（ADR-108）；同一頁的其他獎學金網址和主角一樣，不拿網址比對
    active: bool = True  # 使用中（不是封存）；同一組裡優先當代表（總檢查 A4）


def find_duplicates(items: list[Candidate]) -> dict[int, int]:
    """回傳 {重複的 id: 代表的 id}；沒有重複的不會出現。

    兩筆算重複：官方網址相同，或「提供者＋名稱」都相同。
    只比名稱不夠：很多不同學程都叫 "Erasmus Mundus Scholarships"。
    重複會傳遞（A 像 B、B 像 C，三筆就是同一組），每組由使用中的優先、再由最小的 id 代表。
    """
    # 併查集（union-find）：每筆記住自己的「上一層」，一路往上找到的就是組長
    parent = {item.id: item.id for item in items}
    active = {item.id: item.active for item in items}

    def rank(item_id: int) -> tuple[bool, int]:
        # 排越前面越適合當組長：使用中的（not True = False）排在封存的前面，再比 id
        return not active[item_id], item_id

    def leader(item_id: int) -> int:
        while parent[item_id] != item_id:
            item_id = parent[item_id]
        return item_id

    first_with_key: dict[tuple[str, ...], int] = {}  # 比對鍵 → 第一個有這個鍵的 id
    for item in items:
        keys: list[tuple[str, ...]] = []
        if item.official_url and item.main:
            keys.append(("url", normalize_url(item.official_url)))
        if item.provider:
            keys.append(("provider+name", normalize_name(item.provider), normalize_name(item.name)))
        for key in keys:
            if key not in first_with_key:
                first_with_key[key] = item.id
                continue
            # 合併兩組：排在後面的組長改掛到排在前面的組長底下（使用中的優先，再比 id）
            winner, loser = sorted((leader(first_with_key[key]), leader(item.id)), key=rank)
            parent[loser] = winner
    return {item.id: leader(item.id) for item in items if leader(item.id) != item.id}


SIMILAR_THRESHOLD = 0.95  # 向量相似度門檻（第 5 天，實測後再調）


def main() -> None:
    """依規則標記重複（ADR-048）：重複的那筆的 duplicate_of 指向代表的那筆。"""
    with SessionLocal() as session, session.begin():
        rows = session.scalars(select(Scholarship).where(Scholarship.source_id.is_not(None))).all()
        found = find_duplicates(
            [
                Candidate(r.id, r.provider, r.name, r.official_url, r.key == MAIN_KEY, r.status == ScholarshipStatus.ACTIVE)
                for r in rows
            ]
        )
        for row in rows:
            row.duplicate_of = found.get(row.id)
        # 第 5 天：向量相似度的「可能重複」只列出、不自動標記（docs/day-05.md「Claude 自行決定」第 16 點）
        vectors = {r.id: list(r.embedding) for r in rows if r.embedding is not None and r.id not in found}
        names = {r.id: r.name for r in rows}
        pairs = similar_pairs(vectors, SIMILAR_THRESHOLD)
    print(f"{len(rows)} 筆獎學金，其中 {len(found)} 筆是重複：{found or '無'}")
    print(f"向量相似度 ≥ {SIMILAR_THRESHOLD} 的可能重複：{len(pairs)} 對")
    for a, b, similarity in pairs[:20]:
        print(f"  {similarity:.3f}  {a} {names[a][:40]}  ↔  {b} {names[b][:40]}")


if __name__ == "__main__":
    main()
