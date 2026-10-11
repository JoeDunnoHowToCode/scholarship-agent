"""EACEA Erasmus Mundus 目錄頁解析（ADR-031：固定格式的清單頁 → 學程名稱與網址）。"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

# 歐盟的專案介紹頁：每張卡片都可能附上，但它不是學程官網
PROJECT_PAGE_HOST = "erasmus-plus.ec.europa.eu"


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
