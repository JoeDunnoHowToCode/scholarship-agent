"""評估的指標（ADR-098）：純函式，不連資料庫、不呼叫 AI。"""

from typing import Any

import pytest

from app.features.evaluation.metrics import (
    agreement,
    disagreements,
    grounded,
    incomplete,
    tally,
)


def record(source_id: int, deadlines: list[str], nationality: str = "all:", ok: bool = True,
           statuses: dict[str, Any] | None = None) -> dict[str, Any]:
    verification = {"nationality": "supported", "degrees": "supported",
                    "deadlines": ["supported"] * len(deadlines), "amounts": ["supported"]}
    return {
        "source_id": source_id, "name": f"S{source_id}", "url": f"https://s{source_id}.example/",
        "ok": ok, "error": None if ok else "ExtractionError",
        "fields": {"deadlines": deadlines, "nationality": nationality, "degrees": ["master"], "amounts": ["living:1400:EUR:month"]},
        "evidence": {"deadlines": f"Apply by {deadlines}", "nationality": "Open to all", "degrees": "Master", "amounts": "1,400 EUR"},
        "verification": {**verification, **(statuses or {})},
        "issues": 1,
    }


def test_grounded_rates_per_field() -> None:
    rows = [
        record(1, ["2027-01-15"]),
        record(2, ["2027-02-01", "2027-03-01"], statuses={"nationality": "catalogue", "deadlines": ["supported", "not_supported"]}),
        record(3, [], statuses={"nationality": "not_supported", "degrees": "degree_not_in_quote", "amounts": []}),
        record(4, ["2027-01-15"], ok=False),  # 抽取失敗的不算
    ]
    rates = grounded(rows)
    assert rates["nationality"] == pytest.approx(2 / 3)  # catalogue（目錄當依據）也算有根據
    assert rates["degrees"] == pytest.approx(2 / 3)
    assert rates["deadlines"] == pytest.approx(2 / 3)  # 3 個申請窗口裡 2 個
    assert rates["amounts"] == pytest.approx(1.0)  # 2 筆金額都有根據


def test_incomplete_deadlines() -> None:
    rows = [record(1, ["2027-01-15"], statuses={"deadlines": ["incomplete"]}), record(2, ["2027-02-01"])]
    assert incomplete(rows) == pytest.approx(0.5)


def test_agreement_counts_only_sources_both_extracted() -> None:
    first = [record(1, ["2027-01-15"]), record(2, ["2027-02-01"]), record(3, ["2027-03-01"])]
    second = [record(1, ["2027-01-15"]), record(2, ["2027-02-05"]), record(3, ["2027-03-01"], ok=False)]
    rates = agreement(first, second)
    assert rates["deadlines"] == pytest.approx(0.5)  # 來源 3 第二次失敗，不算
    assert rates["nationality"] == pytest.approx(1.0)
    assert rates["all"] == pytest.approx(0.5)  # 四個欄位全部一樣的比例


def test_disagreements_pick_one_per_source_up_to_the_limit() -> None:
    first = [record(n, ["2027-01-15"], nationality="all:") for n in range(1, 15)]
    second = [record(n, ["2027-01-20"], nationality="listed:FR") for n in range(1, 15)]
    picked = disagreements(first, second, limit=10)
    assert len(picked) == 10
    assert len({p["source_id"] for p in picked}) == 10  # 每個來源最多一筆
    assert picked[0]["field"] == "deadlines"  # 截止日優先
    assert (picked[0]["first"], picked[0]["second"]) == (["2027-01-15"], ["2027-01-20"])
    assert picked[0]["first_evidence"] and picked[0]["url"]
    # 兩邊都沒抽到的欄位不算不一致
    empty = disagreements([record(1, [])], [record(1, [])])
    assert empty == []


def test_tally_reads_the_filled_answers() -> None:
    text = "### 1\n誰對：A\n### 2\n誰對：B\n### 3\n誰對：都對\n### 4\n誰對：\n### 5\n誰對：都錯\n"
    assert tally(text) == {"A": 1, "B": 1, "都對": 1, "都錯": 1, "未填": 1}
