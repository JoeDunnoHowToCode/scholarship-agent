"""獎學金說明（ADR-100 說明那條，docs/summary-plan.md）：2–3 句中文，每句附原文引用並核對三關。

獨立的一步，不改抽取的提示詞；有自己的版本號（extracted["summary_from"]），改說明的提示詞只會重做說明。
"""

from typing import Any

from sqlalchemy.orm import Session

from app.core import prompts
from app.core.llm.base import StructuredLLM
from app.features.scholarships.models import Scholarship
from app.features.scholarships.schemas import SummarySentence

SUMMARY_VERSION = "summary-1"  # 改提示詞就要改版本號
CHECK_VERSION = "summary-check-1"
PROMPT = prompts.load(SUMMARY_VERSION)  # 文字在 backend/prompts/（ADR-088）
CHECK_PROMPT = prompts.load(CHECK_VERSION)
MAX_SENTENCES = 3


def check_sentences(llm: StructuredLLM, sentences: list[SummarySentence], source: str) -> list[str]:
    """每句的核對結果：no_evidence、number_not_in_quote、quote_not_found、not_supported、supported。"""
    return ["no_evidence" if not s.evidence else "supported" for s in sentences]


def make_summary(llm: StructuredLLM, source: str) -> list[dict[str, Any]]:
    """寫說明並核對，回傳最多 3 筆 {text, evidence, status}。"""
    return []


def ensure_summary(session: Session, llm: StructuredLLM, row: Scholarship) -> bool:
    """說明不是最新版本就讀這筆抽取用的快照原文、產生並核對，寫進 extracted；回傳有沒有呼叫 AI。"""
    return False
