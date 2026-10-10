"""把網頁和 PDF 轉成文字，並算出內容雜湊（ADR-027）。"""

import hashlib
import io

import pdfplumber
from bs4 import BeautifulSoup

# 區塊元素：前後換行。其他（span、a、strong…）是行內元素，文字直接接起來，
# 所以被標籤切開的字（例如 <span>202</span><span>7</span>）會接回「2027」
BLOCK_TAGS = [
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4",
    "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
    "table", "td", "th", "tr", "ul",
]


def html_to_text(html: str) -> str:
    """取出頁面上看得到的全部文字（不用正文擷取，避免刪掉關鍵資訊）。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    # 每一行的空白縮成一個，去掉空行
    lines = (" ".join(line.split()) for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line)


def pdf_to_text(data: bytes) -> str:
    """PDF 逐頁取出文字（ADR-027：pdfplumber，實測能抽出教育部簡章的中文）。"""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    lines = (" ".join(line.split()) for line in "\n".join(pages).splitlines())
    return "\n".join(line for line in lines if line)


def content_hash(text: str) -> str:
    """把所有空白（含換行）縮成一個空格後算 SHA-256；只差空白的文字雜湊相同。"""
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
