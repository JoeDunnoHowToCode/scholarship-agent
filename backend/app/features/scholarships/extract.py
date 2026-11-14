"""抽取指令（第 3 天）：把每個來源最新的快照抽成獎學金、類別與文件清單（ADR-008、031、034、037）。

用法：uv run python -m app.features.scholarships.extract [--source ID] [--limit N] [--shard K/N] [--max-cost NT$] [--cycles-only] [--rules-only] [--amounts-only] [--backfill-amounts]

- 網頁：每頁的可見文字合併後整份抽（ADR-034：一般網頁整頁讀）；學程補抓的 PDF 轉錄後當成一頁（ADR-044）
- PDF 與很長的網頁：切段 → 第一輪列大綱 → 第二輪逐節抽 → 程式合併
- 最後都經過驗證者，再把獎學金、類別、文件清單在同一個交易裡整批重寫
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session, aliased

from app.core import prompts
from app.core.fetch.text import decode_snapshot, html_to_text, pdf_to_text
from app.core.llm.gemini import GeminiLLM, LLMError, MissingApiKeyError
from app.features.costs.llm import gemini
from app.features.documents.chunking import chunk_html, chunk_transcript, group_sections
from app.features.documents.transcribe import transcribe
from app.features.scholarships import (
    amounts,
    changes,
    countries,
    cycles,
    merge,
    relevance,
    rules,
    verify,
)
from app.features.scholarships.models import (
    Change,
    Cycle,
    Requirement,
    Scholarship,
    ScholarshipCategory,
    ScholarshipStatus,
)
from app.features.scholarships.schemas import (
    AmountDraft,
    AmountList,
    CategoryDraft,
    Outline,
    ScholarshipDraft,
    WindowDraft,
    section_schema,
)
from app.features.sources.catalogue import CATALOGUE_URL
from app.features.sources.fetch import SNAPSHOT_DIR, in_shard, latest_snapshot
from app.features.sources.models import FetchMethod, Snapshot, Source
from app.shared.db import SessionLocal
from app.shared.settings import settings

# 提示詞版本：改了提示詞就要改號碼；和快照雜湊、模型一起決定要不要重抽（ADR-013）
PROMPT_VERSION = "extract-12"
OUTLINE_VERSION = "outline-8"
SECTION_VERSION = "section-12"
# 只補金額的提示詞（ADR-074）；改了提示詞就要改號碼
AMOUNTS_VERSION = "amounts-1"
SEEN_WINDOW = timedelta(days=7)  # 抽取只用這麼多天內還抓得到的網址（11-09 使用者選 C）
# 網頁合併後超過這個長度才切段（docs/day-03.md「Claude 自行決定」第 6 點）
LONG_TEXT_CHARS = 100_000


AMOUNTS_PROMPT = prompts.load(AMOUNTS_VERSION)  # 文字在 backend/prompts/（ADR-088）

EXTRACT_PROMPT = prompts.load(PROMPT_VERSION)  # 文字在 backend/prompts/（ADR-088）

OUTLINE_PROMPT = prompts.load(OUTLINE_VERSION)  # 文字在 backend/prompts/（ADR-088）

SECTION_PROMPT = prompts.load(SECTION_VERSION)  # 文字在 backend/prompts/（ADR-088）


def documents(session: Session, source: Source) -> list[Snapshot]:
    """這個來源每個網址最新的快照；內容一樣的頁面只留一份（例如同一頁的不同分頁標籤）。"""
    urls = session.scalars(
        select(Snapshot.url).where(Snapshot.source_id == source.id).distinct()
    ).all()
    # 首頁排第一，其他照網址排序，讓輸入順序固定
    ordered = sorted(urls, key=lambda url: (url != source.url, url))
    latest = [s for url in ordered if (s := latest_snapshot(session, source.id, url))]
    # 只用最近一輪還抓得到的網址（11-09 使用者選 C）：換網址前的舊網站、消失的子頁不再混進抽取；
    # 容許 7 天，某天子頁剛好逾時也不會被排除
    seen = [s.seen_at or s.fetched_at for s in latest]
    if seen:
        newest = max(seen)
        latest = [s for s in latest if (s.seen_at or s.fetched_at) >= newest - SEEN_WINDOW]
    unique: dict[str, Snapshot] = {}
    for snapshot in latest:
        unique.setdefault(snapshot.content_hash, snapshot)
    return list(unique.values())


def snapshot_text(session: Session, source_id: int, hashes: list[str]) -> str:
    """這些內容雜湊（抽取結果的 meta.snapshots）對應的原文：網頁取可見文字、PDF 用 pdfplumber，
    和抽取時核對用的原文一樣。核對變更時用來找回上一版網頁（ADR-064）。"""
    texts: list[str] = []
    for digest in hashes:
        snapshot = session.scalars(
            select(Snapshot).where(Snapshot.source_id == source_id, Snapshot.content_hash == digest).limit(1)
        ).first()
        if snapshot is None:
            continue  # 快照紀錄不見了：少了這一頁的原文，那一頁的引用就當成找不到
        path = SNAPSHOT_DIR / snapshot.file_path
        data = path.read_bytes()
        texts.append(pdf_to_text(data) if path.suffix == ".pdf" else html_to_text(decode_snapshot(data)))
    return "\n\n".join(texts)


def relevance_fingerprint(session: Session, source_id: int, hashes: list[str]) -> str:
    """這些快照裡和獎學金有關的段落的指紋（ADR-079）：網頁依標題切段，PDF 用 pdfplumber 的原文切段。"""
    chunks = []
    for digest in hashes:
        snapshot = session.scalars(
            select(Snapshot).where(Snapshot.source_id == source_id, Snapshot.content_hash == digest).limit(1)
        ).first()
        if snapshot is None:
            continue  # 快照紀錄不見了：少了這一頁，指紋會不同，就會重抽（比較保守）
        path = SNAPSHOT_DIR / snapshot.file_path
        data = path.read_bytes()
        chunks += chunk_transcript(pdf_to_text(data)) if path.suffix == ".pdf" else chunk_html(decode_snapshot(data))
    return relevance.fingerprint(chunks)


def stored_quotes(extracted: dict[str, Any]) -> list[str]:
    """已存的原文引用：截止日、國籍、學位（核對變更用的同一批），加上金額。"""
    quotes = [q for field in ("nationality_scope", "degrees", "windows") for q in changes._quotes(field, extracted)]
    return quotes + [a["evidence"] for a in extracted.get("amounts") or [] if a.get("evidence")]


def extract_web(
    llm: GeminiLLM, snapshots: list[Snapshot]
) -> tuple[ScholarshipDraft, str, dict[str, Any]]:
    """網頁（加上補抓的 PDF）：回傳（初稿, 核對用的原文, 額外紀錄）。"""
    pages: dict[str, str] = {}  # 網址 → 給 AI 讀的文字
    raws: list[str] = []  # 核對用的原文：網頁的可見文字、PDF 的 pdfplumber 原文
    htmls: list[str] = []
    unverified: list[str] = []
    for snapshot in snapshots:
        path = SNAPSHOT_DIR / snapshot.file_path
        if path.suffix == ".pdf":
            # ADR-044：學程的 PDF 照 ADR-037 轉錄，pdfplumber 原文當核對基準
            transcript, missing = transcribe(llm, path)
            pages[snapshot.url] = transcript
            raws.append(pdf_to_text(path.read_bytes()))
            unverified += missing
        else:
            html = decode_snapshot(path.read_bytes())
            htmls.append(html)
            pages[snapshot.url] = html_to_text(html)
            raws.append(pages[snapshot.url])
    text = "\n\n".join(f"=== 頁面：{url} ===\n{body}" for url, body in pages.items())
    extra: dict[str, Any] = {"unverified_numbers": unverified} if unverified else {}
    if len(text) <= LONG_TEXT_CHARS:
        prompt = EXTRACT_PROMPT.format(text=text)
        return llm.extract(prompt, ScholarshipDraft), "\n\n".join(raws), {"mode": "whole", **extra}
    chunks = [chunk for html in htmls for chunk in chunk_html(html)]
    chunks += [c for url, body in pages.items() if url.endswith(".pdf") for c in chunk_transcript(body)]
    draft, long_extra = extract_long(llm, text, group_sections(chunks))
    return draft, "\n\n".join(raws), {**long_extra, **extra}


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
            SECTION_PROMPT.format(name=outline.name, categories=categories, text=text),
            section_schema(outline.category_names),  # ADR-045：類別名稱變成選單
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


def save_cycles(
    session: Session, row: Scholarship, windows: list[WindowDraft], statuses: list[str]
) -> None:
    """申請期整批重寫（ADR-047）。預估的申請期是從真的申請期算出來的，也一起刪掉，
    之後由 cycles 指令依新的資料重新產生，才不會留下依舊資料算出來的預估。"""
    now = datetime.now(UTC)
    session.execute(delete(Cycle).where(Cycle.scholarship_id == row.id))
    built: list[Cycle] = []
    for window, status in zip(windows, statuses, strict=True):
        # 年月日不齊全、或年份是模型自己補的，不建申請期（docs/day-04.md「Claude 自行決定」第 4 點）
        if status in ("incomplete", "year_not_in_quote"):
            continue
        assert window.closes_year and window.closes_month and window.closes_day
        try:
            closes_at, assumed = cycles.to_utc(
                window.closes_year, window.closes_month, window.closes_day,
                window.closes_time, window.timezone,
            )
            opens_at = (
                cycles.to_utc(window.opens_year, window.opens_month, window.opens_day, "00:00", window.timezone)[0]
                if window.opens_year and window.opens_month and window.opens_day
                else None
            )
        except ValueError:
            continue  # 不存在的日期（例如 2 月 30 日），不建申請期
        # Erasmus+ 的固定分群（Programme／Partner countries）用程式的國家清單，不靠模型列
        scope, countries = rules.window_nationality(
            window.nationality_scope, window.nationalities, window.label or window.evidence or ""
        )
        cycle = Cycle(
            scholarship_id=row.id,
            intake=window.intake,
            label=window.label,
            opens_at=opens_at,
            closes_at=closes_at,
            timezone=window.timezone,
            timezone_assumed=assumed,
            nationality_scope=scope,
            nationalities=countries,
            funding=window.funding,
            status=cycles.cycle_status(opens_at, closes_at, now, estimated=False),
            estimated=False,
            evidence=window.evidence,
            verification=status,  # 沒通過驗證的照樣保留，但標出來（ADR-008）
        )
        session.add(cycle)
        built.append(cycle)
    # 喚回（「Claude 自行決定」第 7 點）：新的一屆即將開放或開放中，就改回使用中
    if any(c.status in ("upcoming", "open") for c in built):
        row.status = ScholarshipStatus.ACTIVE


def save(
    session: Session,
    source: Source,
    draft: ScholarshipDraft,
    extracted: dict[str, Any],
    snapshot_id: int | None,
) -> Scholarship:
    """獎學金以 source_id 找同一筆更新；類別、文件清單、申請期整批重寫，變更紀錄一起寫（同一個交易）。"""
    row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).first()
    old = dict(row.extracted) if row is not None else None
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
    row.amount = extracted["amount"]  # 由金額清單產生的文字（ADR-070）
    row.nationality_scope = draft.nationality_scope
    row.nationalities = draft.nationalities
    row.nationality_conditions = draft.nationality_conditions
    row.language_requirements = draft.language_requirements
    row.other_eligibility = draft.other_eligibility
    row.requires_admission = draft.requires_admission
    row.official_url = source.url
    row.last_verified_at = datetime.now(UTC)
    row.extracted = extracted  # JSONB 整個重新指定
    session.flush()  # 先拿到 id，類別與文件才能指向它

    # 變更紀錄（ADR-020）：原文真的變了才寫；只因提示詞或模型改版而重抽的不寫（「Claude 自行決定」第 12 點）
    if old is not None and old.get("meta", {}).get("snapshots") != extracted["meta"]["snapshots"]:
        # ADR-064：會推播的欄位（截止日、國籍、學位）要核對新舊兩版原文，官網真的改了才寫
        old_text = snapshot_text(session, source.id, old.get("meta", {}).get("snapshots") or [])
        new_text = snapshot_text(session, source.id, extracted["meta"]["snapshots"])
        for change in changes.diff_important(old, extracted):
            if change.field in changes.QUOTE_KEYS and not changes.website_changed(
                change.field, old, extracted, old_text, new_text
            ):
                continue  # 只是 AI 這次挑了不同的句子，官網這部分沒改
            session.add(
                Change(
                    scholarship_id=row.id,
                    field=change.field,
                    old_value=change.old,
                    new_value=change.new,
                    changed_at=datetime.now(UTC),
                    snapshot_id=snapshot_id,
                )
            )
    save_cycles(session, row, draft.windows, extracted["verification"]["deadlines"])

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
            degree_conditions=c.degree_conditions,
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


# EACEA 目錄頁的原文（ADR-053）：全世界的學生都可以申請學程，另有獎學金給優秀的學生
CATALOGUE_EVIDENCE = (
    "Master's level students from all over the world can apply. "
    "Additionally, scholarships are available for outstanding students."
)


def clean_country_codes(draft: ScholarshipDraft) -> tuple[ScholarshipDraft, list[str]]:
    """AI 填的國碼用套件檢查（ADR-054）：不存在的丟掉，回傳（清理後的初稿, 不存在的代碼）。"""
    invalid: list[str] = []

    def clean(codes: list[str]) -> list[str]:
        valid, wrong = countries.clean_codes(codes)
        invalid.extend(code for code in wrong if code not in invalid)
        return valid

    categories = [c.model_copy(update={"countries": clean(c.countries)}) for c in draft.categories]
    windows = [w.model_copy(update={"nationalities": clean(w.nationalities)}) for w in draft.windows]
    cleaned = draft.model_copy(
        update={
            "countries": clean(draft.countries),
            "nationalities": clean(draft.nationalities),
            "categories": categories,
            "windows": windows,
        }
    )
    return cleaned, invalid


def current_prompts() -> list[str]:
    """抽取結果記下的提示詞版本（快取鍵的一部分，ADR-013）。"""
    return [PROMPT_VERSION, OUTLINE_VERSION, SECTION_VERSION, verify.PROMPT_VERSION]


def from_catalogue(session: Session, source: Source) -> bool:
    """這個來源是不是從 EACEA 目錄解析出來的學程網站。"""
    if source.parent_id is None:
        return False
    parent = session.get(Source, source.parent_id)
    return parent is not None and parent.url == CATALOGUE_URL


def earliest_deadline(windows: list[WindowDraft]) -> str | None:
    """年月日齊全的窗口裡，最早的截止日（YYYY-MM-DD）；沒有就回傳 None。"""
    dates = [
        f"{w.closes_year:04d}-{w.closes_month:02d}-{w.closes_day:02d}"
        for w in windows
        if w.closes_year and w.closes_month and w.closes_day
    ]
    return min(dates, default=None)


def build_extraction(
    session: Session, llm: GeminiLLM, source: Source, snapshots: list[Snapshot], meta: dict[str, Any]
) -> tuple[ScholarshipDraft, dict[str, Any]]:
    """抽取、核對並組出要存的結果，但不寫資料庫（第 11 天段 2：評估要用同一套流程比較模型）。

    回傳（核對後的初稿, extracted）；extract_source 拿去存檔。
    """
    hashes = sorted(s.content_hash for s in snapshots)
    if source.fetch_method == FetchMethod.PDF:
        draft, raw, extra = extract_pdf(llm, snapshots[0])
    else:
        draft, raw, extra = extract_web(llm, snapshots)
    if not draft.categories:
        # ADR-040：每個獎學金至少一筆類別；模型漏填時用整個獎學金的資料補一筆
        only = CategoryDraft(
            name=draft.name, quota=None, degrees=draft.degrees, countries=draft.countries,
            amount=None, eligibility=None, quota_evidence=None,
            degrees_evidence=draft.degrees_evidence, degree_conditions=None,
        )
        draft = draft.model_copy(update={"categories": [only]})
    # 整份抽取的網頁也可能把同一個截止日寫兩次（例如表格和內文各一次），同一個截止日只留一筆
    draft = draft.model_copy(update={"windows": merge.dedupe_windows(draft.windows)})
    # ADR-103：同一筆錢列兩次（完全一樣、或總額＝每月×月數）只留一筆
    draft = draft.model_copy(update={"amounts": merge.clean_amounts(draft.amounts)})
    draft, invalid_codes = clean_country_codes(draft)
    status = verify.verify(llm, draft, raw, extra.get("conflicts", []))
    status["issues"] += [f"invalid_country_code:{code}" for code in invalid_codes]
    verified = verify.apply_verification(draft, status)
    if verified.nationality_scope == "unclear" and from_catalogue(session, source):
        # ADR-053：EACEA 學程自己的網站沒寫國籍，用目錄頁的說明當依據，驗證結果記成 catalogue
        verified = verified.model_copy(
            update={"nationality_scope": "all", "nationalities": [], "nationality_evidence": CATALOGUE_EVIDENCE}
        )
        status["nationality"] = "catalogue"
    # 金額的核對只用程式（docs/day-09.md「Claude 自行決定」第 21 點），結果和其他欄位一起存在 verification
    status["amounts"] = [amounts.amount_status(a, raw) for a in verified.amounts]
    amount_items = [
        {**a.model_dump(mode="json"), "status": s} for a, s in zip(verified.amounts, status["amounts"], strict=True)
    ]
    deadline = earliest_deadline(verified.windows)
    extracted = {
        **verified.model_dump(mode="json"),
        "deadline": deadline,
        # scholarships.amount 的文字改由金額清單產生（搜尋索引、問答、變更紀錄照舊用它）
        "amount": amounts.describe(amount_items),
        "verification": status,
        "original_nationality_scope": draft.nationality_scope,
        **extra,
        "meta": meta,
        "relevance": relevance_fingerprint(session, source.id, hashes),  # ADR-079
    }
    return verified, extracted


def extract_source(session: Session, llm: GeminiLLM, source: Source) -> str:
    """抽一個來源，回傳一行摘要；內容和提示詞都沒變就跳過。"""
    snapshots = documents(session, source)
    hashes = sorted(s.content_hash for s in snapshots)
    meta = {
        "snapshots": hashes,
        "prompts": current_prompts(),
        "model": settings.llm_model,
    }
    existing = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).first()
    if existing and existing.extracted.get("meta") == meta:
        return "unchanged"
    old_meta = existing.extracted.get("meta", {}) if existing else {}
    if existing and {k: v for k, v in old_meta.items() if k != "snapshots"} == {k: v for k, v in meta.items() if k != "snapshots"}:
        # ADR-079：只有網頁內容變了（提示詞、模型沒變）：只看和獎學金有關的段落有沒有變
        new_fingerprint = relevance_fingerprint(session, source.id, hashes)
        # 這個功能上線前抽的資料沒存指紋：用上次抽取時的快照算
        old_fingerprint = existing.extracted.get("relevance") or relevance_fingerprint(
            session, source.id, old_meta.get("snapshots") or []
        )
        decision = relevance.decide(
            old_fingerprint,
            new_fingerprint,
            stored_quotes(existing.extracted),
            snapshot_text(session, source.id, hashes),
            existing.last_verified_at,
            datetime.now(UTC),
        )
        if decision == "skip":
            # 不重抽：記下新的快照與指紋，之後核對變更、核對引用都用新版原文（JSONB 整個重新指定）
            existing.extracted = {
                **existing.extracted,
                "meta": {**old_meta, "snapshots": hashes},
                "relevance": new_fingerprint,
            }
            return "noise"

    verified, extracted = build_extraction(session, llm, source, snapshots, meta)
    status = extracted["verification"]
    deadline = extracted["deadline"]
    latest = max(snapshots, key=lambda snap: snap.fetched_at)
    save(session, source, verified, extracted, latest.id)
    checks = " ".join(f"{f}={status[f]}" for f in ("nationality", "degrees"))
    flagged = len(status["categories"]) + len(status["issues"])
    return (
        f"類別 {len(verified.categories)}、文件 {len(verified.requirements)}、"
        f"窗口 {len(verified.windows)}、最早截止 {deadline}、國籍 {verified.nationality_scope}"
        f"｜{checks}｜其他待確認 {flagged}"
    )


def rebuild_cycles() -> None:
    """改了申請期的規則後，用已存的抽取結果重建所有申請期（不呼叫 AI、不花錢）。"""
    with SessionLocal() as session, session.begin():
        rows = session.scalars(select(Scholarship).where(Scholarship.source_id.is_not(None))).all()
        for row in rows:
            windows = [WindowDraft.model_validate(w) for w in row.extracted.get("windows", [])]
            save_cycles(session, row, windows, row.extracted["verification"]["deadlines"])
    print(f"已重建 {len(rows)} 筆獎學金的申請期；接著執行 cycles 指令更新狀態與預估")


def needs_amounts(row: Scholarship) -> bool:
    """要不要只補金額（ADR-074）：提示詞版本不是最新、但模型一樣的才補；模型換了要整份重抽。"""
    meta = row.extracted.get("meta", {})
    return bool(meta.get("prompts") != current_prompts() and meta.get("model") == settings.llm_model)


def backfill_amounts(session: Session, llm: GeminiLLM, row: Scholarship) -> str:
    """只補金額（ADR-074）：讀這筆抽取用的快照原文（和核對用的一樣，不另外轉錄 PDF），只抽金額清單；
    其他欄位不動，提示詞版本記成最新，之後原文沒變就不會整份重抽。呼叫的人負責 commit。"""
    assert row.source_id is not None
    raw = snapshot_text(session, row.source_id, row.extracted["meta"]["snapshots"])
    found = llm.extract(AMOUNTS_PROMPT.format(text=raw), AmountList).amounts
    statuses = [amounts.amount_status(amount, raw) for amount in found]
    row.extracted = amounts.with_amounts(
        row.extracted, [a.model_dump(mode="json") for a in found], statuses, current_prompts(), AMOUNTS_VERSION
    )
    row.amount = row.extracted["amount"]
    return f"金額 {len(found)} 筆（核對通過 {statuses.count('supported')}）"


def run_backfill(llm: GeminiLLM, source_id: int | None, limit: int | None, max_cost: float | None) -> None:
    """--backfill-amounts：每筆各自一個交易；鎖住那一列，避免和 worker 同時寫同一筆。"""
    with SessionLocal() as session:
        query = select(Scholarship.id).where(Scholarship.source_id.is_not(None)).order_by(Scholarship.id)
        if source_id:
            query = query.where(Scholarship.source_id == source_id)
        ids = list(session.scalars(query))
    counts = {"ok": 0, "current": 0, "failed": 0}
    for scholarship_id in ids:
        if limit is not None and counts["ok"] >= limit:
            break
        if max_cost and llm.cost_usd() * 32 > max_cost:
            print(f"已超過這次的費用上限 NT${max_cost}，停下")
            break
        with SessionLocal() as session, session.begin():
            row = session.scalars(select(Scholarship).where(Scholarship.id == scholarship_id).with_for_update()).one()
            if not needs_amounts(row):
                counts["current"] += 1
                continue
            try:
                summary = backfill_amounts(session, llm, row)
            except LLMError as error:
                counts["failed"] += 1
                print(f"failed     {row.id} {row.name[:50]}：{error}")
                continue
            counts["ok"] += 1
            print(f"{row.id:>4} {row.name[:50]}｜{summary}")
    print(f"補金額 {counts['ok']}、已經是最新 {counts['current']}、失敗 {counts['failed']}")
    print(llm.usage_line())


def recheck_amounts() -> None:
    """改了金額的核對規則後，用已存的金額與快照原文重新核對（不呼叫 AI、不花錢；ADR-070 只用程式核對）。"""
    with SessionLocal() as session, session.begin():
        rows = session.scalars(select(Scholarship).where(Scholarship.source_id.is_not(None))).all()
        checked = changed = 0
        for row in rows:
            items = row.extracted.get("amounts")
            if not items or row.source_id is None:
                continue  # 第 9 天改版前抽的，還沒有金額清單
            raw = snapshot_text(session, row.source_id, row.extracted["meta"]["snapshots"])
            statuses = [amounts.amount_status(AmountDraft.model_validate(item), raw) for item in items]
            checked += 1
            if statuses == row.extracted["verification"].get("amounts"):
                continue
            changed += 1
            text = amounts.describe([{**item, "status": status} for item, status in zip(items, statuses, strict=True)])
            verification = {**row.extracted["verification"], "amounts": statuses}
            row.extracted = {**row.extracted, "verification": verification, "amount": text}  # JSONB 整個重新指定
            row.amount = text
    print(f"重新核對 {checked} 筆獎學金的金額，{changed} 筆的結果有變")


def recheck_rules(session: Session, source_ids: list[int] | None = None) -> tuple[int, int]:
    """改了程式規則後（ADR-103），對已存的抽取結果重新套用：金額去重與核對、截止日的程式檢查，
    有變的重建申請期。不呼叫 AI、不花錢。source_ids 不給就是全部。回傳（看了幾筆, 改了幾筆）。"""
    query = select(Scholarship).where(Scholarship.source_id.is_not(None))
    if source_ids is not None:
        query = query.where(Scholarship.source_id.in_(source_ids))
    checked = changed = 0
    for row in session.scalars(query).all():
        old = row.extracted
        if row.source_id is None or "verification" not in old or "meta" not in old:
            continue  # 很早期的資料，沒有核對結果
        checked += 1
        windows = [WindowDraft.model_validate(w) for w in old.get("windows", [])]
        # 金額：去重後用快照原文重新核對（和抽取時一樣只用程式）
        saved = [AmountDraft.model_validate({k: v for k, v in a.items() if k != "status"}) for a in old.get("amounts", [])]
        cleaned = merge.clean_amounts(saved)
        raw = snapshot_text(session, row.source_id, old["meta"]["snapshots"]) if cleaned else ""
        statuses = [amounts.amount_status(a, raw) for a in cleaned]
        items = [{**a.model_dump(mode="json"), "status": s} for a, s in zip(cleaned, statuses, strict=True)]
        # 截止日：程式檢查排在「沒值、沒引用、各節說法不同」之後（和 verify.verify 的順序一樣）
        deadlines = [
            status if status in ("conflict", "incomplete", "empty", "no_evidence")
            else verify.window_rule(windows[i]) or status
            for i, status in enumerate(old["verification"]["deadlines"])
        ]
        new = {
            **old,
            "amounts": items,
            "amount": amounts.describe(items),
            "verification": {**old["verification"], "amounts": statuses, "deadlines": deadlines},
        }
        if new == old:
            continue
        changed += 1
        row.extracted = new  # JSONB 整個重新指定
        row.amount = new["amount"]
        save_cycles(session, row, windows, deadlines)
    return checked, changed


def main() -> None:
    parser = argparse.ArgumentParser(description="把來源快照抽成獎學金資料")
    parser.add_argument("--source", type=int, help="只抽這個來源 id")
    parser.add_argument("--limit", type=int, help="最多抽幾個來源")
    parser.add_argument("--shard", help="K/N：只抽第 K 份（共 N 份），讓 N 個程序平行抽")
    parser.add_argument(
        "--max-cost", type=float, help="這次執行的 AI 費用上限（新台幣），超過就停下"
    )
    parser.add_argument(
        "--cycles-only", action="store_true", help="只用已存的抽取結果重建申請期，不呼叫 AI"
    )
    parser.add_argument(
        "--rules-only", action="store_true", help="只用已存的抽取結果重新套用程式規則（ADR-103），不呼叫 AI"
    )
    parser.add_argument(
        "--amounts-only", action="store_true", help="只用已存的金額與快照重新核對金額，不呼叫 AI"
    )
    parser.add_argument(
        "--backfill-amounts", action="store_true", help="只補金額（ADR-074）：其他欄位不動，提示詞版本記成最新"
    )
    args = parser.parse_args()
    if args.cycles_only:
        rebuild_cycles()
        return
    if args.rules_only:
        with SessionLocal() as session, session.begin():
            checked, changed = recheck_rules(session)
        print(f"重新套用規則：看了 {checked} 筆，{changed} 筆有變；接著執行 cycles 指令更新狀態與預估")
        return
    if args.amounts_only:
        recheck_amounts()
        return
    try:
        llm = gemini()
    except MissingApiKeyError as error:
        sys.exit(str(error))
    if args.backfill_amounts:
        run_backfill(llm, args.source, args.limit, args.max_cost)
        return

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
            if args.shard and not in_shard(source.url, args.shard):
                continue
            if args.max_cost and llm.cost_usd() * 32 > args.max_cost:
                print(f"已超過這次的費用上限 NT${args.max_cost}，停下")
                break
            try:
                summary = extract_source(session, llm, source)
                session.commit()  # 每個來源各自一個交易
            except LLMError as error:
                session.rollback()
                counts["failed"] += 1
                print(f"failed     {source.id} {source.name}：{error}")
                continue
            counts["unchanged" if summary in ("unchanged", "noise") else "ok"] += 1
            print(f"{source.id:>4} {source.name[:50]}｜{summary}")
    print(f"完成 {counts['ok']}、沒變 {counts['unchanged']}、失敗 {counts['failed']}")
    print(llm.usage_line())


if __name__ == "__main__":
    main()
