"""CI 用的範例資料（ADR-099）：在空的資料庫建一筆假的獎學金和一則假的通知。

有些測試只讀開發資料庫裡的資料（例如詳細頁摘要、通知歷史），CI 的資料庫是空的，所以先放一點假資料。
內容全部是虛構的，不是從任何網站抓來的（repo 是公開的）。重跑不會重複。

用法：cd backend && uv run python scripts/ci_sample_data.py   （先跑遷移與種子）
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 讓 python scripts/… 找得到 app

from sqlalchemy import select

from app.features.notifications.models import Event
from app.features.profiles.service import CURRENT_USER_ID
from app.features.scholarships.models import Cycle, Scholarship
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal

URL = "https://ci-sample.example/scholarship"


def main() -> None:
    now = datetime.now(UTC)
    with SessionLocal() as session:
        if session.scalars(select(Source).where(Source.url == URL)).first() is not None:
            print("範例資料已經有了")
            return
        source = Source(name="CI Sample Scholarship", url=URL, kind=SourceKind.INSTITUTION)
        session.add(source)
        session.flush()
        row = Scholarship(
            name="CI Sample Scholarship", provider="CI Sample Foundation", source_id=source.id,
            countries=["SE"], degrees=["master"], nationality_scope="all", nationalities=[],
            official_url=URL, extracted={"verification": {"degrees": "supported"}, "amounts": []},
        )
        session.add(row)
        session.flush()
        session.add(Cycle(scholarship_id=row.id, closes_at=now + timedelta(days=60), status="upcoming"))
        session.add(Event(
            user_id=CURRENT_USER_ID, kind="new_scholarship", scholarship_id=row.id,
            dedup_key=f"ci-sample:{row.id}", status="sent", created_at=now, sent_at=now,
            payload={"kind": "new_scholarship", "title": "新獎學金：CI Sample Scholarship", "lines": [], "url": URL},
        ))
        session.commit()
        print("已建立範例資料：1 個來源、1 筆獎學金、1 個申請期、1 則通知")


if __name__ == "__main__":
    main()
