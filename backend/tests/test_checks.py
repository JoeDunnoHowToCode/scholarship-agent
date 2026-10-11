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
