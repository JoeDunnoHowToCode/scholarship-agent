"""抓取指令（第 2 天）：抓所有該抓的來源，內容變了才存快照（ADR-019、027、028、029）。

用法：uv run python -m app.features.sources.fetch [--limit N] [--unchecked] [--source ID] [--repick] [--shard K/N]

不翻頁的網頁來源（學程網站、Chevening）首頁是新的或變了，就請 AI 從首頁連結挑出申請頁一起抓（ADR-031）。
"""

import argparse
import sys
import zlib
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.fetch.base import BlockedError, Fetcher, FetchResult
from app.core.fetch.http import HttpFetcher
from app.core.fetch.text import content_hash, html_to_text, pdf_to_text
from app.core.llm.gemini import GeminiLLM, LLMError, MissingApiKeyError
from app.features.sources.links import Link, candidate_links
from app.features.sources.models import FetchMethod, Snapshot, Source, SourceStatus
from app.features.sources.pagination import missing_pages_warning, pagination_urls
from app.shared.db import SessionLocal
from app.shared.settings import settings

# 原始檔放在 backend/data/snapshots/（ADR-019，不進 git）
SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "data" / "snapshots"
MAX_PAGES = 50  # 翻頁最多 50 頁，避免無限翻下去

# 挑連結的函式：(學程名稱, 首頁網址, 候選連結) → 挑中的網址
LinkPicker = Callable[[str, str, list[Link]], list[str]]


def report(label: str, detail: str, target: str) -> None:
    print(f"{datetime.now(UTC):%H:%M:%S}  {label:<9}  {detail:<14}  {target}")


def decode_html(result: FetchResult) -> str:
    # 依 Content-Type 標頭的 charset 解碼，沒寫就當 UTF-8
    header = Message()
    header["content-type"] = result.content_type
    return result.content.decode(header.get_content_charset() or "utf-8", "replace")


def save_raw(source: Source, digest: str, result: FetchResult) -> str:
    """把原始檔存進 data/snapshots/<來源 id>/，回傳相對路徑。"""
    extension = "pdf" if source.fetch_method == FetchMethod.PDF else "html"
    relative = Path(str(source.id)) / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{digest[:12]}.{extension}"
    path = SNAPSHOT_DIR / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(result.content)
    return str(relative)


def latest_snapshot(session: Session, source_id: int, url: str) -> Snapshot | None:
    return session.scalars(
        select(Snapshot)
        .where(Snapshot.source_id == source_id, Snapshot.url == url)
        .order_by(Snapshot.fetched_at.desc())
        .limit(1)
    ).first()


def fetch_source(
    session: Session,
    fetcher: Fetcher,
    source: Source,
    picker: LinkPicker | None = None,
    *,
    repick: bool = False,
) -> None:
    source.last_checked_at = datetime.now(UTC)
    # 要檢查的網址：來源網址、以前快照過的頁面（翻頁遇到 304 也能繼續）、這次找到的翻頁連結
    known = session.scalars(
        select(Snapshot.url).where(Snapshot.source_id == source.id).distinct()
    ).all()
    queue = [source.url, *(url for url in known if url != source.url)]
    seen: set[str] = set()
    checked = 0  # 這次成功檢查到的頁數（200 或 304），漏抓警示用
    while queue and len(seen) < MAX_PAGES:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        latest = latest_snapshot(session, source.id, url)
        try:
            result = fetcher.get(
                url,
                etag=latest.etag if latest else None,
                last_modified=latest.last_modified if latest else None,
            )
        except BlockedError as error:
            source.manual_reason = error.reason  # 界線三：標記需人工，之後跳過
            report("blocked", error.reason, url)
            return
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            report("error", str(status), url)
            if status >= 500:
                return  # 伺服器出錯：這次跳過這個來源，下次再試
            continue  # 例如某一頁消失了（404）：繼續檢查下一頁
        except httpx.HTTPError as error:
            report("error", type(error).__name__, url)
            return  # 網路錯誤：這次跳過這個來源，下次再試

        checked += 1
        if result.status == 304:
            report("unchanged", "304", url)
            continue
        html = decode_html(result) if source.fetch_method == FetchMethod.HTML else ""
        text = pdf_to_text(result.content) if source.fetch_method == FetchMethod.PDF else html_to_text(html)
        digest = content_hash(text)
        changed = not (latest and latest.content_hash == digest)
        if not changed:
            report("unchanged", digest[:12], url)
        else:
            session.add(
                Snapshot(
                    source_id=source.id,
                    url=url,
                    fetched_at=datetime.now(UTC),
                    content_hash=digest,
                    file_path=save_raw(source, digest, result),
                    http_status=result.status,
                    etag=result.etag,
                    last_modified=result.last_modified,
                )
            )
            report("changed" if latest else "new", digest[:12], url)
        # 首頁是新的或變了（或指定 --repick）：請 AI 挑申請頁，加進這次要抓的佇列
        # 目錄這類翻頁來源不挑；學程網站與 Chevening 這類單頁來源都挑
        if (changed or repick) and picker and not source.follow_pagination and url == source.url and html:
            for picked in picker(source.name, result.url, candidate_links(html, result.url)):
                report("picked", "AI 挑連結", picked)
                if picked not in seen:
                    queue.append(picked)
        if source.follow_pagination and html:
            links = pagination_urls(
                html, result.url, page_zero_is_first=source.page_zero_is_first
            )
            queue.extend(link for link in links if link not in seen)

    # 走到這裡代表這次完整跑完（中途被擋或出錯會提早 return，不比較也不更新）
    if source.follow_pagination:
        warning = missing_pages_warning(source.last_page_count, checked)
        if warning:
            report("warning", "漏抓警示", warning)
        source.last_page_count = checked  # 甲：警示後也照常更新，所以只會警示一次


def in_shard(url: str, shard: str) -> bool:
    """依網站分份：同一個網站一定在同一份，所以限速規則（ADR-028）在每個程序裡照樣成立。"""
    index, total = (int(part) for part in shard.split("/"))
    return zlib.crc32((urlsplit(url).hostname or "").encode()) % total == index


def make_picker() -> tuple[LinkPicker | None, GeminiLLM | None]:
    from app.features.sources.pick import pick_links  # 只有挑連結時才需要

    try:
        llm = GeminiLLM(settings.llm_model, settings.google_api_key)
    except MissingApiKeyError as error:
        print(f"{error}；這次不挑連結，只抓首頁", file=sys.stderr)
        return None, None

    def picker(name: str, url: str, links: list[Link]) -> list[str]:
        try:
            return pick_links(llm, name, url, links)
        except LLMError as error:  # 挑連結失敗不影響首頁的快照，下次首頁變了會再挑
            report("error", "挑連結失敗", f"{url} {type(error).__name__}: {error}")
            return []

    return picker, llm


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取來源、存快照")
    parser.add_argument("--limit", type=int, help="最多抓幾個來源")
    parser.add_argument("--unchecked", action="store_true", help="只抓從來沒檢查過的來源")
    parser.add_argument("--source", type=int, help="只抓這個來源 id")
    parser.add_argument("--repick", action="store_true", help="首頁沒變也重新請 AI 挑連結")
    parser.add_argument(
        "--shard", help="K/N：只抓第 K 份（共 N 份），讓 N 個程序平行抓不同網站，例如 0/4"
    )
    args = parser.parse_args()

    query = (
        select(Source)
        .where(
            Source.enabled.is_(True),
            Source.status == SourceStatus.APPROVED,
            Source.manual_reason.is_(None),
        )
        .order_by(Source.id)
        .limit(args.limit)
    )
    if args.unchecked:
        query = query.where(Source.last_checked_at.is_(None))
    if args.source:
        query = query.where(Source.id == args.source)

    picker, llm = make_picker()
    fetcher = HttpFetcher(settings.fetch_min_interval_seconds)
    try:
        with SessionLocal() as session:
            for source in session.scalars(query).all():
                if args.shard and not in_shard(source.url, args.shard):
                    continue
                print(f"== {source.id} {source.name}")
                fetch_source(session, fetcher, source, picker, repick=args.repick)
                session.commit()  # 每個來源各自一個交易：一個出錯不影響其他已存的快照
    finally:
        fetcher.close()
        if llm:
            print(llm.usage_line())


if __name__ == "__main__":
    main()
