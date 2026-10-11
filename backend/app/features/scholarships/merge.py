"""長文件合併規則（ADR-034）：把一節一節抽出的事實合併成一個獎學金。

規則見 docs/day-03.md「Claude 自行決定」第 9 點。
"""

from dataclasses import dataclass, field
from typing import Any

from app.features.scholarships.schemas import Outline, ScholarshipDraft, SectionFacts

# 「事實」欄位：只該有一個值。取第一個有值的；後面出現不同的值就記成衝突
# 每個欄位配上它的引用欄位，引用跟著值一起取
FACT_FIELDS: dict[str, str | None] = {
    "deadline": "deadline_evidence",
    "deadline_timezone": None,
    "intake": None,
    "requires_admission": None,
}


@dataclass
class MergeResult:
    draft: ScholarshipDraft
    conflicts: list[str] = field(default_factory=list)  # 有衝突的欄位名稱
    warnings: list[str] = field(default_factory=list)


def merge_sections(outline: Outline, sections: list[SectionFacts]) -> MergeResult:
    values: dict[str, Any] = {}
    conflicts: list[str] = []
    for name, evidence in FACT_FIELDS.items():
        found = [s for s in sections if getattr(s, name) is not None]
        values[name] = getattr(found[0], name) if found else None
        if evidence:
            values[evidence] = getattr(found[0], evidence) if found else None
        if len({getattr(s, name) for s in found}) > 1:
            conflicts.append(name)

    draft = ScholarshipDraft(
        name=outline.name,
        name_zh=outline.name_zh,
        provider=outline.provider,
        countries=[],
        degrees=[],
        degrees_evidence=None,
        fields=[],
        coverage=None,
        amount=None,
        taiwan_eligibility="unclear",
        taiwan_evidence=None,
        nationality_scope="unclear",
        nationality_evidence=None,
        taiwan_conditions=None,
        language_requirements=None,
        other_eligibility=None,
        categories=[],
        requirements=[],
        **values,
    )
    return MergeResult(draft, conflicts)
