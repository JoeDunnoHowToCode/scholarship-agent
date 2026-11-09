"""抽取的結果（第 11 天段 2 的重構前先釘住）：用假的 AI 回覆和暫存的網頁檔，不連網、不需要本機的快照。

真的資料庫，交易裡跑完就復原；CI 上也能跑。
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.features.scholarships.extract import extract_source
from app.features.scholarships.models import Scholarship
from app.features.scholarships.schemas import ScholarshipDraft
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

    def __init__(self) -> None:
        self.calls = 0

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        self.calls += 1
        if schema is ScholarshipDraft:
            return DRAFT
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
