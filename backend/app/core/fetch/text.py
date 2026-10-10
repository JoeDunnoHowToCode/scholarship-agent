"""把網頁和 PDF 轉成文字，並算出內容雜湊（ADR-027）。"""

from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n")
