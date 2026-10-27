"""問答的單元測試（第 9 天）：answer_with 回傳答案與有效的出處，網頁才能顯示。"""

from pydantic import BaseModel

from app.features.search import ask


class FakeLLM:
    """假的模型：不管問什麼，都回傳事先準備好的答案（不呼叫 Gemini、不花錢）。"""

    def __init__(self, answer: ask.Answer) -> None:
        self.answer = answer

    def extract[M: BaseModel](self, prompt: str, schema: type[M]) -> M:
        return schema.model_validate(self.answer.model_dump())


def test_answer_with_returns_the_answer_and_only_real_citations() -> None:
    evidence = [
        ask.Evidence("F1", "類別「北歐國家」：名額 3", "https://example.org/moe"),
        ask.Evidence("F2", "截止日：2027-02-13", "https://example.org/moe#deadline"),
    ]
    llm = FakeLLM(ask.Answer(answer="北歐國家有 3 個名額 [F1]。", citations=["F1", "F9"]))
    answered = ask.answer_with(llm, "教育部北歐國家有幾個名額？", evidence)
    # 答案原樣回傳；出處只留真的提供給 AI 的（F1），AI 編出來的編號（F9）另外記下
    assert answered.answer == "北歐國家有 3 個名額 [F1]。"
    assert [(e.id, e.where) for e in answered.citations] == [("F1", "https://example.org/moe")]
    assert answered.invalid == ["F9"]
