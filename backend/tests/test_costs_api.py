"""紀錄頁的 API（第 10 天段 6，ADR-089）：資料庫在交易裡跑完就復原。"""

from collections.abc import Iterator
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.features.costs.models import LLMCall
from app.features.discovery.models import AgentRun, AgentStep
from app.main import app
from app.shared.db import SessionLocal, get_session


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


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    app.dependency_overrides[get_session] = lambda: NoCommit(session)
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.rollback()
        session.close()


client = TestClient(app)


def test_costs_show_this_month_by_feature_and_the_cap(db: Session) -> None:
    before = client.get("/api/costs").json()
    db.add(LLMCall(feature="test-api", prompt_version=None, model="m", input_tokens=1, output_tokens=1,
                   cost_usd=0.5, error=None))
    db.flush()
    after = client.get("/api/costs").json()
    assert after["month_ntd"] == pytest.approx(before["month_ntd"] + 16)  # 0.5 美元 × 32
    assert after["cap_ntd"] > 0
    features = {row["feature"]: row for row in after["by_feature"]}
    assert features["test-api"]["calls"] == 1 and features["test-api"]["ntd"] == pytest.approx(16)
    assert after["by_day"] and "day" in after["by_day"][-1]


def test_agent_runs_and_their_steps(db: Session) -> None:
    run = AgentRun(task="smoke", target="test", result="done", steps=2, cost_usd=0.01, final_text="完成")
    db.add(run)
    db.flush()
    db.add_all([
        AgentStep(agent_run_id=run.id, number=1, kind="model", summary="呼叫 search", full_text="呼叫 search(...)",
                  input_tokens=10, output_tokens=2),
        AgentStep(agent_run_id=run.id, number=1, kind="tool", tool="search", args={"query": "q"}, summary="1. 結果",
                  full_text=None),
    ])
    db.flush()
    runs = client.get("/api/agent-runs", params={"limit": 5}).json()
    assert runs, "應該列出 agent 的執行"
    assert runs[0]["id"] == run.id  # 最新的在前
    assert (runs[0]["task"], runs[0]["result"], runs[0]["ntd"]) == ("smoke", "done", pytest.approx(0.32))
    steps = client.get(f"/api/agent-runs/{run.id}/steps").json()
    assert [(s["kind"], s["tool"], s["full_text"]) for s in steps] == [
        ("model", None, "呼叫 search(...)"),
        ("tool", "search", None),  # 超過 30 天的全文清掉了也照樣列出摘要
    ]
