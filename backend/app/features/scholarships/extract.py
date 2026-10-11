"""抽取指令（第 3 天）：把每個來源最新的快照抽成獎學金、類別與文件清單（ADR-008、031、034、037）。

用法：uv run python -m app.features.scholarships.extract [--source ID] [--limit N]

- 網頁：每頁的可見文字合併後整份抽（ADR-034：一般網頁整頁讀）
- PDF 與很長的網頁：切段 → 第一輪列大綱 → 第二輪逐節抽 → 程式合併
- 最後都經過驗證者，再把獎學金、類別、文件清單在同一個交易裡整批重寫
"""

import argparse
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session, aliased

from app.core.fetch.text import html_to_text, pdf_to_text
from app.core.llm.gemini import GeminiLLM, LLMError, MissingApiKeyError
from app.features.documents.chunking import chunk_html, chunk_transcript, group_sections
from app.features.documents.transcribe import transcribe
from app.features.scholarships import merge, verify
from app.features.scholarships.models import (
    Requirement,
    Scholarship,
    ScholarshipCategory,
    TaiwanEligibility,
)
from app.features.scholarships.schemas import (
    CategoryDraft,
    Outline,
    ScholarshipDraft,
    SectionFacts,
)
from app.features.sources.fetch import SNAPSHOT_DIR, latest_snapshot
from app.features.sources.models import FetchMethod, Snapshot, Source
from app.shared.db import SessionLocal
from app.shared.settings import settings

# 提示詞版本：改了提示詞就要改號碼；和快照雜湊、模型一起決定要不要重抽（ADR-013）
PROMPT_VERSION = "extract-2"
OUTLINE_VERSION = "outline-1"
SECTION_VERSION = "section-1"
# 網頁合併後超過這個長度才切段（docs/day-03.md「Claude 自行決定」第 6 點）
LONG_TEXT_CHARS = 100_000

RULES = """規則：
- 只根據原文填寫；原文沒寫的欄位留空，不要推測
- 原文沒有明確提到台灣籍能不能申請時，taiwan_eligibility 一律填 unclear
- 所有 evidence 欄位都要逐字複製原文的句子，不要改寫、不要翻譯
- 日期換算成 YYYY-MM-DD；民國年加 1911 換成西元年
"""

EXTRACT_PROMPT = """你是留學獎學金資料的抽取助手。下面是同一個獎學金（或學程）網站的頁面文字，
每頁開頭標著網址。請整理成一筆獎學金資料。
{rules}
- 學程本身的獎學金（例如 Erasmus Mundus 獎學金）就是這筆資料的主角
- 只有一種名額時，categories 填一個、名稱用獎學金名稱

原文：
{text}
"""

OUTLINE_PROMPT = """下面是一份留學獎學金簡章的全文。只要列出獎學金名稱、提供單位，
以及所有名額類別的名稱（照原文寫，取最細的一層，例如「北歐國家」「新南向國家甲」）。

全文：
{text}
"""

SECTION_PROMPT = """你是留學獎學金資料的抽取助手。下面是「{name}」簡章的其中一節，
這份簡章的名額類別有：{categories}。
{rules}
- 這一節沒提到的欄位留空（清單留空清單，taiwan_eligibility 與 nationality_scope 填 unclear）
- 只適用某些類別的規則放進 category_facts，applies_to 必須照抄上面的類別名稱；適用所有類別填 ["all"]

這一節：
{text}
"""


def documents(session: Session, source: Source) -> list[Snapshot]:
    """這個來源每個網址最新的快照；內容一樣的頁面只留一份（例如同一頁的不同分頁標籤）。"""
    urls = session.scalars(
        select(Snapshot.url).where(Snapshot.source_id == source.id).distinct()
    ).all()
    # 首頁排第一，其他照網址排序，讓輸入順序固定
    ordered = sorted(urls, key=lambda url: (url != source.url, url))
    latest = [s for url in ordered if (s := latest_snapshot(session, source.id, url))]
    unique: dict[str, Snapshot] = {}
    for snapshot in latest:
        unique.setdefault(snapshot.content_hash, snapshot)
    return list(unique.values())


def extract_web(llm: GeminiLLM, snapshots: list[Snapshot]) -> tuple[ScholarshipDraft, str, dict[str, Any]]:
    """網頁：回傳（初稿, 核對用的原文, 額外紀錄）。"""
    pages = {s.url: (SNAPSHOT_DIR / s.file_path).read_text(encoding="utf-8") for s in snapshots}
    text = "\n\n".join(f"=== 頁面：{url} ===\n{html_to_text(html)}" for url, html in pages.items())
    if len(text) <= LONG_TEXT_CHARS:
        prompt = EXTRACT_PROMPT.format(rules=RULES, text=text)
        return llm.extract(prompt, ScholarshipDraft), text, {"mode": "whole"}
    chunks = [chunk for html in pages.values() for chunk in chunk_html(html)]
    draft, extra = extract_long(llm, text, group_sections(chunks))
    return draft, text, extra


def extract_pdf(llm: GeminiLLM, snapshot: Snapshot) -> tuple[ScholarshipDraft, str, dict[str, Any]]:
    """PDF：Gemini 轉錄（ADR-037）→ 切段 → 兩輪抽取 → 合併；核對用 pdfplumber 原文。"""
    path = SNAPSHOT_DIR / snapshot.file_path
    transcript, unverified = transcribe(llm, path)
    sections = group_sections(chunk_transcript(transcript))
    draft, extra = extract_long(llm, transcript, sections)
    raw = pdf_to_text(path.read_bytes())
    return draft, raw, {**extra, "unverified_numbers": unverified}


def extract_long(
    llm: GeminiLLM, full_text: str, sections: list[str]
) -> tuple[ScholarshipDraft, dict[str, Any]]:
    """長文件兩輪抽取（docs/day-03.md「Claude 自行決定」第 8 點）。"""
    outline = llm.extract(OUTLINE_PROMPT.format(text=full_text), Outline)
    categories = "、".join(outline.category_names) or "（只有一種）"
    facts = [
        llm.extract(
            SECTION_PROMPT.format(name=outline.name, categories=categories, rules=RULES, text=text),
            SectionFacts,
        )
        for text in sections
    ]
    result = merge.merge_sections(outline, facts)
    return result.draft, {
        "mode": "sections",
        "sections": len(sections),
        "conflicts": result.conflicts,
        "warnings": result.warnings,
    }


def save(
    session: Session,
    source: Source,
    draft: ScholarshipDraft,
    extracted: dict[str, Any],
) -> Scholarship:
    """獎學金以 source_id 找同一筆更新；類別與文件清單整批刪掉重寫（同一個交易）。"""
    row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).first()
    if row is None:
        row = Scholarship(source_id=source.id)
        session.add(row)
    row.name = draft.name
    row.name_zh = draft.name_zh
    row.provider = draft.provider
    row.countries = draft.countries
    row.degrees = list(draft.degrees)
    row.fields = draft.fields
    row.coverage = draft.coverage
    row.amount = draft.amount
    row.taiwan_eligibility = TaiwanEligibility(draft.taiwan_eligibility)
    row.taiwan_conditions = draft.taiwan_conditions
    row.language_requirements = draft.language_requirements
    row.other_eligibility = draft.other_eligibility
    row.requires_admission = draft.requires_admission
    row.official_url = source.url
    row.last_verified_at = datetime.now(UTC)
    row.extracted = extracted  # JSONB 整個重新指定
    session.flush()  # 先拿到 id，類別與文件才能指向它

    session.execute(delete(Requirement).where(Requirement.scholarship_id == row.id))
    session.execute(delete(ScholarshipCategory).where(ScholarshipCategory.scholarship_id == row.id))
    categories = [
        ScholarshipCategory(
            scholarship_id=row.id,
            name=c.name,
            quota=c.quota,
            degrees=list(c.degrees),
            countries=c.countries,
            amount=c.amount,
            eligibility=c.eligibility,
        )
        for c in draft.categories
    ]
    session.add_all(categories)
    session.flush()
    for r in draft.requirements:
        category = next((c for c in categories if r.category and merge.same_name(c.name, r.category)), None)
        session.add(
            Requirement(
                scholarship_id=row.id,
                category_id=category.id if category else None,
                doc_type=r.doc_type,
                details=r.details,
                required=r.required,
                count=r.count,
                evidence=r.evidence,
            )
        )
    return row


def extract_source(session: Session, llm: GeminiLLM, source: Source) -> str:
    """抽一個來源，回傳一行摘要；內容和提示詞都沒變就跳過。"""
    snapshots = documents(session, source)
    meta = {
        "snapshots": sorted(s.content_hash for s in snapshots),
        "prompts": [PROMPT_VERSION, OUTLINE_VERSION, SECTION_VERSION, verify.PROMPT_VERSION],
        "model": settings.llm_model,
    }
    existing = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).first()
    if existing and existing.extracted.get("meta") == meta:
        return "unchanged"

    if source.fetch_method == FetchMethod.PDF:
        draft, raw, extra = extract_pdf(llm, snapshots[0])
    else:
        draft, raw, extra = extract_web(llm, snapshots)
    if not draft.categories:
        # ADR-040：每個獎學金至少一筆類別；模型漏填時用整個獎學金的資料補一筆
        only = CategoryDraft(
            name=draft.name, quota=None, degrees=draft.degrees, countries=draft.countries,
            amount=draft.amount, eligibility=None, evidence=None,
        )
        draft = draft.model_copy(update={"categories": [only]})
    status = verify.verify(llm, draft, raw, extra.get("conflicts", []))
    verified = verify.apply_verification(draft, status)
    extracted = {
        **verified.model_dump(mode="json"),
        "verification": status,
        "original_taiwan_eligibility": draft.taiwan_eligibility,
        **extra,
        "meta": meta,
    }
    save(session, source, verified, extracted)
    checks = " ".join(f"{field}={value}" for field, value in status.items())
    return (
        f"類別 {len(verified.categories)}、文件 {len(verified.requirements)}、"
        f"截止 {verified.deadline}、台灣 {verified.taiwan_eligibility}｜{checks}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="把來源快照抽成獎學金資料")
    parser.add_argument("--source", type=int, help="只抽這個來源 id")
    parser.add_argument("--limit", type=int, help="最多抽幾個來源")
    args = parser.parse_args()
    try:
        llm = GeminiLLM(settings.llm_model, settings.google_api_key)
    except MissingApiKeyError as error:
        sys.exit(str(error))

    child = aliased(Source)
    query = (
        select(Source)
        # 有快照才抽；目錄頁（有子來源的）本身不是獎學金
        .where(exists().where(Snapshot.source_id == Source.id))
        .where(~exists().where(child.parent_id == Source.id))
        .order_by(Source.id)
        .limit(args.limit)
    )
    if args.source:
        query = query.where(Source.id == args.source)

    counts = {"ok": 0, "unchanged": 0, "failed": 0}
    with SessionLocal() as session:
        for source in session.scalars(query).all():
            try:
                summary = extract_source(session, llm, source)
                session.commit()  # 每個來源各自一個交易
            except LLMError as error:
                session.rollback()
                counts["failed"] += 1
                print(f"failed     {source.id} {source.name}：{error}")
                continue
            counts["unchanged" if summary == "unchanged" else "ok"] += 1
            print(f"{source.id:>4} {source.name[:50]}｜{summary}")
    print(f"完成 {counts['ok']}、沒變 {counts['unchanged']}、失敗 {counts['failed']}")
    print(llm.usage_line())


if __name__ == "__main__":
    main()
