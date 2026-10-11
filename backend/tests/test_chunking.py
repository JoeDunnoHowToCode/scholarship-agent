"""依標題結構切段的單元測試（ADR-038、ADR-036 A）。"""

from app.features.documents import chunking


def test_numbering_lines_become_headings_but_toc_lines_do_not() -> None:
    # 壹、是第一層，一、是第二層，(一)是第三層；1. 不是標題
    # 目錄那行（點點點加頁碼）只是普通文字，不能當標題
    purpose = "教育部為厚植國家實力，培育各領域人才。" * 12
    benefit = "獎學金依留學國家及學門核發，名額依甄試結果決定。" * 10
    amount = "1.一般生每人每年核發 1 萬 6 千美元。\n" + "核發期間依實際就讀情形而定。" * 15
    transcript = f"""一、設置目的………………………… 2
壹、教育部 115 年留學獎學金甄試
貳、教育部 115 年留學獎學金甄試簡章
一、設置目的
{purpose}
二、獎學金待遇及年限
{benefit}
(一)獎學金待遇：
{amount}"""
    brochure = "貳、教育部 115 年留學獎學金甄試簡章"
    assert chunking.chunk_transcript(transcript) == [
        chunking.Chunk((), "一、設置目的………………………… 2", "text"),
        chunking.Chunk(
            ("壹、教育部 115 年留學獎學金甄試",), "壹、教育部 115 年留學獎學金甄試", "text"
        ),
        chunking.Chunk((brochure,), brochure, "text"),
        chunking.Chunk((brochure, "一、設置目的"), "一、設置目的\n" + purpose, "text"),
        chunking.Chunk(
            (brochure, "二、獎學金待遇及年限"), "二、獎學金待遇及年限\n" + benefit, "text"
        ),
        chunking.Chunk(
            (brochure, "二、獎學金待遇及年限", "(一)獎學金待遇："),
            "(一)獎學金待遇：\n" + amount,
            "text",
        ),
    ]

    # 標題路徑裡每個標題最多留 40 個字；段落文字裡的標題行保持完整
    long_heading = "壹、" + "教育部公費留學考試" * 6
    chunks = chunking.chunk_transcript(long_heading + "\n" + purpose)
    assert chunks == [
        chunking.Chunk((long_heading[:40],), long_heading + "\n" + purpose, "text")
    ]
