"""長文件合併規則（ADR-034）：把一節一節抽出的事實合併成一個獎學金。

規則見 docs/day-03.md「Claude 自行決定」第 9 點。
"""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.features.scholarships import rules
from app.features.scholarships.schemas import (
    AmountDraft,
    CategoryDraft,
    CategoryFact,
    Outline,
    OutlineCategory,
    RequirementDraft,
    ScholarshipDraft,
    SectionFacts,
    WindowDraft,
)

# 「事實」欄位：只該有一個值。取第一個有值的；後面出現不同的值就記成衝突
# 每個欄位配上它的引用欄位，引用跟著值一起取
FACT_FIELDS: dict[str, str | None] = {
    "total_quota": None,
    "requires_admission": None,
}
# 有優先順序的欄位：取排在最前面的答案，引用跟著做出決定的那一節
PRIORITY_FIELDS: dict[str, tuple[str, list[str]]] = {
    # ADR-043：列出限定國家的說法最嚴格，優先採用
    "nationality_scope": ("nationality_evidence", ["listed", "excluded", "all", "unclear"]),
}
# 清單欄位：取聯集，保持第一次出現的順序
LIST_FIELDS = ["countries", "degrees", "fields"]
# 文字欄位：不同節可能各寫一部分，把不同的內容串起來
TEXT_FIELDS = [
    "coverage",
    "amount",
    "nationality_conditions",
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


def has_degree_rule(fact: CategoryFact) -> bool:
    """這張卡的學位算不算數：有學位，而且引用（如果有）真的提到學位。

    教育部北歐的例子：第二輪把學位寫在名額那張卡上，引用只講名額，
    這種卡的學位沒有依據，不能蓋掉第一輪有依據的學位（ADR-046）。
    """
    if not fact.degrees:
        return False
    if fact.evidence is None:
        return True
    return any(rules.degree_supported(d, [fact.evidence]) for d in rules.DEGREE_KEYWORDS)


def merge_category(
    name: str,
    explicit: list[CategoryFact],
    shared: list[CategoryFact],
    detail: OutlineCategory | None = None,
) -> CategoryDraft:
    """一個類別：明確點名它的規則 > 第一輪讀全文的類別資料 > 「全部」的規則。"""

    def first[T](items: Iterable[T | None]) -> T | None:
        return next((item for item in items if item is not None), None)

    def pick_list(attr: str) -> list[Any]:
        return (
            unique(x for f in explicit for x in getattr(f, attr))
            or (list(getattr(detail, attr)) if detail else [])
            or unique(x for f in shared for x in getattr(f, attr))
        )

    # 名額：只取「只點名這一個類別」的規則（點名多個類別的規則，名額是那幾類的總數），
    # 沒有才用第一輪的；名額的引用跟著名額從哪裡來
    quota_facts = [f for f in explicit if len(f.applies_to) == 1 and f.quota is not None]
    quota, quota_evidence = (
        (quota_facts[0].quota, quota_facts[0].evidence)
        if quota_facts
        else (detail.quota, detail.quota_evidence) if detail else (None, None)
    )
    # 學位：明確點名的規則 > 第一輪 > 「全部」的規則；學位的引用與條件跟著學位從哪裡來
    explicit_degrees = [f for f in explicit if has_degree_rule(f)]
    shared_degrees = [f for f in shared if has_degree_rule(f)]
    degree_conditions: str | None
    if explicit_degrees or not (detail and detail.degrees):
        source = explicit_degrees or shared_degrees
        degrees_evidence = first(f.evidence for f in source)
        degree_conditions = "\n".join(unique(f.degree_conditions for f in source if f.degree_conditions))
    else:
        degrees_evidence, degree_conditions = detail.degrees_evidence, detail.degree_conditions

    return CategoryDraft(
        name=name,
        quota=quota,
        degrees=unique(x for f in explicit_degrees for x in f.degrees)
        or (list(detail.degrees) if detail else [])
        or unique(x for f in shared_degrees for x in f.degrees),
        countries=pick_list("countries"),
        amount=first(f.amount for f in explicit) or first(f.amount for f in shared),
        eligibility="\n".join(
            unique(f.eligibility for f in explicit + shared if f.eligibility)
        )
        or None,
        quota_evidence=quota_evidence,
        degrees_evidence=degrees_evidence,
        degree_conditions=degree_conditions or None,
    )


def combine(first: RequirementDraft, second: RequirementDraft) -> RequirementDraft:
    """同一份文件出現兩次：保留寫得比較詳細的要求；份數取有寫的；任一處說必要就是必要。"""
    longer = second if len(second.details or "") > len(first.details or "") else first
    required = True if True in (first.required, second.required) else first.required
    if required is None:
        required = second.required
    return longer.model_copy(
        update={
            "count": first.count if first.count is not None else second.count,
            "required": required,
        }
    )


def completeness(window: WindowDraft) -> int:
    """窗口寫了多少資訊：有值的欄位數，加上有寫明的申請類型。"""
    filled = sum(value not in (None, [], "") for value in window.model_dump().values())
    return filled + (window.funding != "any")


def merge_amounts(sections: list[list[AmountDraft]]) -> list[AmountDraft]:
    """各節抽到的金額取聯集（ADR-070）：數字、幣別、期間、用途、適用對象都一樣的，只留第一次出現的那筆與它的引用。"""
    kept: dict[tuple[Any, ...], AmountDraft] = {}
    for amount in (a for section in sections for a in section):
        key = (amount.value, amount.currency.upper(), amount.period, amount.kind, normalized(amount.applies_to or ""))
        kept.setdefault(key, amount)
    return list(kept.values())


def dedupe_windows(windows: list[WindowDraft]) -> list[WindowDraft]:
    """截止日同一天、適用國籍一樣，就是同一個窗口：留下資訊最完整的那筆（一樣完整時留先出現的）。

    教育部的例子：2/13 的截止日在三個章節各抽到一次，寫法略有不同。
    """
    kept: dict[tuple[Any, ...], WindowDraft] = {}
    for w in windows:
        window_key = (
            (w.closes_year, w.closes_month, w.closes_day),
            w.nationality_scope,
            tuple(sorted(normalized(n) for n in w.nationalities)),
        )
        if window_key not in kept or completeness(w) > completeness(kept[window_key]):
            kept[window_key] = w
    return list(kept.values())


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

    # 申請窗口（ADR-047）：每一節找到的都收下，同一個截止日只留一筆
    values["windows"] = dedupe_windows([w for s in sections for w in s.windows])

    for name, (evidence, order) in PRIORITY_FIELDS.items():
        decider = min(
            sections, key=lambda s: order.index(getattr(s, name)), default=None
        )
        values[name] = getattr(decider, name) if decider else order[-1]
        values[evidence] = getattr(decider, evidence) if decider else None
    # 國家清單：只取和最後決定的範圍同一類的那些節
    values["nationalities"] = unique(
        n for s in sections if s.nationality_scope == values["nationality_scope"]
        for n in s.nationalities
    )
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
                name,
                [f for f in facts if any(same_name(name, n) for n in f.applies_to)],
                shared,
                next((d for d in outline.category_details if same_name(d.name, name)), None),
            )
            for name in outline.category_names
        ]
    else:
        # 只有一種名額：用獎學金名稱當類別名稱，「全部」的規則就是它的規則
        categories = [merge_category(outline.name, shared, [])]
    # 文件要求：同一類型、同一類別只留一筆（other 要連要求文字都一樣才算同一份）
    requirements: dict[tuple[str, str, str], RequirementDraft] = {}
    for item in (r for s in sections for r in s.requirements):
        target = item.category
        if target and not any(same_name(target, n) for n in outline.category_names):
            if outline.category_names:
                warnings.append(f"未知類別：{target}")
            target = None  # 不能猜它指哪個類別，當成所有類別都要交
        details = normalized(item.details or "") if item.doc_type == "other" else ""
        key = (item.doc_type, normalized(target or ""), details)
        item = item.model_copy(update={"category": target})
        if key in requirements:
            item = combine(requirements[key], item)
        requirements[key] = item

    # 類別沒有自己的學位或國家時，用整個獎學金的
    for category in categories:
        if not category.degrees:
            category.degrees = values["degrees"]
            category.degrees_evidence = values["degrees_evidence"]
        category.countries = category.countries or values["countries"]

    values["total_quota"] = outline.total_quota or values["total_quota"]
    draft = ScholarshipDraft(
        name=outline.name,
        name_zh=outline.name_zh,
        provider=outline.provider,
        categories=categories,
        requirements=list(requirements.values()),
        **values,
    )
    return MergeResult(draft, conflicts, warnings)
