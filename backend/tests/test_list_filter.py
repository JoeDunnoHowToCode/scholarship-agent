"""網頁列表「只看開放中的」篩選（11-07）：只留現在已開放、還沒截止的申請期，不含即將開放的。"""

from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql

from app.features.scholarships import api

NOW = datetime(2027, 3, 1, tzinfo=UTC)


def test_open_only_keeps_rounds_open_right_now_not_upcoming_ones() -> None:
    query = api.cycle_filter(open_only=True, deadline_after=None, deadline_before=None, now=NOW)
    compiled = query.compile(dialect=postgresql.dialect())
    sql, params = str(compiled), dict(compiled.params)
    # 照日期當下判斷（和卡片上的狀態同一套規則），不用資料庫裡上次更新的 status
    assert "upcoming" not in params.values()
    assert "cycles.closes_at >" in sql  # 還沒截止
    assert "cycles.opens_at IS NULL" in sql and "cycles.opens_at <=" in sql  # 已開放；開放日原文沒寫的算開放中
    assert NOW in params.values()
    assert "cycles.estimated IS false" in sql  # 程式預估的申請期不算
