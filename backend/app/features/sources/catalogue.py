"""EACEA Erasmus Mundus 目錄頁解析（ADR-031：固定格式的清單頁 → 學程名稱與網址）。

用法：uv run python -m app.features.sources.catalogue（先跑 fetch 抓下目錄）
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.features.sources.fetch import SNAPSHOT_DIR, latest_snapshot
from app.features.sources.models import Discovery, Snapshot, Source, SourceKind
from app.features.sources.seed import SEEDS
from app.shared.db import SessionLocal

# 歐盟的專案介紹頁：每張卡片都可能附上，但它不是學程官網
PROJECT_PAGE_HOST = "erasmus-plus.ec.europa.eu"
CATALOGUE_URL = SEEDS[0]["url"]  # 種子裡的 EACEA 目錄


@dataclass(frozen=True)
class CatalogueEntry:
    """目錄裡的一個學程：名稱與官網網址。"""

    name: str
    url: str


def parse_catalogue(html: str) -> list[CatalogueEntry]:
    """每張 <article class="ecl-card"> 是一個學程，依頁面順序取出名稱與網址。"""
    entries: list[CatalogueEntry] = []
    for card in BeautifulSoup(html, "html.parser").find_all("article", class_="ecl-card"):
        title = card.find("div", class_="ecl-content-block__title")
        if title is None:
            continue
        # get_text 會連換行一起取出；split + join 把連續空白收成一格
        name = " ".join(title.get_text().split())
        link = title.find("a", href=True)
        url = str(link["href"]) if link else _homepage_in_description(card)
        if url is None:
            continue
        entries.append(CatalogueEntry(name=name, url=url))
    return entries


def catalogue_total(html: str) -> int | None:
    """讀標題「Projects(218)」裡的學程總數，之後可拿來檢查漏抓；找不到就回傳 None。"""
    for heading in BeautifulSoup(html, "html.parser").find_all("h2"):
        # \s* 允許括號前後有空白，例如 "Projects (218)"
        match = re.fullmatch(r"Projects\s*\(\s*(\d+)\s*\)", heading.get_text().strip())
        if match:
            return int(match.group(1))
    return None


def _homepage_in_description(card: Tag) -> str | None:
    """少數卡片標題沒有連結，官網網址寫在說明文字裡；跳過歐盟專案頁，取第一個其他連結。"""
    description = card.find("div", class_="ecl-content-block__description")
    if description is None:
        return None
    for link in description.find_all("a", href=True):
        url = str(link["href"])
        if urlsplit(url).hostname != PROJECT_PAGE_HOST:
            return url
    return None


def import_programmes(session: Session) -> None:
    """讀 EACEA 目錄每一頁最新的快照，把學程寫成子來源（以網址 upsert，重跑不會重複）。"""
    catalogue = session.scalars(select(Source).where(Source.url == CATALOGUE_URL)).one()
    urls = session.scalars(
        select(Snapshot.url).where(Snapshot.source_id == catalogue.id).distinct()
    ).all()
    entries: dict[str, CatalogueEntry] = {}
    total = None
    for url in urls:
        latest = latest_snapshot(session, catalogue.id, url)
        if latest is None:
            continue
        html = (SNAPSHOT_DIR / latest.file_path).read_text(encoding="utf-8")
        total = total or catalogue_total(html)
        for entry in parse_catalogue(html):
            entries.setdefault(entry.url, entry)

    for entry in entries.values():
        statement = (
            insert(Source)
            .values(
                name=entry.name,
                url=entry.url,
                kind=SourceKind.UNIVERSITY,  # Erasmus Mundus 學程由多所大學合辦
                parent_id=catalogue.id,
                discovery=Discovery.CATALOGUE,
            )
            # 已存在就只更新名稱與上層來源，不動抓取狀態（例如需人工的原因）
            .on_conflict_do_update(
                index_elements=[Source.url],
                set_={"name": entry.name, "parent_id": catalogue.id},
            )
        )
        session.execute(statement)
    print(f"解析出 {len(entries)} 個學程（{len(urls)} 頁）；頁面寫的總數：{total}")
    if total != len(entries):
        # ADR-031：EACEA 改版時要能發現解析器壞掉
        print(f"warning  解析數和頁面總數不同，解析器可能需要修正：{len(entries)} ≠ {total}")


def main() -> None:
    with SessionLocal() as session, session.begin():
        import_programmes(session)


if __name__ == "__main__":
    main()
