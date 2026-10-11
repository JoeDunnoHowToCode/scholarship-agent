"""轉錄稿對照原始文字的單元測試（ADR-037）。"""

from app.features.documents import checks


def test_quote_in_source_ignores_whitespace_width_and_checks_ellipsis_order() -> None:
    # pdfplumber 會在句子中間斷行，全形「（」和半形「(」也要當成一樣
    source = "教育部（以下簡稱本部）為厚植國家實力，\n培育各領域人才。申請人須具備 ＴＯＥＦＬ 80 分。"
    assert checks.quote_in_source("教育部(以下簡稱本部)為厚植國家實力，培育各領域人才", source)
    # 引用中間用刪節號省略：每一截都要依序出現在原文
    assert checks.quote_in_source("教育部…培育各領域人才", source)
    assert checks.quote_in_source("教育部...TOEFL 80", source)
    assert not checks.quote_in_source("培育各領域人才…教育部", source)
    # 原文沒有的話、只有刪節號的空引用，都算不通過
    assert not checks.quote_in_source("申請人須具備 IELTS 6.5", source)
    assert not checks.quote_in_source("…", source)


def test_unverified_numbers_lists_numbers_missing_from_raw_text() -> None:
    # 轉錄稿的「16,000」對得到原文的「16000」，「1400」也對得到「1,400」
    # 「9」和「25.5」原文裡找不到，列出來（重複的只列一次，依出現順序）
    transcript = "核發 16,000 美元，名額 1400 名，115 年 3 月 9 日截止，共 9 年，另有 25.5 萬元。"
    raw = "核發 16000 美元，名額 1,400 名，\n115 年 3 月 1 日截止"
    assert checks.unverified_numbers(transcript, raw) == ["9", "25.5"]


# 教育部簡章的日程表在 pdfplumber 原文裡，左右兩欄的字交錯在一起
TABLE_RAW = """申請人須於開放報名期限內完成：
【開放網路報名起訖時間】
1. 網路填寫報名資料，列印報名表
115 年 1 月 16 日(五)上午 8:30 起至
親筆簽名後上傳至報名系統
115 年 2 月 13 日(五)中午 12:00 截止
2. 下載繳費單並繳交報名費，將報
【入學許可主動補件期間】
115 年 3 月 9 日(一)上午 8:30 起至"""


def test_quote_in_table_text_accepts_fragments_in_order_nearby() -> None:
    # Gemini 轉錄的表格是連續的一句，原文被另一欄切開；每一截（至少 6 個字）依序、就近出現就算找得到
    quote = "【開放網路報名起訖時間】115 年 1 月 16 日(五)上午 8:30 起至115 年 2 月 13 日(五)中午 12:00 截止"
    assert not checks.quote_in_source(quote, TABLE_RAW)
    assert checks.quote_in_table_text(quote, TABLE_RAW)


def test_quote_in_table_text_rejects_a_changed_date() -> None:
    # 把截止日改成 3 月 13 日：拼得出「115年3月」和「13日(五)中午12:00截止」，但順序不對
    quote = "【開放網路報名起訖時間】115 年 1 月 16 日(五)上午 8:30 起至115 年 3 月 13 日(五)中午 12:00 截止"
    assert not checks.quote_in_table_text(quote, TABLE_RAW)
