"""抽取 schema 的單元測試（ADR-045 格式限制）。"""

from typing import Any

import pytest
from pydantic import ValidationError

from app.features.scholarships import schemas
from app.features.scholarships.schemas import (
    AmountDraft,
    Outline,
    ScholarshipDraft,
    WindowDraft,
)

FACT: dict[str, Any] = {
    "quota": None, "degrees": [], "countries": [], "amount": None,
    "eligibility": None, "evidence": None,
}
REQUIREMENT: dict[str, Any] = {
    "doc_type": "cv", "details": None, "required": None, "count": None, "evidence": None,
}
SECTION: dict[str, Any] = {
    "provider": None, "countries": [], "degrees": [], "degrees_evidence": None, "fields": [],
    "coverage": None, "amounts": [], "nationality_scope": "unclear", "nationalities": [],
    "nationality_evidence": None, "nationality_conditions": None,
    "language_requirements": None, "other_eligibility": None, "requires_admission": None,
    "total_quota": None, "windows": [],
}


def test_section_schema_only_accepts_outline_category_names() -> None:
    # 第二輪的類別名稱只能從第一輪的清單挑（或 all），模型就寫不出「北歐」這種對不上的名稱
    schema = schemas.section_schema(["北歐國家", "一般學群"])
    ok = schema.model_validate({
        **SECTION,
        "category_facts": [{**FACT, "applies_to": ["北歐國家", "all"]}],
        "requirements": [{**REQUIREMENT, "category": "一般學群"}],
    })
    assert isinstance(ok, schemas.SectionFacts)
    assert "北歐國家" in str(schema.model_json_schema())  # 選單真的出現在送給模型的 schema 裡
    with pytest.raises(ValidationError):
        schema.model_validate({
            **SECTION, "category_facts": [{**FACT, "applies_to": ["北歐"]}], "requirements": [],
        })
    with pytest.raises(ValidationError):
        schema.model_validate({
            **SECTION, "category_facts": [],
            "requirements": [{**REQUIREMENT, "category": "藝術學群"}],
        })


def test_old_extractions_without_the_new_fields_keep_working() -> None:
    # ADR-105：新欄位在重抽前不存在；沒有時的行為要和以前一樣（申請獎學金的日期、這個獎學金的錢、不清楚有沒有開）
    window = WindowDraft.model_validate({
        "label": None, "intake": None, "opens_year": None, "opens_month": None, "opens_day": None,
        "closes_year": 2027, "closes_month": 1, "closes_day": 15, "closes_time": None, "timezone": None,
        "nationality_scope": "all", "nationalities": [], "funding": "any", "evidence": "15 January 2027",
    })
    amount = AmountDraft.model_validate({"value": 1400, "currency": "EUR", "period": "month",
                                         "kind": "living_allowance", "applies_to": None, "evidence": "x"})
    outline = Outline.model_validate({"name": "Test", "name_zh": None, "provider": None, "category_names": []})
    assert (window.kind, amount.for_this, outline.offered, outline.offered_evidence) == (
        "scholarship", True, "unclear", None,
    )
    assert "offered" in ScholarshipDraft.model_fields and "offered_evidence" in ScholarshipDraft.model_fields
