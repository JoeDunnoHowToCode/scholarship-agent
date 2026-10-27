"""結構化金額的單元測試（第 9 天，ADR-070）：數字寫法、核對、列表的大概金額、文字說明。"""

from app.features.scholarships import amounts


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
