"""核對沒過就把錯誤拋回 AI 重抽一次（ADR-111）。假的 AI、真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.features.scholarships.extract import extract_source
from app.features.scholarships.schemas import ScholarshipDraft
from app.features.scholarships.verify import ClaimVerdict, Verdicts
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal
from tests.test_extract_build import DRAFT, PAGE


class JudgingLLM:
    """抽取時依序回傳 drafts；核對時，unsupported 裡的項目判不支持。記下每次抽取的提示詞。"""

    model = "fake-model"

    def __init__(self, drafts: list[ScholarshipDraft], unsupported: list[set[str]]) -> None:
        self.drafts, self.unsupported, self.prompts = list(drafts), list(unsupported), []

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        if schema is ScholarshipDraft:
            self.prompts.append(prompt)
            return self.drafts.pop(0)
        bad = self.unsupported.pop(0) if self.unsupported else set()
        claims = [line[2:].split("：")[0] for line in prompt.splitlines() if line.startswith("- ") and "：值 = " in line]
        return Verdicts(verdicts=[ClaimVerdict(claim=c, supported=c not in bad, reason="") for c in claims])


def source_with_page(session: Session, tmp_path: Path) -> Source:
    path = tmp_path / "page.html"
    path.write_text(PAGE, encoding="utf-8")
    source = Source(name="Test retry", url="https://test-retry.example/", kind=SourceKind.UNIVERSITY)
    session.add(source)
    session.flush()
    now = datetime.now(UTC)
    session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                         content_hash="5" * 64, file_path=str(path), http_status=200, etag=None, last_modified=None))
    session.flush()
    return source


def test_no_retry_when_every_check_passes(tmp_path: Path) -> None:
    session = SessionLocal()
    try:
        llm = JudgingLLM([DRAFT], [set()])
        extract_source(session, llm, source_with_page(session, tmp_path))  # type: ignore[arg-type]
        assert len(llm.prompts) == 1
    finally:
        session.rollback()
        session.close()


def test_a_failed_check_retries_once_with_the_error_message(tmp_path: Path) -> None:
    # 第一次：核對的 AI 判學位不支持 → 拋回錯誤重抽；重抽的提示詞要寫出哪個欄位、為什麼
    session = SessionLocal()
    try:
        llm = JudgingLLM([DRAFT, DRAFT], [{"degrees"}, set()])
        extract_source(session, llm, source_with_page(session, tmp_path))  # type: ignore[arg-type]
        assert len(llm.prompts) == 2
        assert "- 學位：上次填" in llm.prompts[1] and "核對的 AI 判斷引用撐不起這個值" in llm.prompts[1]
        assert "上次填" not in llm.prompts[0]
    finally:
        session.rollback()
        session.close()
