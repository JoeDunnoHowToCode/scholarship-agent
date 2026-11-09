"""評估指令的純邏輯（ADR-098）：挑樣本、整理一次抽取的紀錄、報告與抽查清單。不連資料庫、不呼叫 AI。"""

from typing import Any

from app.features.evaluation.metrics import tally
from app.features.evaluation.run import (
    disagreements_markdown,
    pick_sample,
    record_of,
    report_markdown,
)
from app.features.scholarships.schemas import ScholarshipDraft

SOURCE = {"source_id": 7, "name": "Test Scholarship", "url": "https://test.example/"}


def draft() -> ScholarshipDraft:
    return ScholarshipDraft.model_validate({
        "name": "Test Scholarship", "name_zh": None, "provider": "Test University", "countries": ["SE"],
        "degrees": ["phd", "master"], "degrees_evidence": "Master and PhD", "fields": [], "coverage": None,
        "amounts": [{"value": 1400, "currency": "EUR", "period": "month", "kind": "living_allowance",
                     "applies_to": None, "evidence": "1,400 EUR per month"}],
        "nationality_scope": "listed", "nationalities": ["TW", "FR"], "nationality_evidence": "France and Taiwan",
        "nationality_conditions": None, "language_requirements": None, "other_eligibility": None,
        "requires_admission": None, "total_quota": None, "categories": [], "requirements": [],
        "windows": [{"label": None, "intake": "2027", "opens_year": None, "opens_month": None, "opens_day": None,
                     "closes_year": 2027, "closes_month": 1, "closes_day": 15, "closes_time": None, "timezone": None,
                     "nationality_scope": "all", "nationalities": [], "funding": "scholarship",
                     "evidence": "Apply by 15 January 2027"}],
    })


def test_the_sample_is_fixed_and_keeps_every_non_erasmus_source() -> None:
    non_erasmus, erasmus = [3, 1, 2], list(range(100, 200))
    first = pick_sample(non_erasmus, erasmus, n=40)
    assert first == pick_sample(non_erasmus, list(reversed(erasmus)), n=40)  # 順序不同也挑到同一批
    assert set(non_erasmus) <= set(first) and len(first) == 3 + 40
    assert first == sorted(first)
    assert len(pick_sample([], [100, 101], n=40)) == 2  # 不夠 40 個就全部


def test_a_record_keeps_only_what_the_comparison_needs() -> None:
    extracted: dict[str, Any] = {"verification": {"nationality": "supported", "degrees": "supported",
                                                  "deadlines": ["supported"], "amounts": ["supported"],
                                                  "categories": {}, "issues": ["x", "y"]}}
    row = record_of(SOURCE, "m1", 1, draft(), extracted, 2.5, 0.001, None)
    assert row.get("ok") is True
    assert (row["model"], row["round"], row["source_id"]) == ("m1", 1, 7)
    assert row["fields"] == {
        "deadlines": ["2027-01-15"], "nationality": "listed:FR,TW", "degrees": ["master", "phd"],
        "amounts": ["living_allowance:1400:EUR:month"],
    }
    assert row["evidence"]["deadlines"] == "Apply by 15 January 2027" and row["issues"] == 2
    failed = record_of(SOURCE, "m1", 1, None, None, 1.0, 0.0, "ExtractionError")
    assert (failed["ok"], failed["error"]) == (False, "ExtractionError")


def test_report_has_numbers_and_the_checklist_can_be_tallied() -> None:
    ok = record_of(SOURCE, "m1", 1, draft(), {"verification": {"nationality": "supported", "degrees": "supported",
                                                               "deadlines": ["supported"], "amounts": ["supported"],
                                                               "issues": []}}, 2.0, 0.002, None)
    report = report_markdown({"m1": [[ok], [ok]], "m2": [[ok], [ok]]}, "2026-11-10")
    assert "# 模型評估：2026-11-10" in report
    assert "| m1 |" in report and "| m2 |" in report
    assert "Apply by" not in report  # 報告不放原文引用（repo 是公開的）
    items = [{"source_id": 7, "name": "Test", "url": "https://test.example/", "field": "deadlines",
              "first": ["2027-01-15"], "second": ["2027-01-20"], "first_evidence": "Apply by 15 January 2027",
              "second_evidence": "Apply by 20 January 2027"}]
    checklist = disagreements_markdown(items, "m1", "m2")
    assert "https://test.example/" in checklist and "Apply by 15 January 2027" in checklist
    assert tally(checklist) == {"A": 0, "B": 0, "都對": 0, "都錯": 0, "未填": 1}
