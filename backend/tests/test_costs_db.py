"""費用紀錄在真的資料庫上跑（ADR-089）：在交易裡跑完就復原，不留任何資料。"""

from datetime import UTC, datetime, timedelta
from typing import Any, Self

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.costs.log import month_total_usd, record_call
from app.features.costs.models import LLMCall
from app.features.costs.recorder import CostRecorder, MonthlyCapError
from app.features.costs.summary import summarize
from app.features.costs.usage import NTD_PER_USD, TAIPEI, month_start
from app.features.pipeline.errors import classify
from app.features.sources import pick
from app.shared.db import SessionLocal


def test_calls_are_recorded_and_summed_for_this_month() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        before = month_total_usd(session, now)
        sent = pick.PROMPT.format(name="MULTICOM", url="https://example.eu", max_picks=3, links="- Apply | /apply")
        record_call(session, sent, "gemini-test", 100, 20, 0.5, None)
        record_call(session, "hello", "gemini-test", 0, 0, 0.0, "TimeoutError")  # 失敗的呼叫也記
        # 上個月最後一秒花的錢不算進本月
        session.add(LLMCall(
            called_at=month_start(now) - timedelta(seconds=1), feature="extract", prompt_version=None,
            model="gemini-test", input_tokens=1, output_tokens=1, cost_usd=100.0, error=None,
        ))
        session.flush()
        rows = session.scalars(
            select(LLMCall).where(LLMCall.model == "gemini-test", LLMCall.called_at >= month_start(now))
            .order_by(LLMCall.id)
        ).all()
        assert [(r.feature, r.prompt_version, r.input_tokens, r.error) for r in rows] == [
            ("links", "links-1", 100, None),
            ("unknown", None, 0, "TimeoutError"),
        ]
        assert month_total_usd(session, now) == pytest.approx(before + 0.5)
    finally:
        session.rollback()
        session.close()


class NoCommit:
    """讓 CostRecorder 用測試的連線：commit 只 flush，測試結束時整個交易復原。"""

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


def test_recorder_records_and_blocks_once_the_cap_is_reached() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        before = month_total_usd(session, now)
        shared = NoCommit(session)
        # 上限設成「目前總額＋1 美元」：再花 1 美元就到頂
        recorder = CostRecorder(cap_ntd=(before + 1.0) * NTD_PER_USD, source_id=None, sessions=lambda: shared)  # type: ignore[arg-type, return-value]
        recorder.before_call()  # 還沒到上限：不擋
        recorder.after_call("hello", "gemini-test", 10, 5, 1.0, None)
        assert month_total_usd(session, now) == pytest.approx(before + 1.0)
        with pytest.raises(MonthlyCapError, match="每月上限"):
            recorder.before_call()  # 到上限了：下一次呼叫前就擋下
        # 背景工作遇到它會打開斷路器（ADR-056）
        assert classify(MonthlyCapError("x")) == "pause_ai"
    finally:
        session.rollback()
        session.close()


def test_summary_groups_this_month_by_feature_and_recent_days() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        before = summarize(session, now)
        for feature, cost in [("test-a", 0.2), ("test-a", 0.3), ("test-b", 0.1)]:
            session.add(LLMCall(
                feature=feature, prompt_version=None, model="gemini-test",
                input_tokens=1, output_tokens=1, cost_usd=cost, error=None,
            ))
        session.flush()
        after = summarize(session, now)
        assert after.month_usd == pytest.approx(before.month_usd + 0.6)
        features = {name: (count, usd) for name, count, usd in after.by_feature}
        assert features["test-a"][0] == 2 and features["test-a"][1] == pytest.approx(0.5)
        assert features["test-b"][0] == 1 and features["test-b"][1] == pytest.approx(0.1)
        # 今天（台灣日期）多了 0.6 美元；最近 7 天最多 7 筆，舊的在前
        today = now.astimezone(TAIPEI).date()
        before_today = dict(before.by_day).get(today, 0.0)
        assert dict(after.by_day)[today] == pytest.approx(before_today + 0.6)
        assert len(after.by_day) <= 7 and after.by_day == sorted(after.by_day)
    finally:
        session.rollback()
        session.close()
