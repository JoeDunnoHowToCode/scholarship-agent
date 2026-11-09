"""AI 比對兩筆獎學金（11-09 使用者選 E＋D 的 D）：用假的 AI，不連網。"""

from datetime import UTC, datetime
from typing import Any

from app.features.discovery.duplicates import SameVerdict, ai_same
from app.features.scholarships.models import Cycle, Scholarship


class FakeLLM:
    def __init__(self, same: bool) -> None:
        self.same = same
        self.prompts: list[str] = []

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        self.prompts.append(prompt)
        return SameVerdict(same=self.same, reason="同一個計畫的台灣頁和總頁")


def scholarship(name: str, url: str) -> Scholarship:
    row = Scholarship(name=name, provider="Foreign, Commonwealth and Development Office", countries=["GB"],
                      degrees=["master"], official_url=url, coverage="Full tuition, living allowance", extracted={})
    row.cycles = [Cycle(closes_at=datetime(2026, 10, 7, tzinfo=UTC), status="closed")]
    return row


def test_the_ai_sees_both_scholarships_and_its_answer_is_used() -> None:
    llm = FakeLLM(same=True)
    first = scholarship("Chevening Scholarships", "https://www.chevening.org/scholarships")
    second = scholarship("Chevening Scholarship – Taiwan", "https://www.chevening.org/scholarship/taiwan/")
    assert ai_same(llm)(first, second) is True
    assert len(llm.prompts) == 1
    sent = llm.prompts[0]
    # 兩筆的名稱、官網、國家、截止日都要給 AI 看
    for text in ("Chevening Scholarships", "Chevening Scholarship – Taiwan", "chevening.org/scholarship/taiwan",
                 "GB", "2026-10-07", "Full tuition"):
        assert text in sent
    assert ai_same(FakeLLM(same=False))(first, second) is False
