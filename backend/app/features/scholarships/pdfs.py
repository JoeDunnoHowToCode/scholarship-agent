"""補抓學程的 PDF（ADR-044）：截止日或文件清單有缺的學程，從它的頁面挑一份申請說明 PDF 抓下來。

用法：uv run python -m app.features.scholarships.pdfs [--max-cost NT$]
抓完再跑 extract：快照變了，那些學程會自動重抽，PDF 照 ADR-037 轉錄。
"""

import argparse
import io
import sys
from datetime import UTC, datetime
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.fetch.base import BlockedError, Fetcher
from app.core.fetch.http import HttpFetcher
from app.core.fetch.text import content_hash, decode_snapshot, pdf_to_text
from app.core.llm.gemini import GeminiLLM, LLMError, MissingApiKeyError
from app.features.scholarships.extract import documents
from app.features.scholarships.models import Scholarship
from app.features.sources.fetch import SNAPSHOT_DIR, report, save_raw
from app.features.sources.links import Link
from app.features.sources.models import Snapshot, Source
from app.features.sources.pick import pick_links
from app.shared.db import SessionLocal
from app.shared.settings import settings

MAX_PAGES = 30  # 超過 30 頁的 PDF 不讀（docs/day-03.md「Claude 自行決定」第 25 點）


def missing_data(scholarship: Scholarship) -> bool:
    """截止日或文件清單有缺（ADR-044 的「缺資料」）。"""
    extracted = scholarship.extracted
    return extracted.get("deadline") is None or not extracted.get("requirements")


def pdf_links(session: Session, source: Source) -> list[Link]:
    """這個來源已抓頁面上的所有 PDF 連結（不限同一個網站：大學常把說明放在主網域）。"""
    found: dict[str, Link] = {}
    for snapshot in documents(session, source):
        if snapshot.file_path.endswith(".pdf"):
            continue
        html = decode_snapshot((SNAPSHOT_DIR / snapshot.file_path).read_bytes())
        for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            url = urldefrag(urljoin(snapshot.url, str(anchor["href"]))).url
            parts = urlsplit(url)
            if parts.scheme in ("http", "https") and parts.path.lower().endswith(".pdf"):
                found.setdefault(url, Link(url, " ".join(anchor.get_text().split())))
    return list(found.values())


def fetch_pdf(session: Session, fetcher: Fetcher, source: Source, url: str) -> None:
    """抓一份 PDF，頁數沒超過上限就存成這個來源的快照。"""
    try:
        result = fetcher.get(url)
    except BlockedError as error:
        report("blocked", error.reason, url)  # PDF 被擋只跳過這份，不把整個學程標成需人工
        return
    except httpx.HTTPError as error:
        report("error", type(error).__name__, url)
        return
    if "pdf" not in result.content_type:
        report("skip", "不是 PDF", url)
        return
    pages = len(PdfReader(io.BytesIO(result.content)).pages)
    if pages > MAX_PAGES:
        report("skip", f"{pages} 頁", url)
        return
    digest = content_hash(pdf_to_text(result.content))
    session.add(
        Snapshot(
            source_id=source.id,
            url=result.url,
            fetched_at=datetime.now(UTC),
            content_hash=digest,
            file_path=save_raw(source, digest, result, is_pdf=True),
            http_status=result.status,
            etag=result.etag,
            last_modified=result.last_modified,
        )
    )
    report("new", f"PDF {pages} 頁", url)


def main() -> None:
    parser = argparse.ArgumentParser(description="缺資料的學程補抓一份申請說明 PDF")
    parser.add_argument("--max-cost", type=float, help="這次執行的 AI 費用上限（新台幣）")
    args = parser.parse_args()
    try:
        llm = GeminiLLM(
            settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute
        )
    except MissingApiKeyError as error:
        sys.exit(str(error))

    fetcher = HttpFetcher(settings.fetch_min_interval_seconds)
    counts = {"checked": 0, "fetched": 0}
    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(Scholarship, Source)
                .join(Source, Scholarship.source_id == Source.id)
                .where(Source.parent_id.is_not(None))
                .order_by(Source.id)
            ).all()
            for scholarship, source in rows:
                has_pdf = any(s.file_path.endswith(".pdf") for s in documents(session, source))
                if not missing_data(scholarship) or has_pdf:
                    continue
                if args.max_cost and llm.cost_usd() * 32 > args.max_cost:
                    print(f"已超過這次的費用上限 NT${args.max_cost}，停下")
                    break
                links = pdf_links(session, source)
                counts["checked"] += 1
                if not links:
                    continue
                print(f"== {source.id} {source.name}")
                try:
                    picked = pick_links(llm, source.name, source.url, links)[:1]
                except LLMError as error:
                    report("error", "挑 PDF 失敗", str(error))
                    continue
                for url in picked:
                    fetch_pdf(session, fetcher, source, url)
                    counts["fetched"] += 1
                session.commit()
    finally:
        fetcher.close()
    print(f"缺資料的學程 {counts['checked']} 個，嘗試抓 PDF {counts['fetched']} 份")
    print(llm.usage_line())


if __name__ == "__main__":
    main()
