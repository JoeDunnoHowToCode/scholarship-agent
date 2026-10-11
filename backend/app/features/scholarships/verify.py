"""驗證者（ADR-008）：核對截止日、台灣籍、學位能不能在原文找到依據。

兩關：先由程式確認引用逐字存在於原文，再請 AI 判斷引用是否支持抽出來的值。
任一關沒過就是「待確認」；台灣籍沒過就改成 unclear（原文沒說清楚，絕不推定可以）。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.llm.base import StructuredLLM
from app.features.documents.checks import quote_in_source, quote_in_table_text
from app.features.scholarships.schemas import ScholarshipDraft

PROMPT_VERSION = "verify-2"  # 改提示詞就要改版本號

# 每個欄位的結果：
# supported 有依據；empty 沒抽到值（沒有要核對的）；no_evidence 有值但沒附引用；
# quote_not_found 引用不在原文裡；not_supported 引用不支持這個值；conflict 長文件各節說法不同
Status = Literal["supported", "empty", "no_evidence", "quote_not_found", "not_supported", "conflict"]

PROMPT = """你是查核員。下面每一項是從獎學金原文抽出的值，以及抽取時附上的原文引用。
只根據引用本身判斷它是否支持這個值；引用沒寫到、寫得模糊、或要靠推測才成立，都算不支持。
- taiwan_eligibility 是 yes 或 no 時，引用必須明確寫出台灣人（或中華民國國民）能或不能申請；只出現「Taiwan」這個字不算
- deadline 的引用必須寫出那個日期

{claims}
"""


class Verdict(BaseModel):
    supported: bool = Field(description="引用是否足以支持這個值")
    reason: str = Field(description="一句話說明")


class Verdicts(BaseModel):
    deadline: Verdict
    taiwan_eligibility: Verdict
    degrees: Verdict


def claims(draft: ScholarshipDraft) -> dict[str, tuple[Any, str | None]]:
    """要核對的三個欄位：（值, 引用）。"""
    return {
        "deadline": (draft.deadline, draft.deadline_evidence),
        "taiwan_eligibility": (draft.taiwan_eligibility, draft.taiwan_evidence),
        "degrees": (draft.degrees, draft.degrees_evidence),
    }


def verify(
    llm: StructuredLLM, draft: ScholarshipDraft, source: str, conflicts: list[str]
) -> dict[str, Status]:
    status: dict[str, Status] = {}
    to_ask: dict[str, tuple[Any, str]] = {}
    for field, (value, evidence) in claims(draft).items():
        if field in conflicts:
            status[field] = "conflict"
        elif value in (None, [], "unclear"):
            status[field] = "empty"
        elif not evidence:
            status[field] = "no_evidence"
        elif not (quote_in_source(evidence, source) or quote_in_table_text(evidence, source)):
            # 第一關：引用必須存在於原文（表格的字被交錯排列時，允許切成幾截就近出現）
            status[field] = "quote_not_found"
        else:
            to_ask[field] = (value, evidence)
    if to_ask:
        # 第二關：一次問完需要判斷的欄位；不需要判斷的也要填，告訴模型略過
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
    return status


def apply_verification(draft: ScholarshipDraft, status: dict[str, Status]) -> ScholarshipDraft:
    """台灣籍沒有通過驗證就改成 unclear；其他欄位保留值，由 status 標示待確認。"""
    if status["taiwan_eligibility"] not in ("supported", "empty"):
        return draft.model_copy(update={"taiwan_eligibility": "unclear"})
    return draft
