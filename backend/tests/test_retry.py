"""核對沒過的錯誤訊息（ADR-111）：拋回 AI 重抽時，要讓它知道哪個欄位、上次填什麼、為什麼沒過。"""

from app.features.scholarships import retry
from tests.test_extract_build import DRAFT


def test_problems_list_each_failed_field_with_its_value_quote_and_reason() -> None:
    draft = DRAFT.model_copy(update={"offered": "yes", "offered_evidence": "Applications are closed"})
    status = {
        "nationality": "supported", "degrees": "degree_not_in_quote", "deadlines": [],
        "amounts": [], "offered": "not_supported", "categories": {}, "issues": [],
    }
    lines = retry.problems(draft, status)
    assert len(lines) == 2
    degrees, offered = lines
    assert degrees.startswith("- 學位") and "master" in degrees and "引用裡沒有這個學位" in degrees
    assert offered.startswith("- 今年有沒有開") and "Applications are closed" in offered and "標準 5.1" in offered
    assert retry.failures(status) == 2


def test_statuses_the_program_handles_itself_are_not_retried() -> None:
    # 年份交給程式推算（ADR-110）、沒有值、長文件各節說法不同：重抽也不會變好
    status = {"nationality": "empty", "degrees": "supported", "deadlines": ["incomplete", "conflict"],
              "amounts": ["supported"], "categories": {}, "issues": []}
    assert retry.problems(DRAFT, status) == [] and retry.failures(status) == 0
