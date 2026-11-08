"""通知歷史 API 回傳是哪一筆獎學金（ADR-092）：網頁的通知卡片才能點回詳細頁。

用開發用的資料庫，只讀不寫。
"""

from app.features.notifications import api
from app.shared.db import SessionLocal


def test_scholarship_events_carry_their_scholarship_id() -> None:
    with SessionLocal() as session:
        events = api.list_events(session, limit=200)
    about_one = [e for e in events if e.kind != "system"]
    assert about_one, "開發資料庫裡應該有和單一獎學金有關的通知"
    assert all(e.scholarship_id is not None for e in about_one)
    assert all(e.scholarship_id is None for e in events if e.kind == "system")  # 每日報告這類通知不屬於任何一筆
