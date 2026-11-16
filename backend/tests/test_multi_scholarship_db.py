"""一頁有幾個獎學金就存幾筆（A1 C，ADR-108）。真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.scholarships.extract import extract_source
from app.features.scholarships.models import Scholarship, ScholarshipStatus
from app.features.scholarships.schemas import OtherScholarship, ScholarshipDraft
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal
from tests.test_extract_build import DRAFT, PAGE, FakeLLM


def scholarship(source_id: int, key: str) -> Scholarship:
    return Scholarship(name=f"Test {key}", source_id=source_id, key=key, countries=["FR"], degrees=["master"],
                       nationality_scope="all", nationalities=[], extracted={})


def source_with_page(session: Session, tmp_path: Path, page: str = PAGE) -> Source:
    path = tmp_path / "page.html"
    path.write_text(page, encoding="utf-8")
    source = Source(name="Test multi page", url="https://test-multi-page.example/", kind=SourceKind.UNIVERSITY)
    session.add(source)
    session.flush()
    now = datetime.now(UTC)
    session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                         content_hash="8" * 64, file_path=str(path), http_status=200, etag=None, last_modified=None))
    session.flush()
    return source


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


def test_reextracting_the_page_updates_its_main_scholarship(tmp_path: Path) -> None:
    # 同一來源已經有其他獎學金時，重抽主角要更新 key=main 那一筆，不能隨便拿到第一筆
    session = SessionLocal()
    try:
        source = source_with_page(session, tmp_path)
        other = scholarship(source.id, "erasmusgrant")  # 依 (source_id, key) 索引排序時排在 main 前面
        main = scholarship(source.id, "main")
        session.add_all([other, main])
        session.flush()
        extract_source(session, FakeLLM(), source)  # type: ignore[arg-type]
        assert main.name == "Test Global Scholarship"
        assert other.name == "Test erasmusgrant"
    finally:
        session.rollback()
        session.close()


class MultiLLM(FakeLLM):
    """主角的抽取列出同一頁的其他獎學金；提示詞寫「只抽『某某』」時回傳那一個（假的 AI）。"""

    def __init__(self, others: list[str], focused_name: str | None = None) -> None:
        super().__init__(DRAFT.model_copy(update={
            "other_scholarships": [OtherScholarship(name=name, evidence=f"{name} is also offered") for name in others],
        }))
        self.focused_name = focused_name

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        if schema is ScholarshipDraft:
            for name in self.draft.other_scholarships:
                if f"只抽「{name.name}」" in prompt:
                    return DRAFT.model_copy(update={"name": self.focused_name or name.name})
        return super().extract(prompt, schema)


def test_other_scholarships_on_the_page_are_saved_and_archived_when_gone(tmp_path: Path) -> None:
    session = SessionLocal()
    try:
        source = source_with_page(session, tmp_path)
        extract_source(session, MultiLLM(["Regional Grant"]), source)  # type: ignore[arg-type]
        rows = {row.key: row for row in session.scalars(select(Scholarship).where(Scholarship.source_id == source.id))}
        assert sorted(rows) == ["main", "regionalgrant"]
        assert (rows["main"].name, rows["regionalgrant"].name) == ("Test Global Scholarship", "Regional Grant")
        assert rows["regionalgrant"].extracted["focus"] == "Regional Grant"
        # AI 這次寫成 Regional Grants：同一來源內名稱很像（相似度 ≥ 0.9）就是同一筆，不另外新增
        extract_source(session, MultiLLM(["Regional Grants"]), source, force=True)  # type: ignore[arg-type]
        keys = sorted(session.scalars(select(Scholarship.key).where(Scholarship.source_id == source.id)))
        assert keys == ["main", "regionalgrant"] and rows["regionalgrant"].name == "Regional Grants"
        # 頁面上不再出現：封存，不刪
        extract_source(session, MultiLLM([]), source, force=True)  # type: ignore[arg-type]
        assert rows["regionalgrant"].status == ScholarshipStatus.ARCHIVED
        assert rows["main"].status == ScholarshipStatus.ACTIVE
    finally:
        session.rollback()
        session.close()


def test_a_source_with_several_scholarships_is_checked_once_a_day() -> None:
    # 每天的檢查以來源為單位：同一來源有好幾筆獎學金也只排一次（頻率看主角那一筆）
    from app.features.pipeline.jobs import due_source_ids, taipei_date
    from app.features.sources.models import SourceStatus

    session = SessionLocal()
    try:
        source = Source(name="Test due", url="https://test-due.example/", kind=SourceKind.UNIVERSITY,
                        status=SourceStatus.APPROVED, enabled=True)
        session.add(source)
        session.flush()
        session.add_all([scholarship(source.id, "main"), scholarship(source.id, "regionalgrant")])
        session.flush()
        assert due_source_ids(session, taipei_date()).count(source.id) == 1
    finally:
        session.rollback()
        session.close()


class FakeEmbedder:
    """假的向量模型：每段文字回傳固定的向量。"""

    model_id = "fake-embedder"

    def embed_documents(self, items: list[tuple[str, str]]) -> list[list[float]]:
        from app.features.scholarships.models import EMBEDDING_DIMENSIONS

        return [[0.1] * EMBEDDING_DIMENSIONS for _ in items]


def test_every_scholarship_of_a_source_gets_a_vector() -> None:
    # 去重（ADR-097）用獎學金的向量比對；一頁有好幾筆時每一筆都要有
    from app.features.search.index import index_scholarship

    session = SessionLocal()
    try:
        source = Source(name="Test vectors", url="https://test-vectors.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        rows = [scholarship(source.id, "main"), scholarship(source.id, "regionalgrant")]
        session.add_all(rows)
        session.flush()
        assert index_scholarship(session, FakeEmbedder(), source) == 2  # type: ignore[arg-type]
        assert all(row.embed_model == "fake-embedder" for row in rows)
    finally:
        session.rollback()
        session.close()


def test_another_scholarship_without_amounts_or_dates_on_the_page_is_not_saved(tmp_path: Path) -> None:
    # ADR-108：只列出名字、簡介或連結的外部資助管道不是同一頁的另一個獎學金；
    # 11-17 重抽後拆出來的 150 筆有 41 筆沒有金額也沒有申請期，程式擋下來
    session = SessionLocal()
    try:
        source = source_with_page(session, tmp_path)
        llm = MultiLLM(["Campus France"])
        bare = DRAFT.model_copy(update={"name": "Campus France", "amounts": [], "windows": []})
        llm.extract = lambda prompt, schema: (  # type: ignore[method-assign]
            bare if schema is ScholarshipDraft and "只抽「Campus France」" in prompt else MultiLLM.extract(llm, prompt, schema)
        )
        extract_source(session, llm, source)  # type: ignore[arg-type]
        keys = sorted(session.scalars(select(Scholarship.key).where(Scholarship.source_id == source.id)))
        assert keys == ["main"]
    finally:
        session.rollback()
        session.close()
