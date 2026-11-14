"""獎學金說明的核對與產生（docs/summary-plan.md）：假的 AI，不碰資料庫。"""

from typing import Any

from app.features.scholarships import summary
from app.features.scholarships.schemas import SummaryDraft, SummarySentence
from app.features.scholarships.verify import ClaimVerdict, Verdicts

SOURCE = "The Test Foundation offers 20 scholarships to non-EU students. Each scholar receives EUR 1,400 per month."


class FakeLLM:
    """寫說明時回傳固定的句子；核對時依 supported 決定每一句的結果（沒列到的句子就不回答）。"""

    def __init__(self, sentences: list[SummarySentence] | None = None, supported: dict[str, bool] | None = None):
        self.sentences = sentences or []
        self.supported = supported or {}
        self.calls = 0

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        self.calls += 1
        if schema is SummaryDraft:
            return SummaryDraft(sentences=self.sentences)
        return Verdicts(verdicts=[ClaimVerdict(claim=c, supported=ok, reason="") for c, ok in self.supported.items()])


def test_a_sentence_without_a_quote_is_no_evidence() -> None:
    sentences = [SummarySentence(text="由 Test Foundation 提供。", evidence=None)]
    assert summary.check_sentences(FakeLLM(), sentences, SOURCE) == ["no_evidence"]


def test_a_number_missing_from_the_quote_is_number_not_in_quote() -> None:
    # 中文寫 1,500 歐元，引用寫的是 1,400：程式就擋下，不用問 AI；1,400 和 1400 視為相同
    wrong = SummarySentence(text="每月補助 1,500 歐元。", evidence="Each scholar receives EUR 1,400 per month.")
    right = SummarySentence(text="每月補助 1400 歐元。", evidence="Each scholar receives EUR 1,400 per month.")
    statuses = summary.check_sentences(FakeLLM(supported={"s1": True}), [wrong, right], SOURCE)
    assert statuses[0] == "number_not_in_quote"


def test_a_quote_not_in_the_source_is_quote_not_found() -> None:
    made_up = SummarySentence(text="由 Test Foundation 提供。", evidence="The Test Foundation funds everyone.")
    assert summary.check_sentences(FakeLLM(), [made_up], SOURCE) == ["quote_not_found"]


def test_the_ai_decides_the_rest_and_a_missing_answer_is_not_supported() -> None:
    who = SummarySentence(text="由 Test Foundation 提供。", evidence="The Test Foundation offers 20 scholarships")
    whom = SummarySentence(text="給非歐盟學生。", evidence="scholarships to non-EU students")
    money = SummarySentence(text="每月 1,400 歐元。", evidence="Each scholar receives EUR 1,400 per month.")
    llm = FakeLLM(supported={"s0": True, "s1": False})  # s2 沒回答
    assert summary.check_sentences(llm, [who, whom, money], SOURCE) == ["supported", "not_supported", "not_supported"]
    assert llm.calls == 1  # 一次問完
