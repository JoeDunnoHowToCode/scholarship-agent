"""EACEA Erasmus Mundus 目錄頁解析（ADR-031：固定格式的清單頁 → 學程名稱與網址）。"""

from dataclasses import dataclass

from bs4 import BeautifulSoup


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
        if link is None:
            # 少數卡片標題沒有連結，官網網址寫在說明文字裡
            description = card.find("div", class_="ecl-content-block__description")
            link = description.find("a", href=True) if description else None
        if link is None:
            continue
        entries.append(CatalogueEntry(name=name, url=str(link["href"])))
    return entries
