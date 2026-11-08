"""agent 每一步的紀錄與 30 天清理（ADR-089），在真的資料庫上跑：交易裡跑完就復原。"""

from datetime import UTC, datetime, timedelta
from typing import Any, Self

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm.base import ChatMessage, ToolCall, Turn
from app.features.discovery.models import AgentRun, AgentStep
from app.features.discovery.trace import DbStepLog, clear_old_texts
from app.shared.db import SessionLocal


class NoCommit:
    """讓 DbStepLog 用測試的連線：commit 只 flush，測試結束時整個交易復原。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def commit(self) -> None:
        self.session.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.session, name)


def test_each_step_is_written_with_summary_and_full_text() -> None:
    session = SessionLocal()
    try:
        run = AgentRun(task="smoke")
        session.add(run)
        session.flush()
        shared = NoCommit(session)
        log = DbStepLog(run.id, sessions=lambda: shared)  # type: ignore[arg-type, return-value]
        turn = Turn(ChatMessage("assistant", "", [ToolCall("c1", "search", {"query": "UK scholarship"})]), 50, 10, 0.001)
        log.model(1, turn)
        log.tool(1, "search", {"query": "UK scholarship"}, "結果" * 300)
        steps = session.scalars(select(AgentStep).where(AgentStep.agent_run_id == run.id).order_by(AgentStep.id)).all()
        assert [(s.number, s.kind, s.tool, s.args) for s in steps] == [
            (1, "model", None, None),
            (1, "tool", "search", {"query": "UK scholarship"}),
        ]
        model, tool = steps
        assert "search" in model.summary and "UK scholarship" in model.summary  # 看摘要就知道 AI 要做什麼
        assert (model.input_tokens, model.output_tokens) == (50, 10)
        assert len(tool.summary) == 200 and tool.full_text == "結果" * 300  # 摘要截短，全文完整
    finally:
        session.rollback()
        session.close()


def test_full_texts_older_than_30_days_are_cleared() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        run = AgentRun(task="smoke")
        session.add(run)
        session.flush()
        old = AgentStep(agent_run_id=run.id, number=1, kind="tool", tool="read_page", args={"url": "https://a.eu"},
                        summary="舊的", full_text="舊的全文", created_at=now - timedelta(days=31))
        recent = AgentStep(agent_run_id=run.id, number=2, kind="tool", tool="read_page", args={"url": "https://b.eu"},
                           summary="新的", full_text="新的全文", created_at=now - timedelta(days=29))
        session.add_all([old, recent])
        session.flush()
        assert clear_old_texts(session, now) >= 1
        session.refresh(old)
        session.refresh(recent)
        assert (old.full_text, old.summary, old.args) == (None, "舊的", {"url": "https://a.eu"})  # 只清全文
        assert recent.full_text == "新的全文"
    finally:
        session.rollback()
        session.close()
