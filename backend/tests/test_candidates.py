"""候選來源的規則（ADR-078）：純邏輯，不連資料庫。"""

from datetime import UTC, datetime

from app.features.discovery.candidates import (
    EMPTY_LIMIT,
    WEEKLY_DECISIONS,
    Facts,
    budget,
    judge,
    next_empty,
)

NOW = datetime(2026, 11, 8, tzinfo=UTC)
GOOD = Facts(
    countries=["SE"], degrees=["master"], degrees_check="supported",
    nationality_scope="all", nationalities=[], closes=[datetime(2027, 1, 15, tzinfo=UTC)],
)


def with_(**changes: object) -> Facts:
    return Facts(**{**GOOD.__dict__, **changes})  # type: ignore[arg-type]


def test_a_good_master_scholarship_in_europe_passes() -> None:
    assert judge(GOOD, NOW) == []


def test_each_rule_has_a_plain_reason() -> None:
    assert judge(with_(countries=["US"]), NOW) == ["留學國家不在歐洲"]
    assert judge(with_(countries=[]), NOW) == ["留學國家不在歐洲"]  # 沒寫國家也不收
    assert judge(with_(degrees=["phd"]), NOW) == ["原文沒有可核對的碩士學位"]
    assert judge(with_(degrees_check="not_supported"), NOW) == ["原文沒有可核對的碩士學位"]
    assert judge(with_(nationality_scope="excluded", nationalities=["TW"]), NOW) == ["國籍規定排除台灣"]
    assert judge(with_(nationality_scope="listed", nationalities=["FR"]), NOW) == ["國籍規定排除台灣"]
    assert judge(with_(closes=[datetime(2025, 10, 1, tzinfo=UTC)]), NOW) == ["申請期都是一年多以前的"]


def test_unclear_information_does_not_reject() -> None:
    # 原文沒寫國籍、沒寫申請期：不排除（spec：全部列出、不過濾，評分時再標「待確認」）
    assert judge(with_(nationality_scope="unclear"), NOW) == []
    assert judge(with_(nationality_scope="listed", nationalities=[]), NOW) == []  # 有限制但不知道哪些國家
    assert judge(with_(closes=[]), NOW) == []
    # 舊的截止日之外還有新的：不算舊資料
    assert judge(with_(closes=[datetime(2025, 1, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)]), NOW) == []


def test_three_empty_extractions_in_a_row_disable_the_source() -> None:
    count, disable = 0, False
    for _ in range(EMPTY_LIMIT - 1):
        count, disable = next_empty(count, valid=False)
    assert (count, disable) == (EMPTY_LIMIT - 1, False)
    assert next_empty(count, valid=False) == (EMPTY_LIMIT, True)
    assert next_empty(count, valid=True) == (0, False)  # 中間抽到一次有效的就重新算


def test_weekly_budget() -> None:
    assert budget(0) == WEEKLY_DECISIONS
    assert budget(WEEKLY_DECISIONS - 3) == 3
    assert budget(WEEKLY_DECISIONS + 5) == 0
