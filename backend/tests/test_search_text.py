"""要變成向量的文字的單元測試。"""

from app.features.search import text


def test_chunk_title_joins_headings() -> None:
    # 教育部簡章的段落：標題路徑去掉空白的那一層，用「 > 」串起來
    headings = ["貳、教育部 115 年留學獎學金甄試簡章", "四、獎助類別及名額", " "]
    assert text.chunk_title(headings) == "貳、教育部 115 年留學獎學金甄試簡章 > 四、獎助類別及名額"
    assert text.chunk_title([]) == ""
