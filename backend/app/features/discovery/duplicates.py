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
    closes = sorted(f"{c.closes_at:%Y-%m-%d}" for c in row.cycles if not c.estimated)
    return "\n".join([
        f"名稱：{row.name}",
        f"提供者：{row.provider or '原文沒寫'}",
        f"官網：{row.official_url or '原文沒寫'}",
        f"留學國家：{', '.join(row.countries) or '原文沒寫'}",
        f"學位：{', '.join(row.degrees) or '原文沒寫'}",
        f"截止日：{', '.join(closes) or '原文沒寫'}",
        f"補助：{(row.coverage or row.amount or '原文沒寫')[:300]}",
    ])


def ai_same(llm: StructuredLLM) -> Callable[[Scholarship, Scholarship], bool]:
    """回傳一個「請 AI 比對兩筆獎學金」的函式，交給 decide_candidate 用。"""

    def same(first: Scholarship, second: Scholarship) -> bool:
        prompt = PROMPT.format(first=describe(first), second=describe(second))
        return llm.extract(prompt, SameVerdict).same

    return same
