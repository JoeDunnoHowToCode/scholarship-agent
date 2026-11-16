"""一頁有幾個獎學金就存幾筆（A1 C，ADR-108）。真的資料庫，交易裡跑完就復原。"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.features.scholarships.models import Scholarship
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal


def scholarship(source_id: int, key: str) -> Scholarship:
    return Scholarship(name=f"Test {key}", source_id=source_id, key=key, countries=["FR"], degrees=["master"],
                       nationality_scope="all", nationalities=[], extracted={})


def test_one_source_can_hold_several_scholarships_with_different_keys() -> None:
    # 主角的 key 固定是 main（既有資料遷移後都是 main）；同一頁其他獎學金用正規化的名稱
    session = SessionLocal()
    try:
        source = Source(name="Test multi", url="https://test-multi.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        session.add_all([scholarship(source.id, "main"), scholarship(source.id, "regionalgrant")])
        session.flush()
        session.add(scholarship(source.id, "regionalgrant"))
        with pytest.raises(IntegrityError):
            session.flush()  # 同一來源、同一個 key 只能有一筆
    finally:
        session.rollback()
        session.close()
