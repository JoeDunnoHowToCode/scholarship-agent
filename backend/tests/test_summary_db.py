"""獎學金說明寫進資料庫（docs/summary-plan.md）：真的資料庫，交易裡跑完就復原；假的 AI。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.features.scholarships import summary
from app.features.scholarships.models import Scholarship
from app.features.scholarships.schemas import SummaryDraft, SummarySentence
from app.features.scholarships.verify import ClaimVerdict, Verdicts
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal

TEXT = "The Test Foundation offers 20 scholarships to non-EU students."


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        self.calls += 1
        if schema is SummaryDraft:
            return SummaryDraft(sentences=[
                SummarySentence(text="由 Test Foundation 提供 20 個名額。", evidence="The Test Foundation offers 20 scholarships"),
                SummarySentence(text="給所有學生。", evidence="open to everyone"),  # 引用不在原文
            ])
        return Verdicts(verdicts=[ClaimVerdict(claim="s0", supported=True, reason="")])


def scholarship(session: Session, tmp_path: Path) -> Scholarship:
    page = tmp_path / "page.html"
    page.write_text(f"<html><body><p>{TEXT}</p></body></html>", encoding="utf-8")
    source = Source(name="Test summary", url="https://test-summary.example/", kind=SourceKind.UNIVERSITY)
    session.add(source)
    session.flush()
    now = datetime.now(UTC)
    session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                         content_hash="f" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
    row = Scholarship(name="Test summary", source_id=source.id, countries=["SE"], degrees=["master"],
                      nationality_scope="all", nationalities=[],
                      extracted={"meta": {"snapshots": ["f" * 64]}, "verification": {}})
    session.add(row)
    session.flush()
    return row


def test_ensure_summary_writes_once_per_version(tmp_path: Path) -> None:
    session = SessionLocal()
    try:
        row = scholarship(session, tmp_path)
        llm = FakeLLM()
        assert summary.ensure_summary(session, llm, row) is True
        assert row.extracted["summary_from"] == summary.SUMMARY_VERSION
        assert [s["status"] for s in row.extracted["summary"]] == ["supported", "quote_not_found"]
        # 已經是最新版本：不再呼叫 AI
        calls = llm.calls
        assert summary.ensure_summary(session, llm, row) is False
        assert llm.calls == calls
    finally:
        session.rollback()
        session.close()
