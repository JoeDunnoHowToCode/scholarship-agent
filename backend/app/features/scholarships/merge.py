"""長文件合併規則（ADR-034）：把一節一節抽出的事實合併成一個獎學金。

規則見 docs/day-03.md「Claude 自行決定」第 9 點。
"""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.features.scholarships.schemas import (
    CategoryDraft,
    CategoryFact,
    Outline,
    RequirementDraft,
    ScholarshipDraft,
    SectionFacts,
)

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


def normalized(text: str) -> str:
    """忽略空白與全形半形差異，用來比對名稱與要求。"""
    return "".join(unicodedata.normalize("NFKC", text).split())


def same_name(a: str, b: str) -> bool:
    return normalized(a) == normalized(b)


def merge_category(
    name: str, explicit: list[CategoryFact], shared: list[CategoryFact]
) -> CategoryDraft:
    """一個類別：先用明確點名它的規則，沒有才用「全部」的規則。名額只看明確的規則。"""

    def first[T](items: Iterable[T | None]) -> T | None:
        return next((item for item in items if item is not None), None)

    def pick_list(attr: str) -> list[Any]:
        return unique(x for f in explicit for x in getattr(f, attr)) or unique(
            x for f in shared for x in getattr(f, attr)
        )

    return CategoryDraft(
        name=name,
        quota=first(f.quota for f in explicit),
        degrees=pick_list("degrees"),
        countries=pick_list("countries"),
        amount=first(f.amount for f in explicit) or first(f.amount for f in shared),
        eligibility="\n".join(
            unique(f.eligibility for f in explicit + shared if f.eligibility)
        )
        or None,
        evidence=first(f.evidence for f in explicit),
    )


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
        decider = min(
            sections, key=lambda s: order.index(getattr(s, name)), default=None
        )
        values[name] = getattr(decider, name) if decider else order[-1]
        values[evidence] = getattr(decider, evidence) if decider else None
    for name in LIST_FIELDS:
        values[name] = unique(item for s in sections for item in getattr(s, name))
    # 學位的引用：取第一個真的有抽到學位的那一節
    with_degrees = [s for s in sections if s.degrees]
    values["degrees_evidence"] = (
        with_degrees[0].degrees_evidence if with_degrees else None
    )
    for name in TEXT_FIELDS:
        texts = unique(getattr(s, name) for s in sections if getattr(s, name))
        values[name] = "\n".join(texts) or None

    facts = [f for s in sections for f in s.category_facts]
    shared = [f for f in facts if "all" in f.applies_to]
    warnings: list[str] = []
    if outline.category_names:
        known = [*outline.category_names, "all"]
        for name in unique(n for f in facts for n in f.applies_to):
            if not any(same_name(name, k) for k in known):
                warnings.append(f"未知類別：{name}")
        categories = [
            merge_category(
                name, [f for f in facts if any(same_name(name, n) for n in f.applies_to)], shared
            )
            for name in outline.category_names
        ]
    else:
        # 只有一種名額：用獎學金名稱當類別名稱，「全部」的規則就是它的規則
        categories = [merge_category(outline.name, shared, [])]
    # 文件要求：取聯集；類型、類別、要求都一樣（忽略空白）就算同一份
    requirements: dict[tuple[str, str, str], RequirementDraft] = {}
    for item in (r for s in sections for r in s.requirements):
        target = item.category
        if target and not any(same_name(target, n) for n in outline.category_names):
            if outline.category_names:
                warnings.append(f"未知類別：{target}")
            target = None  # 不能猜它指哪個類別，當成所有類別都要交
        key = (item.doc_type, normalized(target or ""), normalized(item.details or ""))
        requirements.setdefault(key, item.model_copy(update={"category": target}))

    # 類別沒有自己的學位或國家時，用整個獎學金的
    for category in categories:
        category.degrees = category.degrees or values["degrees"]
        category.countries = category.countries or values["countries"]

    draft = ScholarshipDraft(
        name=outline.name,
        name_zh=outline.name_zh,
        provider=outline.provider,
        categories=categories,
        requirements=list(requirements.values()),
        **values,
    )
    return MergeResult(draft, conflicts, warnings)
