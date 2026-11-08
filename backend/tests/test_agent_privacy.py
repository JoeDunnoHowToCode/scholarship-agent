"""假個資測試（ADR-087）：國籍、想去的國家不會出現在送給 AI 或 Tavily 的任何文字裡。"""

from datetime import date
from typing import Any

from app.core.llm.base import ChatMessage, ToolCall, ToolSpec, Turn
from app.features.discovery.agent import run_agent
from app.features.discovery.tasks import search_task
from app.features.discovery.tools import Page, SearchHit, Toolbox
from app.features.profiles.models import Profile

# 帶記號的假個資：只要記號出現在送出去的文字裡，就代表個資外流
PROFILE = Profile(
    user_id=1, nationality="NATIONALITY-MARKER", target_degree="master",
    current_major="Computer Science", target_fields=["Machine Learning"], target_countries=["COUNTRY-MARKER"],
)
MARKERS = ("NATIONALITY-MARKER", "COUNTRY-MARKER")


class EchoLLM:
    """最壞的情況：AI 把它看到的任務內容整段拿去搜尋。記下它看過的所有訊息。"""

    def __init__(self) -> None:
        self.seen: list[ChatMessage] = []
        self.turns = 0

    def step(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> Turn:
        self.seen = list(messages)
        self.turns += 1
        if self.turns == 1:
            task = next(m.content for m in messages if m.role == "user")
            return Turn(ChatMessage("assistant", "", [ToolCall("c1", "search", {"query": task})]), 1, 1, 0.0)
        return Turn(ChatMessage("assistant", "完成"), 1, 1, 0.0)


class NoLog:
    def model(self, number: int, turn: Turn) -> None:
        pass

    def tool(self, number: int, name: str, args: dict[str, Any], result: str) -> None:
        pass


def test_profile_markers_never_reach_the_ai_or_the_search_service() -> None:
    task = search_task(PROFILE, date(2026, 11, 8))
    # 科系和領域要在（否則這個測試什麼都沒證明）
    assert "Computer Science" in task and "Machine Learning" in task
    queries: list[str] = []

    def searcher(query: str) -> list[SearchHit]:
        queries.append(query)
        return [SearchHit("Result", "https://example.eu/s", "summary")]

    llm = EchoLLM()
    box = Toolbox(searcher, lambda url: Page(url, "", []), searches_left=5)
    run_agent(llm, "任務說明", task, box.tools(), NoLog(), max_steps=5, max_cost_usd=1.0)
    sent_to_ai = "\n".join(m.content for m in llm.seen)
    assert queries and "Computer Science" in queries[0]  # AI 真的把任務拿去搜尋了
    for marker in MARKERS:
        assert marker not in sent_to_ai
        assert all(marker not in q for q in queries)
