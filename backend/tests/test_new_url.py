"""找新網址（ADR-080）：換網址前確認是同一個學程。"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.features.discovery.new_url import apply_new_url, same_programme
from app.features.notifications.models import Event
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal

CYBER = ["Master of Applied Cybersecurity", "Erasmus Mundus Joint Master Degree Scholarship – CyberMACS"]


def test_same_programme_when_name_and_provider_appear() -> None:
    page = "CyberMACS – Erasmus Mundus Master of Applied Cybersecurity. Offered by the CyberMACS Consortium."
    assert same_programme(CYBER, "CyberMACS Consortium", page) is True


def test_names_match_ignoring_case_and_punctuation() -> None:
    page = "Welcome to RE PLAY - European Joint Masters in Games! Applications open soon."
    assert same_programme(["RE_PLAY: EUROPEAN JOINT MASTERS IN GAMES"], None, page) is True


def test_a_different_programme_is_not_the_same() -> None:
    page = "Erasmus Mundus Master in Data Science. Offered by the DSE Consortium."
    assert same_programme(CYBER, "CyberMACS Consortium", page) is False


def test_the_distinctive_provider_word_must_appear() -> None:
    # 名稱對上了，但主辦單位（波爾圖大學）沒出現：可能是別人轉貼的頁面，不換
    page = "Master of Applied Cybersecurity scholarships explained by a blog."
    assert same_programme(CYBER, "Universidade do Porto", page) is False
    # 主辦單位只有通用的字（European Commission）：只看名稱
    assert same_programme(CYBER, "European Commission", page) is True


def test_a_matching_new_url_replaces_the_old_one_and_notifies() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        source = Source(
            name="Master of Applied Cybersecurity", url="https://old-cybermacs.example/", kind=SourceKind.UNIVERSITY,
            fail_days=5, last_failed_on=now.date(), unreachable_since=now.date(),
        )
        session.add(source)
        session.flush()
        page = "CyberMACS: Master of Applied Cybersecurity. Erasmus Mundus programme."
        assert apply_new_url(session, source, "https://cybermacs.example/", page, now) is True
        assert source.url == "https://cybermacs.example/"
        assert (source.fail_days, source.last_failed_on, source.unreachable_since) == (0, None, None)
        titles = [e.payload["title"] for e in session.scalars(select(Event).where(Event.dedup_key.like(f"new-url:{source.id}:%")))]
        assert titles == ["找到新網址：Master of Applied Cybersecurity"]
    finally:
        session.rollback()
        session.close()


def test_a_different_programme_is_not_applied_but_reported() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        source = Source(
            name="Master of Applied Cybersecurity", url="https://old-cybermacs-2.example/", kind=SourceKind.UNIVERSITY,
            fail_days=5, unreachable_since=now.date(),
        )
        session.add(source)
        session.flush()
        assert apply_new_url(session, source, "https://data-science.example/", "Master in Data Science", now) is False
        assert source.url == "https://old-cybermacs-2.example/" and source.unreachable_since == now.date()
        titles = [e.payload["title"] for e in session.scalars(select(Event).where(Event.dedup_key.like(f"new-url:{source.id}:%")))]
        assert titles == ["新網址對不上，沒有換：Master of Applied Cybersecurity"]
    finally:
        session.rollback()
        session.close()


def test_long_official_names_match_by_their_distinctive_words() -> None:
    # 11-08 實跑：agent 找到 SERP 的新官網，網頁寫的是學程名稱的後半段，完整名稱沒有出現，原本的檢查誤判成對不上
    name = "Erasmus Mundus Joint Master's programme in Surface, Electro, Radiation, and Photo-chemistry"
    page = (
        "Erasmus Mundus SERP Master About us General description Partners universities. "
        "Programme overview “Surface, Electro-, Radiation, and Photo-Chemistry” The SERP+ master is a two-year programme."
    )
    assert same_programme([name, "master-serp.eu"], None, page) is True
    # 只出現其中一部分的字（Surface、Chemistry）不算
    assert same_programme([name], None, "Surface chemistry research group news") is False
