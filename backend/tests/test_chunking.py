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


def test_markdown_heading_sets_level_unless_text_is_numbered() -> None:
    # 一般 Markdown 標題：幾個 # 就是第幾層
    # 「### 一、設置目的」有公文編號，層級看編號（第二層），不看 # 的數量
    intro = "This guide explains the scholarship rules. " * 6
    rules = "The applicant must be a citizen of Taiwan. " * 6
    age = "The applicant must be under 35 years old. " * 6
    purpose = "教育部為厚植國家實力，培育各領域人才。" * 12
    transcript = f"""# Scholarship Guide
{intro}
## Eligibility
{rules}
### Age
{age}
### 一、設置目的
{purpose}"""
    assert chunking.chunk_transcript(transcript) == [
        chunking.Chunk(("Scholarship Guide",), "Scholarship Guide\n" + intro.strip(), "text"),
        chunking.Chunk(
            ("Scholarship Guide", "Eligibility"), "Eligibility\n" + rules.strip(), "text"
        ),
        chunking.Chunk(
            ("Scholarship Guide", "Eligibility", "Age"), "Age\n" + age.strip(), "text"
        ),
        chunking.Chunk(
            ("Scholarship Guide", "一、設置目的"), "一、設置目的\n" + purpose, "text"
        ),
    ]


def test_transcript_table_lines_become_one_table_chunk() -> None:
    # 連續以 | 開頭的行是一張表，整張表自成一段；表格前後的文字各自成段
    transcript = """一、重要日程
| 時程 | 要項 |
| --- | --- |
| 115 年 1 月 16 日 | 開放網路報名 |
以上日期如有變動，以本部公告為準。"""
    assert chunking.chunk_transcript(transcript) == [
        chunking.Chunk(("一、重要日程",), "一、重要日程", "text"),
        chunking.Chunk(
            ("一、重要日程",),
            "| 時程 | 要項 |\n| --- | --- |\n| 115 年 1 月 16 日 | 開放網路報名 |",
            "table",
        ),
        chunking.Chunk(("一、重要日程",), "以上日期如有變動，以本部公告為準。", "text"),
    ]


def test_too_long_text_chunk_splits_at_line_boundaries() -> None:
    # 一段超過 MAX_CHARS 就在換行處切開：每塊都不超過上限，標題路徑不變，字一個都不少
    line = "申請人應檢附成績單。" * 10  # 一行 100 字
    transcript = "一、應繳文件\n" + "\n".join([line] * 30)
    chunks = chunking.chunk_transcript(transcript)
    assert len(chunks) == 2
    assert all(len(chunk.text) <= chunking.MAX_CHARS for chunk in chunks)
    assert all(chunk.heading_path == ("一、應繳文件",) for chunk in chunks)
    assert "\n".join(chunk.text for chunk in chunks) == transcript

    # 單獨一行就超過上限時，只好照字數硬切
    chunks = chunking.chunk_transcript("一、說明\n" + "字" * 7000)
    assert [len(chunk.text) for chunk in chunks] == [4, 3000, 3000, 1000]


def test_too_short_text_chunk_merges_into_previous_under_same_top_heading() -> None:
    # 「二、年限」太短，併進同在「壹、」底下的上一段，沿用上一段的標題路徑
    # 「三、附則」的上一段是表格，不併；「貳、」的上一段屬於「壹、」，也不併
    quota = "本年度預計錄取一百二十名，依學門分配。" * 12
    transcript = f"""壹、獎學金
一、名額
{quota}
二、年限
最長二年。
| 項目 | 金額 |
三、附則
未盡事宜依本部規定辦理。
貳、申請方式
一律網路報名。"""
    assert chunking.chunk_transcript(transcript) == [
        chunking.Chunk(("壹、獎學金",), "壹、獎學金", "text"),
        chunking.Chunk(
            ("壹、獎學金", "一、名額"), f"一、名額\n{quota}\n二、年限\n最長二年。", "text"
        ),
        chunking.Chunk(("壹、獎學金", "二、年限"), "| 項目 | 金額 |", "table"),
        chunking.Chunk(("壹、獎學金", "三、附則"), "三、附則\n未盡事宜依本部規定辦理。", "text"),
        chunking.Chunk(("貳、申請方式",), "貳、申請方式\n一律網路報名。", "text"),
    ]


def test_html_heading_tags_become_chunk_boundaries() -> None:
    # 網頁的 h1～h4 就是標題：h1 第一層、h2 第二層……；script 不是看得到的文字
    about = "The scholarship supports master's students in Europe. " * 4
    rules = "Applicants must hold a bachelor's degree. " * 5
    age = "Applicants must be under 35 years old. " * 6
    docs = "Upload two reference letters before the deadline. " * 4
    html = f"""<h1>Guide</h1><p>{about}</p><script>var x = 1;</script>
<h2>Eligibility</h2><p>{rules}</p>
<h3>Age</h3><p>{age}</p>
<h4>Documents</h4><p>{docs}</p>"""
    assert chunking.chunk_html(html) == [
        chunking.Chunk(("Guide",), "Guide\n" + about.strip(), "text"),
        chunking.Chunk(("Guide", "Eligibility"), "Eligibility\n" + rules.strip(), "text"),
        chunking.Chunk(("Guide", "Eligibility", "Age"), "Age\n" + age.strip(), "text"),
        chunking.Chunk(
            ("Guide", "Eligibility", "Age", "Documents"), "Documents\n" + docs.strip(), "text"
        ),
    ]
