"""候選來源的規則（ADR-078）：純邏輯，不連資料庫。"""

from datetime import UTC, datetime

from app.features.discovery.candidates import (
    EMPTY_LIMIT,
    WEEKLY_DECISIONS,
    Brief,
    Facts,
    budget,
    judge,
    next_empty,
    same_scholarship,
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


def brief(provider: str = "fcdo", countries: tuple[str, ...] = (), closes: tuple[str, ...] = (),
          embedding: list[float] | None = None) -> Brief:
    return Brief(provider, frozenset(countries), frozenset(closes), embedding)


def test_duplicates_are_found_from_content_not_from_the_domain() -> None:
    # 用 11-09 實際的配對設計（E＋D）
    near, far = [1.0, 0.0], [0.97, 0.243]  # 相似度 1.0 與約 0.97
    assert same_scholarship(brief(embedding=near), brief(embedding=far)) == "duplicate"  # 像 MER、master-cne
    # 國家和截止日都相同：就算沒有向量也是重複
    assert same_scholarship(brief(countries=("FR", "PL"), closes=("2027-02-15",)),
                            brief(countries=("FR", "PL"), closes=("2027-02-15",))) == "duplicate"
    # 國家不同或截止日不同：不同的獎學金（像 Université Côte d'Azur 的兩個學程）
    assert same_scholarship(brief(countries=("FR", "DE")), brief(countries=("FR", "IT"))) == "different"
    assert same_scholarship(brief(closes=("2027-03-06",)), brief(closes=("2027-02-28",))) == "different"
    # 不夠相似、資料又不夠：判斷不了，交給 AI（像 Chevening 總頁和台灣頁）
    assert same_scholarship(brief(countries=("GB",)), brief(countries=("GB",))) == "unclear"
    assert same_scholarship(brief(embedding=[1.0, 0.0]), brief(embedding=[0.9, 0.436])) == "unclear"  # 約 0.90


def test_only_the_same_provider_is_compared() -> None:
    imt = brief("imt atlantique", countries=("FR",), closes=("2027-02-15",))
    mer = brief("mer consortium", countries=("FR",), closes=("2027-02-15",))
    assert same_scholarship(imt, mer) == "different"
    unknown = brief("", countries=("FR",), closes=("2027-02-15",))
    assert same_scholarship(unknown, unknown) == "different"  # 沒抽到提供者：不比


def test_providers_match_when_one_name_contains_the_other() -> None:
    # 11-09 實際的 Chevening：總頁寫「… Office (FCDO) and partner organisations」，台灣頁寫「… Office」
    total = brief("foreigncommonwealthanddevelopmentofficefcdoandpartnerorganisations", countries=("GB",))
    taiwan = brief("foreigncommonwealthanddevelopmentoffice", countries=("GB",))
    assert same_scholarship(total, taiwan) == "unclear"  # 同一個提供者、資料不夠：交給 AI
    # 太短的名稱不算包含（例如 eu 會出現在很多名稱裡）
    assert same_scholarship(brief("eu", countries=("GB",)), brief("eucore", countries=("GB",))) == "different"
