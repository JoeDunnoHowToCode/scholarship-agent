"""設定頁的 API（第 10 天段 6）：用 FastAPI 的 TestClient 打 API，資料庫在交易裡跑完就復原。"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.features.costs.recorder import CostRecorder, MonthlyCapError
from app.features.pipeline import breaker
from app.features.settings.models import AppSetting
from app.features.settings.service import effective
from app.features.sources.models import Discovery, Source, SourceKind, SourceStatus
from app.main import app
from app.shared.db import SessionLocal, get_session
from app.shared.settings import settings


class NoCommit:
    """API 裡的 commit 只 flush，測試結束時整個交易復原。"""

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
    session.execute(delete(AppSetting))  # 從預設值開始（交易結束會復原）
    app.dependency_overrides[get_session] = lambda: NoCommit(session)
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.rollback()
        session.close()


client = TestClient(app)


def test_settings_start_from_the_env_defaults(db: Session) -> None:
    body = client.get("/api/settings").json()
    assert (body["notify_threshold"], body["monthly_cap_ntd"], body["cap_limit_ntd"]) == (
        settings.notify_threshold, settings.monthly_cap_ntd, 7000,
    )
    assert body["breaker"]["open"] == breaker.is_open(db)


def test_saved_settings_take_effect(db: Session) -> None:
    response = client.put("/api/settings", json={"notify_threshold": 75, "monthly_cap_ntd": 500})
    assert response.status_code == 200
    assert (response.json()["notify_threshold"], response.json()["monthly_cap_ntd"]) == (75, 500)
    assert effective(db, 1).notify_threshold == 75 and effective(db, 1).monthly_cap_ntd == 500


@pytest.mark.parametrize("body", [
    {"notify_threshold": 101, "monthly_cap_ntd": 500},
    {"notify_threshold": -1, "monthly_cap_ntd": 500},
    {"notify_threshold": 60, "monthly_cap_ntd": 7001},  # ADR-049：不能超過 NT$7,000
    {"notify_threshold": 60, "monthly_cap_ntd": 0},
])
def test_out_of_range_settings_are_refused(db: Session, body: dict[str, float]) -> None:
    assert client.put("/api/settings", json=body).status_code == 422


def test_the_cost_recorder_uses_the_saved_cap(db: Session) -> None:
    client.put("/api/settings", json={"notify_threshold": 60, "monthly_cap_ntd": 1})
    shared = NoCommit(db)
    recorder = CostRecorder(cap_ntd=None, sessions=lambda: shared)  # type: ignore[arg-type, return-value]
    recorder.after_call("hello", "gemini-test", 1, 1, 0.05, None)  # NT$1.6
    with pytest.raises(MonthlyCapError):
        recorder.before_call()


def test_the_breaker_can_be_reset_from_the_page(db: Session) -> None:
    breaker.open_breaker(db, "測試：本月 AI 已達每月上限")
    db.flush()
    assert client.get("/api/settings").json()["breaker"]["open"] is True
    assert client.post("/api/settings/breaker/reset").json()["breaker"]["open"] is False


def test_agent_sources_are_listed_and_can_be_switched_off_and_on(db: Session) -> None:
    now = datetime.now(UTC)
    added = Source(name="Test Lund Global", url="https://test-api-lund.example/s", kind=SourceKind.UNIVERSITY,
                   discovery=Discovery.SEARCH, status=SourceStatus.APPROVED, decided_at=now)
    replaced = Source(name="Test old programme", url="https://test-api-old.example/", kind=SourceKind.UNIVERSITY,
                      discovery=Discovery.CATALOGUE, enabled=False, review_note="已由 #1 取代", disabled_at=now)
    plain = Source(name="Test plain", url="https://test-api-plain.example/", kind=SourceKind.UNIVERSITY,
                   discovery=Discovery.CATALOGUE)
    db.add_all([added, replaced, plain])
    db.flush()
    listed = {row["id"]: row for row in client.get("/api/discovery/sources").json()}
    # agent 加的、被停用（有原因）的都列出來；一般的目錄來源不列
    assert added.id in listed and replaced.id in listed and plain.id not in listed
    assert (listed[added.id]["status"], listed[added.id]["enabled"]) == ("approved", True)
    assert listed[replaced.id]["review_note"] == "已由 #1 取代"
    off = client.patch(f"/api/discovery/sources/{added.id}", json={"enabled": False}).json()
    assert off["enabled"] is False and added.disabled_at is not None
    on = client.patch(f"/api/discovery/sources/{replaced.id}", json={"enabled": True}).json()
    assert (on["enabled"], on["review_note"]) == (True, None)
    assert (replaced.disabled_at, replaced.empty_extractions) == (None, 0)
    assert client.patch("/api/discovery/sources/999999999", json={"enabled": True}).status_code == 404


def judged_not_scholarship(db: Session, name: str, check: str) -> Source:
    """一個來源＋主角那筆：AI 判斷「這頁不是獎學金」，引用的核對結果是 check。"""
    from app.features.scholarships.models import Scholarship

    source = Source(name=name, url=f"https://test-review-{check}-{len(name)}.example/", kind=SourceKind.UNIVERSITY)
    db.add(source)
    db.flush()
    db.add(Scholarship(name=name, source_id=source.id, extracted={
        "not_scholarship": True, "not_scholarship_evidence": "Study programmes",
        "verification": {"not_scholarship": check},
    }))
    db.flush()
    return source


def test_unverified_not_scholarship_judgments_wait_for_you(db: Session) -> None:
    # ADR-115（總檢查 C4 選 B）：AI 說「這頁不是獎學金」，但引用沒核對過，所以沒有自動停用、一直卡在列表上；
    # 列在設定頁，由你決定。核對過的已經自動停用，不必列
    unverified = judged_not_scholarship(db, "Test Royal Academy study programmes", "not_supported")
    verified = judged_not_scholarship(db, "Test verified", "supported")
    response = client.get("/api/settings/review")
    assert response.status_code == 200
    listed = {row["source_id"]: row for row in response.json()}
    assert unverified.id in listed and verified.id not in listed
    assert (listed[unverified.id]["name"], listed[unverified.id]["evidence"]) == (
        "Test Royal Academy study programmes", "Study programmes",
    )


def test_you_can_disable_a_source_judged_not_a_scholarship(db: Session) -> None:
    source = judged_not_scholarship(db, "Test disable me", "quote_not_found")
    response = client.post(f"/api/settings/review/{source.id}", json={"action": "disable"})
    assert response.status_code == 200
    assert (source.enabled, source.review_note) == (False, "你在設定頁停用：這頁不是獎學金")
    assert source.id not in {row["source_id"] for row in client.get("/api/settings/review").json()}


def test_a_source_you_keep_stays_in_the_daily_check_and_leaves_the_list(db: Session) -> None:
    # 你判斷 AI 錯了（這頁有獎學金）：照常檢查；之後重抽同樣的判斷也不再列出來
    source = judged_not_scholarship(db, "Test keep me", "not_supported")
    response = client.post(f"/api/settings/review/{source.id}", json={"action": "keep"})
    assert response.status_code == 200
    assert source.enabled is True
    assert source.id not in {row["source_id"] for row in response.json()}
