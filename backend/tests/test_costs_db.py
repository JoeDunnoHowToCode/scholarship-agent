"""費用紀錄在真的資料庫上跑（ADR-089）：在交易裡跑完就復原，不留任何資料。"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.features.costs.log import month_total_usd, record_call
from app.features.costs.models import LLMCall
from app.features.costs.usage import month_start
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
