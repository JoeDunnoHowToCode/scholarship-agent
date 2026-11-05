"""產生通知要能在真的資料庫上跑完（11-04 發現：新年度公布的查詢寫錯，收尾工作當掉）。

用開發用的資料庫，在交易裡跑完就復原，不留任何資料；需要已經有個人資料（docker compose 起著）。
"""

from datetime import UTC, datetime

import pytest

from app.features.notifications.generate import generate
from app.features.profiles.service import CURRENT_USER_ID
from app.shared.db import SessionLocal


def test_generate_runs_on_the_real_database() -> None:
    session = SessionLocal()
    try:
        try:
            counts = generate(session, CURRENT_USER_ID, datetime.now(UTC))
        except Exception as error:  # noqa: BLE001 — 任何例外都代表收尾工作會當掉
            pytest.fail(f"generate() 當掉：{type(error).__name__}: {error}")
        assert isinstance(counts, dict)
    finally:
        session.rollback()  # generate 不 commit；這裡復原，不留下事件
        session.close()
