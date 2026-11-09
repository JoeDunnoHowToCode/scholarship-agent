"""AI 比對兩筆獎學金是不是同一個計畫（11-09 使用者選 E＋D 的 D）：只在規則判斷不了的時候用。"""

from collections.abc import Callable

from pydantic import BaseModel, Field

from app.core import prompts
from app.core.llm.base import StructuredLLM
from app.features.scholarships.models import Scholarship

DEDUP_VERSION = "dedup-1"
PROMPT = prompts.load(DEDUP_VERSION)  # 文字在 backend/prompts/（ADR-088）


class SameVerdict(BaseModel):
    same: bool = Field(description="是不是同一個獎學金計畫")
    reason: str = Field(description="一句話說明")


def describe(row: Scholarship) -> str:
    """給 AI 比對用的摘要：只有抽出來的公開資料。"""
    return ""  # 骨架


def ai_same(llm: StructuredLLM) -> Callable[[Scholarship, Scholarship], bool]:
    """回傳一個「請 AI 比對兩筆獎學金」的函式，交給 decide_candidate 用。"""
    return lambda first, second: False  # 骨架
