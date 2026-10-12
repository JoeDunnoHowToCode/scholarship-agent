"""PDF 轉錄（ADR-037）：Gemini 讀 PDF 原檔轉成保留表格的 Markdown，pdfplumber 原文當核對基準。

用法：uv run python -m app.features.documents.transcribe <PDF 快照檔路徑>
"""

import argparse
import io
import json
import sys
from pathlib import Path

from pypdf import PdfReader as PypdfReader
from pypdf import PdfWriter

from app.core.fetch.text import pdf_to_text
from app.core.llm.base import PdfReader
from app.features.documents.checks import unverified_numbers

PROMPT_VERSION = "transcribe-1"  # 改提示詞就要改版本號，舊的轉錄稿會自動重做
PAGES_PER_BATCH = 10  # 一次送 10 頁，避免輸出太長被截斷

PROMPT = """把這份 PDF 逐字轉錄成 Markdown：
- 不要摘要、不要改字、不要補字；看不清楚的字照原樣寫
- 保留原本的編號（壹、一、(一)、1.、(1)），每個編號另起一行
- 表格轉成 Markdown 表格，合併儲存格的內容在每一格重複寫出
- 頁首、頁尾、頁碼不要寫
只輸出轉錄稿本身。
"""


def split_pdf(pdf: bytes, pages_per_batch: int) -> list[bytes]:
    """把 PDF 每 N 頁切成一個小 PDF。"""
    reader = PypdfReader(io.BytesIO(pdf))
    batches = []
    for start in range(0, len(reader.pages), pages_per_batch):
        writer = PdfWriter()
        for page in reader.pages[start : start + pages_per_batch]:
            writer.add_page(page)
        buffer = io.BytesIO()
        writer.write(buffer)
        batches.append(buffer.getvalue())
    return batches


def cache_path(pdf_path: Path) -> Path:
    # 轉錄稿存在快照旁邊；檔名含提示詞版本，改提示詞就會重轉
    return pdf_path.with_name(f"{pdf_path.name}.{PROMPT_VERSION}.json")


def transcribe(reader: PdfReader, pdf_path: Path) -> tuple[str, list[str]]:
    """回傳（轉錄稿, 在同一批原文裡找不到的數字）。有快取就不呼叫模型。"""
    cache = cache_path(pdf_path)
    batches = split_pdf(pdf_path.read_bytes(), PAGES_PER_BATCH)
    if cache.exists():
        texts: list[str] = json.loads(cache.read_text(encoding="utf-8"))
    else:
        texts = [reader.read_pdf(PROMPT, batch) for batch in batches]
        cache.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    # 每一批只和同一批頁面的原文比，常見的小數字比較不會碰巧在別頁出現而漏抓
    unverified: list[str] = []
    for text, batch in zip(texts, batches, strict=True):
        for number in unverified_numbers(text, pdf_to_text(batch)):
            if number not in unverified:
                unverified.append(number)
    return "\n\n".join(texts), unverified


def main() -> None:
    from app.core.llm.gemini import GeminiLLM, MissingApiKeyError
    from app.shared.settings import settings

    parser = argparse.ArgumentParser(description="把 PDF 快照轉錄成 Markdown 並核對數字")
    parser.add_argument("path", type=Path, help="PDF 快照檔")
    args = parser.parse_args()
    try:
        llm = GeminiLLM(
            settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute
        )
    except MissingApiKeyError as error:
        sys.exit(str(error))
    transcript, unverified = transcribe(llm, args.path)
    batches = len(split_pdf(args.path.read_bytes(), PAGES_PER_BATCH))
    print(f"批次：{batches}，轉錄稿 {len(transcript):,} 字元，存在 {cache_path(args.path)}")
    print(f"原文裡找不到的數字：{unverified or '無'}")
    print(llm.usage_line())


if __name__ == "__main__":
    main()
