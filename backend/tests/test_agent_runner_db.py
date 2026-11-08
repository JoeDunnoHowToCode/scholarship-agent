"""跑一次 agent 並留下紀錄（ADR-089），在真的資料庫上跑：交易裡跑完就復原。"""

from typing import Any, Self

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm.base import ChatMessage, ToolCall, ToolSpec, Turn
from app.features.discovery.models import AgentRun, AgentStep
from app.features.discovery.runner import execute
from app.features.discovery.tools import Page, SearchHit, Toolbox
from app.shared.db import SessionLocal


class NoCommit:
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


class TwoSteps:
    """先搜尋，再回答。"""

    def __init__(self) -> None:
        self.turns = [
            Turn(ChatMessage("assistant", "", [ToolCall("c1", "search", {"query": "Lund"})]), 30, 5, 0.01),
            Turn(ChatMessage("assistant", "沒找到合適的頁面"), 40, 6, 0.02),
        ]

    def step(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> Turn:
        return self.turns.pop(0)


class Broken:
    def step(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> Turn:
        raise RuntimeError("Gemini 掛了")


def box() -> Toolbox:
    return Toolbox(lambda q: [SearchHit("t", "https://lu.se/s", "c")], lambda u: Page(u, "", []), searches_left=5)


def test_a_run_is_recorded_with_its_result_steps_and_cost() -> None:
    session = SessionLocal()
    try:
        shared = NoCommit(session)
        run_id, outcome = execute(
            "smoke", "test", "任務說明", "開始", box(), True, 5, 1.0,
            make_llm=lambda _: TwoSteps(), sessions=lambda: shared,  # type: ignore[arg-type, return-value]
        )
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert (run.task, run.target, run.result, run.steps) == ("smoke", "test", "done", 2)
        assert run.cost_usd == pytest.approx(0.03) and run.final_text == "沒找到合適的頁面"
        assert run.finished_at is not None
        kinds = session.scalars(select(AgentStep.kind).where(AgentStep.agent_run_id == run_id).order_by(AgentStep.id)).all()
        assert kinds == ["model", "tool", "model"]
        assert outcome.result == "done"
    finally:
        session.rollback()
        session.close()


def test_a_crash_is_recorded_as_error_and_raised_again() -> None:
    session = SessionLocal()
    try:
        shared = NoCommit(session)
        with pytest.raises(RuntimeError, match="Gemini 掛了"):
            execute(
                "smoke", None, "任務說明", "開始", box(), True, 5, 1.0,
                make_llm=lambda _: Broken(), sessions=lambda: shared,  # type: ignore[arg-type, return-value]
            )
        run = session.scalars(select(AgentRun).where(AgentRun.task == "smoke").order_by(AgentRun.id.desc())).first()
        assert run is not None
        assert run.result == "error" and "Gemini 掛了" in (run.final_text or "")
    finally:
        session.rollback()
        session.close()
