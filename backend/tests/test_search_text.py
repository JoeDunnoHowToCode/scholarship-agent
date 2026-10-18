"""要變成向量的文字的單元測試。"""

from app.features.search import text


def test_chunk_title_joins_headings() -> None:
    # 教育部簡章的段落：標題路徑去掉空白的那一層，用「 > 」串起來
    headings = ["貳、教育部 115 年留學獎學金甄試簡章", "四、獎助類別及名額", " "]
    assert text.chunk_title(headings) == "貳、教育部 115 年留學獎學金甄試簡章 > 四、獎助類別及名額"
    assert text.chunk_title([]) == ""


def test_scholarship_profile_lists_known_fields_in_order() -> None:
    # Erasmus 學程：沒填的金額、空的領域都不寫；清單用逗號串起來，順序固定
    fields = {
        "name": "Erasmus Mundus Scholarship – SuCat",
        "countries": ["France", "Spain"],
        "degrees": ["master"],
        "amount": None,
        "fields": [],
    }
    assert text.scholarship_profile(fields) == (
        "名稱：Erasmus Mundus Scholarship – SuCat\n國家：France, Spain\n學位：master"
    )
    # 欄位打亂順序傳進來，輸出仍照固定順序；空字串也略過
    fields = {"language_requirements": "IELTS 6.5", "provider": "", "coverage": "學費與生活費", "name": "教育部留學獎學金"}
    assert text.scholarship_profile(fields) == "名稱：教育部留學獎學金\n補助內容：學費與生活費\n語言要求：IELTS 6.5"
