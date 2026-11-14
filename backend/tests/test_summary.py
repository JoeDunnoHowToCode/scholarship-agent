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
