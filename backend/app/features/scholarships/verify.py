"""驗證者（ADR-008、045）：核對截止日、國籍資格、學位能不能在原文找到依據。

三關：先跑程式檢查（rules.py，不花錢），再由程式確認引用存在於原文，
最後請 AI 判斷引用是否支持抽出來的值。任一關沒過就是「待確認」；
國籍資格沒過就改成 unclear（原文沒說清楚，絕不推定可以，ADR-043）。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.llm.base import StructuredLLM
from app.features.documents.checks import quote_in_source, quote_in_table_text
from app.features.scholarships import rules
from app.features.scholarships.schemas import ScholarshipDraft

PROMPT_VERSION = "verify-3"  # 改提示詞就要改版本號

# 每個欄位的結果：
# supported 有依據；empty 沒抽到值（沒有要核對的）；no_evidence 有值但沒附引用；
# quote_not_found 引用不在原文裡；not_supported 引用不支持這個值；conflict 長文件各節說法不同；
# year_not_in_quote 截止日的年份不在引用裡；degree_not_in_quote 學位的關鍵字不在引用裡
Status = Literal[
    "supported",
    "empty",
    "no_evidence",
    "quote_not_found",
    "not_supported",
    "conflict",
    "year_not_in_quote",
    "degree_not_in_quote",
]

PROMPT = """你是查核員。下面每一項是從獎學金原文抽出的值，以及抽取時附上的原文引用。
只根據引用本身判斷它是否支持這個值；引用沒寫到、寫得模糊、或要靠推測才成立，都算不支持。
- deadline 的引用必須寫出那個日期（包括年份）
- nationality 是 all 時，引用必須明確寫出開放所有國籍；listed 或 excluded 時，引用必須寫出那些國家

{claims}
"""


class Verdict(BaseModel):
    supported: bool = Field(description="引用是否足以支持這個值")
    reason: str = Field(description="一句話說明")


class Verdicts(BaseModel):
    deadline: Verdict
    nationality: Verdict
    degrees: Verdict


def deadline_text(draft: ScholarshipDraft) -> str | None:
    """年月日都有才組成 YYYY-MM-DD；缺任何一個就沒有完整的截止日。"""
    if draft.deadline_year and draft.deadline_month and draft.deadline_day:
        return f"{draft.deadline_year:04d}-{draft.deadline_month:02d}-{draft.deadline_day:02d}"
    return None


def claims(draft: ScholarshipDraft) -> dict[str, tuple[Any, str | None]]:
    """要核對的三個欄位：（值, 引用）。"""
    deadline = None
    if draft.deadline_year or draft.deadline_month:
        deadline = deadline_text(draft) or (
            f"{draft.deadline_year or '????'}-{draft.deadline_month or '??'}-{draft.deadline_day or '??'}"
        )
    nationality = (
        None
        if draft.nationality_scope == "unclear"
        else f"{draft.nationality_scope} {', '.join(draft.nationalities)}".strip()
    )
    return {
        "deadline": (deadline, draft.deadline_evidence),
        "nationality": (nationality, draft.nationality_evidence),
        "degrees": (draft.degrees, draft.degrees_evidence),
    }


def rule_status(field: str, draft: ScholarshipDraft) -> Status | None:
    """程式檢查（ADR-045）：截止日年份、學位關鍵字；沒問題回傳 None。"""
    year = draft.deadline_year
    if field == "deadline" and year and not rules.deadline_year_in_quote(year, draft.deadline_evidence):
        return "year_not_in_quote"
    quotes = [draft.degrees_evidence]
    if field == "degrees" and not all(rules.degree_supported(d, quotes) for d in draft.degrees):
        return "degree_not_in_quote"
    return None


def category_issues(draft: ScholarshipDraft, source: str) -> dict[str, list[str]]:
    """每個類別的程式檢查：名稱、名額、學位關鍵字（ADR-045 第 2、3、4 條）。"""
    found: dict[str, list[str]] = {}
    for category in draft.categories:
        issues = []
        if name_issue := rules.category_name_issue(category.name, source):
            issues.append(name_issue)
        if category.quota is not None and not rules.number_in_source(category.quota, source):
            issues.append("quota_not_in_source")
        quotes = [category.evidence, draft.degrees_evidence]
        issues += [
            f"degree_not_in_quote:{d}" for d in category.degrees if not rules.degree_supported(d, quotes)
        ]
        if issues:
            found[category.name] = issues
    return found


def other_issues(draft: ScholarshipDraft, source: str) -> list[str]:
    """名額加總（第 5 條）與國名（第 4 條）。"""
    issues = []
    if rules.quota_sum_mismatch(draft.total_quota, [c.quota for c in draft.categories]):
        issues.append("quota_sum_mismatch")
    issues += [
        f"nationality_not_in_source:{n}"
        for n in draft.nationalities
        if not rules.name_in_source(n, source)
    ]
    return issues


def verify(
    llm: StructuredLLM, draft: ScholarshipDraft, source: str, conflicts: list[str]
) -> dict[str, Any]:
    status: dict[str, Status] = {}
    to_ask: dict[str, tuple[Any, str]] = {}
    for field, (value, evidence) in claims(draft).items():
        if field in conflicts:
            status[field] = "conflict"
        elif value in (None, []):
            status[field] = "empty"
        elif not evidence:
            status[field] = "no_evidence"
        elif problem := rule_status(field, draft):
            status[field] = problem  # 第一關：程式檢查
        elif not (quote_in_source(evidence, source) or quote_in_table_text(evidence, source)):
            # 第二關：引用必須存在於原文（表格的字被交錯排列時，允許切成幾截就近出現）
            status[field] = "quote_not_found"
        else:
            to_ask[field] = (value, evidence)
    if to_ask:
        # 第三關：一次問完需要判斷的欄位；不需要判斷的也要填，告訴模型略過
        lines = [
            f"- {field}：值 = {to_ask[field][0]}；引用 = 「{to_ask[field][1]}」"
            if field in to_ask
            else f"- {field}：（不需判斷，supported 填 true）"
            for field in claims(draft)
        ]
        verdicts = llm.extract(PROMPT.format(claims="\n".join(lines)), Verdicts)
        for field in to_ask:
            verdict: Verdict = getattr(verdicts, field)
            status[field] = "supported" if verdict.supported else "not_supported"
    return {
        **status,
        "categories": category_issues(draft, source),
        "issues": other_issues(draft, source),
    }


def apply_verification(draft: ScholarshipDraft, verification: dict[str, Any]) -> ScholarshipDraft:
    """國籍資格沒有通過驗證就改成 unclear；其他欄位保留值，由 verification 標示待確認。"""
    if verification["nationality"] not in ("supported", "empty"):
        return draft.model_copy(update={"nationality_scope": "unclear", "nationalities": []})
    return draft
