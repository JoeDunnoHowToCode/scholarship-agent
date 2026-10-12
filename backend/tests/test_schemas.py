"""抽取 schema 的單元測試（ADR-045 格式限制）。"""

from typing import Any

import pytest
from pydantic import ValidationError

from app.features.scholarships import schemas

FACT: dict[str, Any] = {
    "quota": None, "degrees": [], "countries": [], "amount": None,
    "eligibility": None, "evidence": None,
}
REQUIREMENT: dict[str, Any] = {
    "doc_type": "cv", "details": None, "required": None, "count": None, "evidence": None,
}
SECTION: dict[str, Any] = {
    "provider": None, "countries": [], "degrees": [], "degrees_evidence": None, "fields": [],
    "coverage": None, "amount": None, "nationality_scope": "unclear", "nationalities": [],
    "nationality_evidence": None, "nationality_conditions": None,
    "language_requirements": None, "other_eligibility": None, "requires_admission": None,
    "intake": None, "total_quota": None, "deadline_year": None, "deadline_month": None,
    "deadline_day": None, "deadline_timezone": None, "deadline_evidence": None,
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
