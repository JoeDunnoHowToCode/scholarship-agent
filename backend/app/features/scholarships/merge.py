"""長文件合併規則（ADR-034）：把一節一節抽出的事實合併成一個獎學金。

規則見 docs/day-03.md「Claude 自行決定」第 9 點。
"""

from collections.abc import Iterable
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
# 有優先順序的欄位：取排在最前面的答案，引用跟著做出決定的那一節
PRIORITY_FIELDS: dict[str, tuple[str, list[str]]] = {
    "taiwan_eligibility": ("taiwan_evidence", ["no", "yes", "unclear"]),
    "nationality_scope": (
        "nationality_evidence",
        ["taiwan_specific", "listed_countries", "worldwide", "unclear"],
    ),
}
# 清單欄位：取聯集，保持第一次出現的順序
LIST_FIELDS = ["countries", "degrees", "fields"]
# 文字欄位：不同節可能各寫一部分，把不同的內容串起來
TEXT_FIELDS = [
    "coverage",
    "amount",
    "taiwan_conditions",
    "language_requirements",
    "other_eligibility",
]


@dataclass
class MergeResult:
    draft: ScholarshipDraft
    conflicts: list[str] = field(default_factory=list)  # 有衝突的欄位名稱
    warnings: list[str] = field(default_factory=list)


def unique[T](items: Iterable[T]) -> list[T]:
    """去掉重複、保持順序。"""
    return list(dict.fromkeys(items))


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

    for name, (evidence, order) in PRIORITY_FIELDS.items():
        decider = min(sections, key=lambda s: order.index(getattr(s, name)), default=None)
        values[name] = getattr(decider, name) if decider else order[-1]
        values[evidence] = getattr(decider, evidence) if decider else None
    for name in LIST_FIELDS:
        values[name] = unique(item for s in sections for item in getattr(s, name))
    for name in TEXT_FIELDS:
        texts = unique(getattr(s, name) for s in sections if getattr(s, name))
        values[name] = "\n".join(texts) or None

    draft = ScholarshipDraft(
        name=outline.name,
        name_zh=outline.name_zh,
        provider=outline.provider,
        degrees_evidence=None,
        categories=[],
        requirements=[],
        **values,
    )
    return MergeResult(draft, conflicts)
