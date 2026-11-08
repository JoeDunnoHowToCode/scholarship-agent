"""找新網址（ADR-080）：換網址前確認是同一個學程。"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.features.discovery.new_url import apply_new_url, decide_new_url, same_programme
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


def test_a_url_that_differs_only_by_the_trailing_slash_is_already_taken() -> None:
    # 11-08 實跑：EACEA 目錄已經把 SERP 的新網址 https://master-serp.com/ 加成另一個來源；
    # agent 提議 https://master-serp.com（沒有結尾的 /），不能再換一次造成重複
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        session.add(Source(name="SERP new", url="https://test-serp-new.example/", kind=SourceKind.UNIVERSITY))
        old = Source(name="Surface Electro Radiation Photo chemistry", url="https://test-serp-old.example/",
                     kind=SourceKind.UNIVERSITY, unreachable_since=now.date())
        session.add(old)
        session.flush()
        page = "Surface, Electro-, Radiation, and Photo-Chemistry master"
        replaced, reason = decide_new_url(session, old, "https://test-serp-new.example", page)
        assert (replaced, old.url) == (False, "https://test-serp-old.example/")
        assert "另一個來源" in reason
    finally:
        session.rollback()
        session.close()


def test_old_source_is_disabled_when_the_catalogue_already_has_the_new_url() -> None:
    # 11-08 使用者選 B：目錄已經把新網址加成另一個來源，而且是同一個學程，舊來源自動停用並註明被誰取代
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        new = Source(name="Surface Electro Radiation Photo chemistry (new)", url="https://test-serp-b-new.example/",
                     kind=SourceKind.UNIVERSITY)
        old = Source(name="Surface Electro Radiation Photo chemistry", url="https://test-serp-b-old.example/",
                     kind=SourceKind.UNIVERSITY, unreachable_since=now.date())
        session.add_all([new, old])
        session.flush()
        page = "Surface, Electro-, Radiation, and Photo-Chemistry master"
        replaced, reason = decide_new_url(session, old, "https://test-serp-b-new.example", page)
        assert replaced is False and f"#{new.id}" in reason
        assert (old.enabled, old.review_note) == (False, f"已由 #{new.id} 取代")
        assert old.disabled_at is not None
        # 不是同一個學程（只是網址被別的來源用了）：不停用
        other = Source(name="Master of Applied Cybersecurity", url="https://test-cyber-b.example/",
                       kind=SourceKind.UNIVERSITY, unreachable_since=now.date())
        session.add(other)
        session.flush()
        decide_new_url(session, other, "https://test-serp-b-new.example/", page)
        assert other.enabled is True
    finally:
        session.rollback()
        session.close()
