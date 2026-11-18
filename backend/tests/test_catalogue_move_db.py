"""EACEA 學程以目錄為準（11-09 使用者選 D）：學程在目錄裡換了網址，就更新原本那一筆，不新增。真的資料庫，交易裡跑完就復原。"""

from sqlalchemy import select

from app.features.sources.catalogue import (
    CATALOGUE_URL,
    CatalogueEntry,
    upsert_programme,
)
from app.features.sources.models import Discovery, Source, SourceKind
from app.shared.db import SessionLocal


def test_a_programme_that_changed_its_url_keeps_its_source() -> None:
    session = SessionLocal()
    try:
        catalogue = session.scalars(select(Source).where(Source.url == CATALOGUE_URL)).one()
        old = Source(name="Test Joint Master in Moving Sites", url="https://test-moving-old.example/",
                     kind=SourceKind.UNIVERSITY, parent_id=catalogue.id, discovery=Discovery.CATALOGUE,
                     fail_days=4, unreachable_since=None, last_error="gaierror: nodename nor servname provided")
        session.add(old)
        session.flush()
        moved = CatalogueEntry(name="TEST JOINT MASTER IN MOVING SITES", url="https://test-moving-new.example/")
        listed = {moved.url}  # 舊網址已經不在目錄裡
        assert upsert_programme(session, catalogue.id, moved, listed) == "moved"
        assert (old.url, old.fail_days, old.last_error) == ("https://test-moving-new.example/", 0, None)
        assert session.scalars(select(Source).where(Source.url == "https://test-moving-new.example/")).one() is old
        # 再跑一次：已經是這個網址，什麼都不變
        assert upsert_programme(session, catalogue.id, moved, listed) == "kept"
    finally:
        session.rollback()
        session.close()


def test_a_new_programme_is_added_and_a_listed_twin_is_not_moved() -> None:
    session = SessionLocal()
    try:
        catalogue = session.scalars(select(Source).where(Source.url == CATALOGUE_URL)).one()
        twin = Source(name="Test Twin Programme", url="https://test-twin-a.example/", kind=SourceKind.UNIVERSITY,
                      parent_id=catalogue.id, discovery=Discovery.CATALOGUE)
        session.add(twin)
        session.flush()
        other = CatalogueEntry(name="Test Twin Programme", url="https://test-twin-b.example/")
        # 舊網址還在目錄裡（目錄同時列了兩個網址）：不搬，另外新增
        assert upsert_programme(session, catalogue.id, other, {twin.url, other.url}) == "added"
        assert twin.url == "https://test-twin-a.example/"
        fresh = CatalogueEntry(name="Test Brand New Programme", url="https://test-brand-new.example/")
        assert upsert_programme(session, catalogue.id, fresh, {fresh.url}) == "added"
    finally:
        session.rollback()
        session.close()


def test_the_same_site_written_with_https_or_www_is_not_added_again() -> None:
    # 總檢查 A3：目錄同時列了 http://www.fipdes.eu/ 和 https://www.fipdes.eu/（名稱略有不同），
    # 以前用網址字串比對，新增了第二個來源，同一個網站每天抓兩次、抽兩次
    session = SessionLocal()
    try:
        catalogue = session.scalars(select(Source).where(Source.url == CATALOGUE_URL)).one()
        first = Source(name="Test Food Innovation Master", url="http://www.test-same-site.example/",
                       kind=SourceKind.UNIVERSITY, parent_id=catalogue.id, discovery=Discovery.CATALOGUE)
        session.add(first)
        session.flush()
        again = CatalogueEntry(name="Test Joint Master in Food Innovation", url="https://test-same-site.example")
        assert upsert_programme(session, catalogue.id, again, {first.url, again.url}) == "kept"
        same_site = session.scalars(select(Source).where(Source.url.ilike("%test-same-site.example%"))).all()
        assert same_site == [first]
    finally:
        session.rollback()
        session.close()
