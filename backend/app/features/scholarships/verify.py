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
from app.features.scholarships.schemas import ScholarshipDraft, WindowDraft

PROMPT_VERSION = "verify-5"  # 改提示詞就要改版本號

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
    "incomplete",  # 截止日的年月日不齊全，不能建成申請期
]

PROMPT = """你是查核員。下面每一項是從獎學金原文抽出的值，以及抽取時附上的原文引用。
只根據引用本身判斷它是否支持這個值；引用沒寫到、寫得模糊、或要靠推測才成立，都算不支持。
- deadline:N 的引用必須寫出那個日期（包括年份），而且適用對象（國籍、獎學金或自費）要和引用一致；民國年加 1911 就是西元年，例如 115 年＝2026 年
- nationality 是 all 時，引用必須明確寫出開放所有國籍；listed 或 excluded 時，引用必須寫出那些國家

{claims}
"""


class Verdict(BaseModel):
    supported: bool = Field(description="引用是否足以支持這個值")
    reason: str = Field(description="一句話說明")


class ClaimVerdict(BaseModel):
    claim: str = Field(description="要判斷的項目代號，照抄，例如 nationality、deadline:0")
    supported: bool = Field(description="引用是否足以支持這個值")
    reason: str = Field(description="一句話說明")


class Verdicts(BaseModel):
    verdicts: list[ClaimVerdict]


def window_value(window: WindowDraft) -> str | None:
    """截止日的年月日都有才組成要核對的值，附上適用對象；不齊全回傳 None。"""
    if not (window.closes_year and window.closes_month and window.closes_day):
        return None
    date = f"{window.closes_year:04d}-{window.closes_month:02d}-{window.closes_day:02d}"
    who = f"{window.nationality_scope} {', '.join(window.nationalities)}".strip()
    return f"{date}（適用國籍：{who}；申請類型：{window.funding}）"


def claims(draft: ScholarshipDraft) -> dict[str, tuple[Any, str | None]]:
    """要核對的項目：（值, 引用）。每個申請窗口各一項（ADR-047）。"""
    nationality = (
        None
        if draft.nationality_scope == "unclear"
        else f"{draft.nationality_scope} {', '.join(draft.nationalities)}".strip()
    )
    found: dict[str, tuple[Any, str | None]] = {
        "nationality": (nationality, draft.nationality_evidence),
        "degrees": (draft.degrees, draft.degrees_evidence),
    }
    for index, window in enumerate(draft.windows):
        found[f"deadline:{index}"] = (window_value(window), window.evidence)
    return found


def rule_status(field: str, draft: ScholarshipDraft) -> Status | None:
    """程式檢查（ADR-045）：截止日年份要在引用裡、學位關鍵字；沒問題回傳 None。"""
    if field.startswith("deadline:"):
        window = draft.windows[int(field.split(":")[1])]
        if window.closes_year and not rules.deadline_year_in_quote(window.closes_year, window.evidence):
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
        # 只有一個類別時，名稱照規定用獎學金名稱，名稱檢查只對多個類別有意義
        multiple = len(draft.categories) > 1
        if multiple and (name_issue := rules.category_name_issue(category.name, source)):
            issues.append(name_issue)
        if category.quota is not None and not rules.number_in_source(category.quota, source):
            issues.append("quota_not_in_source")
        # ADR-046：有多個類別時只看這一類自己的學位引用；只有一個類別時才能用整個獎學金的
        quotes = [category.degrees_evidence] + ([] if multiple else [draft.degrees_evidence])
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
        elif field.startswith("deadline:") and value is None:
            status[field] = "incomplete"  # 只有月份或沒有年份，不能建成申請期
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
        # 第三關：只把需要判斷的項目一次問完；AI 沒回答到的項目算不支持
        lines = [f"- {field}：值 = {value}；引用 = 「{evidence}」" for field, (value, evidence) in to_ask.items()]
        verdicts = llm.extract(PROMPT.format(claims="\n".join(lines)), Verdicts)
        answers = {v.claim: v.supported for v in verdicts.verdicts}
        for field in to_ask:
            status[field] = "supported" if answers.get(field) else "not_supported"
    return {
        "nationality": status["nationality"],
        "degrees": status["degrees"],
        # 每個申請窗口的核對結果，順序和 draft.windows 一樣
        "deadlines": [status[f"deadline:{i}"] for i in range(len(draft.windows))],
        "categories": category_issues(draft, source),
        "issues": other_issues(draft, source),
    }


def apply_verification(draft: ScholarshipDraft, verification: dict[str, Any]) -> ScholarshipDraft:
    """國籍資格沒有通過驗證就改成 unclear；其他欄位保留值，由 verification 標示待確認。"""
    if verification["nationality"] not in ("supported", "empty"):
        return draft.model_copy(update={"nationality_scope": "unclear", "nationalities": []})
    return draft
