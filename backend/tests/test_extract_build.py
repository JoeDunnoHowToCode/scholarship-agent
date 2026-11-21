"""抽取的結果（第 11 天段 2 的重構前先釘住）：用假的 AI 回覆和暫存的網頁檔，不連網、不需要本機的快照。

真的資料庫，交易裡跑完就復原；CI 上也能跑。
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.features.scholarships.extract import extract_source
from app.features.scholarships.models import Scholarship
from app.features.scholarships.schemas import (
    AmountDraft,
    CategoryDraft,
    ScholarshipDraft,
)
from app.features.scholarships.verify import ClaimVerdict, Verdicts
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal

PAGE = (
    "<html><body><h1>Test Global Scholarship</h1>"
    "<p>The scholarship is for Master's programmes and covers tuition fees.</p>"
    "<p>Open to all nationalities.</p></body></html>"
)

DRAFT = ScholarshipDraft.model_validate({
    "name": "Test Global Scholarship", "name_zh": "測試全球獎學金", "provider": "Test University",
    "countries": ["SE"], "degrees": ["master"],
    "degrees_evidence": "The scholarship is for Master's programmes and covers tuition fees.",
    "fields": [], "coverage": "Tuition fees", "amounts": [],
    "nationality_scope": "all", "nationalities": [], "nationality_evidence": "Open to all nationalities.",
    "nationality_conditions": None, "language_requirements": None, "other_eligibility": None,
    "requires_admission": None, "total_quota": None, "windows": [], "categories": [], "requirements": [],
})


class FakeLLM:
    """抽取時回傳固定的初稿；核對時每一項都說有根據。"""

    model = "fake-model"

    def __init__(self, draft: ScholarshipDraft = DRAFT) -> None:
        self.calls = 0
        self.draft = draft

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        self.calls += 1
        if schema is ScholarshipDraft:
            return self.draft
        # 核對的提示詞每一項寫成「- 欄位：值 = …」（verify.py）
        claims = [line[2:].split("：")[0] for line in prompt.splitlines() if line.startswith("- ") and "：值 = " in line]
        return Verdicts(verdicts=[ClaimVerdict(claim=c, supported=True, reason="原文有寫") for c in claims])


def test_extract_source_saves_the_verified_draft(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text(PAGE, encoding="utf-8")
    session = SessionLocal()
    try:
        source = Source(name="Test extract", url="https://test-extract.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        now = datetime.now(UTC)
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                             content_hash="a" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
        session.flush()
        summary = extract_source(session, FakeLLM(), source)  # type: ignore[arg-type]
        assert summary.startswith("類別 1、文件 0、窗口 0")  # 模型沒填類別時補一筆（ADR-040）
        row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).one()
        assert (row.name, row.provider, row.countries, row.degrees, row.nationality_scope) == (
            "Test Global Scholarship", "Test University", ["SE"], ["master"], "all",
        )
        verification = row.extracted["verification"]
        assert verification["degrees"] == "supported" and verification["nationality"] == "supported"
        assert row.extracted["meta"]["snapshots"] == ["a" * 64]
        assert row.extracted["mode"] == "whole"
    finally:
        session.rollback()
        session.close()


def test_extraction_keeps_each_amount_once(tmp_path: Path) -> None:
    # ADR-103：一般網頁整份抽也套用金額的規則（總檢查：每月 1,400 和總額 33,600 是同一筆錢）
    page = tmp_path / "page.html"
    page.write_text(PAGE.replace("</body>", "<p>A monthly allowance of EUR 1,400, in total EUR 33,600.</p></body>"),
                    encoding="utf-8")
    quote = "A monthly allowance of EUR 1,400, in total EUR 33,600."
    amounts = [
        AmountDraft.model_validate({"value": value, "currency": "EUR", "period": period, "kind": "living_allowance", "applies_to": None,
         "evidence": quote})
        for value, period in ((1400, "month"), (1400, "month"), (33600, "total"))
    ]
    session = SessionLocal()
    try:
        source = Source(name="Test amounts", url="https://test-amounts.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        now = datetime.now(UTC)
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                             content_hash="b" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
        session.flush()
        extract_source(session, FakeLLM(DRAFT.model_copy(update={"amounts": amounts})), source)  # type: ignore[arg-type]
        row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).one()
        assert [(a["value"], a["period"]) for a in row.extracted["amounts"]] == [(1400, "month")]
    finally:
        session.rollback()
        session.close()


def test_earliest_deadline_ignores_dates_that_are_not_scholarship_applications() -> None:
    # ADR-105：補件日期不算截止日，否則「缺截止日」的來源就不會去補抓 PDF（pdfs.missing_data）
    from app.features.scholarships.extract import earliest_deadline
    from app.features.scholarships.schemas import WindowDraft

    def window(day: int, kind: str) -> WindowDraft:
        return WindowDraft.model_validate({
            "label": None, "intake": None, "opens_year": None, "opens_month": None, "opens_day": None,
            "closes_year": 2027, "closes_month": 3, "closes_day": day, "closes_time": None, "timezone": None,
            "nationality_scope": "all", "nationalities": [], "funding": "any", "evidence": None, "kind": kind,
        })

    assert earliest_deadline([window(9, "document"), window(20, "scholarship")]) == "2027-03-20"
    assert earliest_deadline([window(9, "payment")]) is None


def saved_source(session: Any, tmp_path: Path, url: str) -> Source:
    page = tmp_path / "page.html"
    page.write_text(PAGE, encoding="utf-8")
    source = Source(name="Test cache", url=url, kind=SourceKind.UNIVERSITY)
    session.add(source)
    session.flush()
    now = datetime.now(UTC)
    session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                         content_hash="e" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
    session.flush()
    extract_source(session, FakeLLM(), source)  # type: ignore[arg-type]
    return source


def set_meta(session: Any, source: Source, **changes: Any) -> None:
    row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).one()
    row.extracted = {**row.extracted, "meta": {**row.extracted["meta"], **changes}}  # JSONB 整個重新指定
    session.flush()


def test_prompt_change_does_not_reextract_but_model_change_does(tmp_path: Path) -> None:
    # ADR-104：提示詞改版不再讓所有來源重抽（原文沒變就沿用）；換模型照舊重抽
    session = SessionLocal()
    try:
        source = saved_source(session, tmp_path, "https://test-cache.example/")
        set_meta(session, source, prompts=["extract-1", "outline-1", "section-1", "verify-1"])
        llm = FakeLLM()
        assert extract_source(session, llm, source) == "unchanged"  # type: ignore[arg-type]
        assert llm.calls == 0
        set_meta(session, source, model="another-model")
        assert extract_source(session, FakeLLM(), source) != "unchanged"  # type: ignore[arg-type]
    finally:
        session.rollback()
        session.close()


def test_force_reextracts_a_source_that_has_not_changed(tmp_path: Path) -> None:
    # ADR-104：要用新版提示詞重抽，就指定來源並加 force
    session = SessionLocal()
    try:
        source = saved_source(session, tmp_path, "https://test-force.example/")
        llm = FakeLLM()
        assert extract_source(session, llm, source, force=True) != "unchanged"  # type: ignore[arg-type]
        assert llm.calls > 0
    finally:
        session.rollback()
        session.close()


def test_country_groups_are_saved_as_country_codes(tmp_path: Path) -> None:
    # D1 C（ADR-109）：AI 填群組代號，存檔時展開成國碼，評分與申請期用展開後的國碼
    from app.features.scholarships.models import Cycle

    page = tmp_path / "page.html"
    page.write_text(PAGE.replace("Open to all nationalities.", "Open to citizens of African Union member states. "
                                 "EU applicants apply by 1 March 2027."), encoding="utf-8")
    window = {"label": None, "intake": None, "opens_year": None, "opens_month": None, "opens_day": None,
              "closes_year": 2027, "closes_month": 3, "closes_day": 1, "closes_time": None, "timezone": None,
              "nationality_scope": "listed", "nationalities": [], "nationality_groups": ["EU"], "funding": "any",
              "evidence": "EU applicants apply by 1 March 2027"}
    draft = DRAFT.model_copy(update={
        "nationality_scope": "listed", "nationality_groups": ["AU"],
        "nationality_evidence": "Open to citizens of African Union member states.",
        "windows": [ScholarshipDraft.model_validate({**DRAFT.model_dump(), "windows": [window]}).windows[0]],
    })
    session = SessionLocal()
    try:
        source = Source(name="Test groups", url="https://test-groups-save.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        now = datetime.now(UTC)
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                             content_hash="f" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
        session.flush()
        extract_source(session, FakeLLM(draft), source)  # type: ignore[arg-type]
        row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).one()
        assert row.nationality_scope == "listed" and len(row.nationalities) == 55 and "NG" in row.nationalities
        cycle = session.scalars(select(Cycle).where(Cycle.scholarship_id == row.id)).one()
        assert len(cycle.nationalities) == 27 and "FR" in cycle.nationalities
    finally:
        session.rollback()
        session.close()


def test_saving_drops_category_regions_that_only_repeat_the_exclusion(tmp_path: Path) -> None:
    # 11-21 重新檢查（ADR-120）：非歐盟學生的學費獎學金，AI 把整筆排除的 EU、EEA 抄進類別；存下來的類別不帶這些代號
    page = tmp_path / "page.html"
    page.write_text(PAGE.replace("Open to all nationalities.", "Only for non-EU/EEA students."), encoding="utf-8")
    only = CategoryDraft.model_validate({
        "name": "Test Global Scholarship", "quota": None, "degrees": ["master"], "countries": ["SE"], "amount": None,
        "eligibility": None, "quota_evidence": None, "degrees_evidence": None, "degree_conditions": None,
        "nationality_groups": ["EU", "EEA"],
    })
    draft = DRAFT.model_copy(update={
        "nationality_scope": "excluded", "nationality_groups": ["EU", "EEA"],
        "nationality_evidence": "Only for non-EU/EEA students.", "categories": [only],
    })
    session = SessionLocal()
    try:
        source = Source(name="Test exclusion", url="https://test-exclusion.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        now = datetime.now(UTC)
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                             content_hash="b" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
        session.flush()
        extract_source(session, FakeLLM(draft), source)  # type: ignore[arg-type]
        row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).one()
        assert row.nationality_scope == "excluded"
        assert row.extracted["categories"][0]["nationality_groups"] == []
    finally:
        session.rollback()
        session.close()
