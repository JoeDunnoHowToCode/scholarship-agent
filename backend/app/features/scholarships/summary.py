"""獎學金說明（ADR-100 說明那條，docs/summary-plan.md）：2–3 句中文，每句附原文引用並核對三關。

獨立的一步，不改抽取的提示詞；有自己的版本號（extracted["summary_from"]），改說明的提示詞只會重做說明。
"""

from typing import Any

from sqlalchemy.orm import Session

from app.core import prompts
from app.core.llm.base import StructuredLLM
from app.features.documents.checks import quote_in_source, quote_in_table_text
from app.features.scholarships.amounts import numbers_in
from app.features.scholarships.models import Scholarship, ScholarshipStatus
from app.features.scholarships.schemas import SummaryDraft, SummarySentence
from app.features.scholarships.verify import Verdicts

SUMMARY_VERSION = "summary-1"  # 改提示詞就要改版本號
CHECK_VERSION = "summary-check-1"
PROMPT = prompts.load(SUMMARY_VERSION)  # 文字在 backend/prompts/（ADR-088）
CHECK_PROMPT = prompts.load(CHECK_VERSION)
MAX_SENTENCES = 3


def check_sentences(llm: StructuredLLM, sentences: list[SummarySentence], source: str) -> list[str]:
    """每句的核對結果：no_evidence、number_not_in_quote、quote_not_found、not_supported、supported。"""
    statuses: list[str] = []
    for sentence in sentences:
        if not sentence.evidence:
            statuses.append("no_evidence")
        elif not numbers_in(sentence.text) <= numbers_in(sentence.evidence):
            statuses.append("number_not_in_quote")  # 第一關：中文裡的每個數字都要在引用裡（1,400 和 1400 相同）
        elif not (quote_in_source(sentence.evidence, source) or quote_in_table_text(sentence.evidence, source)):
            statuses.append("quote_not_found")  # 第二關：引用要在原文裡（和 verify.py 一樣允許表格的字交錯）
        else:
            statuses.append("ask")
    # 第三關：剩下的一次問完；AI 沒回答到的算不支持（和 verify.py 一樣）
    to_ask = {f"s{i}": sentences[i] for i, status in enumerate(statuses) if status == "ask"}
    if to_ask:
        lines = [f"- {key}：句子 = {s.text}；引用 = 「{s.evidence}」" for key, s in to_ask.items()]
        verdicts = llm.extract(CHECK_PROMPT.format(claims="\n".join(lines)), Verdicts)
        answers = {v.claim: v.supported for v in verdicts.verdicts}
        for key in to_ask:
            statuses[int(key[1:])] = "supported" if answers.get(key) else "not_supported"
    return statuses


def make_summary(llm: StructuredLLM, source: str) -> list[dict[str, Any]]:
    """寫說明並核對，回傳最多 3 筆 {text, evidence, status}。"""
    sentences = llm.extract(PROMPT.format(text=source), SummaryDraft).sentences[:MAX_SENTENCES]
    statuses = check_sentences(llm, sentences, source)
    return [{"text": s.text, "evidence": s.evidence, "status": st} for s, st in zip(sentences, statuses, strict=True)]


def needs_summary(row: Scholarship) -> bool:
    """補抽說明時要不要做這筆：已封存、重複的不做（docs/summary-plan.md「Claude 自行決定」第 3 點）。"""
    return (
        row.status != ScholarshipStatus.ARCHIVED
        and row.duplicate_of is None
        and row.extracted.get("summary_from") != SUMMARY_VERSION
    )


def ensure_summary(session: Session, llm: StructuredLLM, row: Scholarship) -> bool:
    """說明不是最新版本就讀這筆抽取用的快照原文、產生並核對，寫進 extracted；回傳有沒有呼叫 AI。"""
    if row.extracted.get("summary_from") == SUMMARY_VERSION or row.source_id is None:
        return False
    # 放在函式裡匯入：extract 的補抽指令也會用到這個模組，放在檔案開頭會互相匯入
    from app.features.scholarships.extract import snapshot_text

    source = snapshot_text(session, row.source_id, row.extracted.get("meta", {}).get("snapshots", []))
    made = make_summary(llm, source)
    row.extracted = {**row.extracted, "summary": made, "summary_from": SUMMARY_VERSION}  # JSONB 整個重新指定
    return True
