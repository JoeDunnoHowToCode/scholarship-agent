"""結構化金額的單元測試（第 9 天，ADR-070）：數字寫法、核對、列表的大概金額、文字說明。"""

from app.features.scholarships import amounts, schemas


def test_numbers_in_reads_thousands_decimals_and_chinese_units() -> None:
    # 千分位用逗號或點都可以；最後一段只有 1–2 位數的是小數
    assert amounts.numbers_in("EUR 1,400 per month") == {1400}
    assert amounts.numbers_in("1.400 € pro Monat") == {1400}
    assert amounts.numbers_in("tuition fee 5,613.10 EUR") == {5613.10}
    assert amounts.numbers_in("Studiengebühr 5.613,10 EUR") == {5613.10}
    assert amounts.numbers_in("up to 2.5 times") == {2.5}
    # 全形數字（NFKC）
    assert amounts.numbers_in("每月１，４００歐元") == {1400}
    # 中文單位：教育部簡章的寫法
    assert amounts.numbers_in("一般生每人每年核發 1 萬 6 千美元") == {16000}
    assert amounts.numbers_in("每人每年核發 3 萬美元、特殊教育生 2萬美元") == {30000, 20000}
    assert amounts.numbers_in("1.6 萬美元") == {16000}
    assert amounts.numbers_in("5千元") == {5000}
    # 沒有數字
    assert amounts.numbers_in("全額補助") == set()


def test_amount_status_checks_the_quote_and_the_number() -> None:
    page = "Each scholar receives a monthly allowance of EUR 1,400. Travel costs: up to 3,000 € per year."

    def amount(value: float, evidence: str | None, currency: str = "EUR") -> "schemas.AmountDraft":
        return schemas.AmountDraft(
            value=value, currency=currency, period="month", kind="living_allowance", applies_to=None, evidence=evidence
        )

    # 引用在原文裡，而且引用裡真的有這個數字：通過
    assert amounts.amount_status(amount(1400, "a monthly allowance of EUR 1,400"), page) == "supported"
    # 沒附引用
    assert amounts.amount_status(amount(1400, None), page) == "no_evidence"
    # 幣別不是 ISO 4217 的三碼代碼
    assert amounts.amount_status(amount(1400, "a monthly allowance of EUR 1,400", currency="EURO"), page) == "invalid_currency"
    # 引用不在原文裡（AI 改寫過）
    assert amounts.amount_status(amount(1400, "EUR 1,400 every month"), page) == "quote_not_found"
    # 引用在原文裡，但數字不對（AI 把 1,400 寫成 1,500）
    assert amounts.amount_status(amount(1500, "a monthly allowance of EUR 1,400"), page) == "number_not_in_quote"
