"""重複獎學金比對規則的單元測試（ADR-048）。"""

from app.features.scholarships import dedup


def test_normalize_url_ignores_scheme_www_fragment_and_trailing_slash() -> None:
    # 同一個申請頁，有人抄成 HTTP、加 www、帶著 #錨點，仍是同一個網址
    assert dedup.normalize_url("HTTP://www.Example.eu/Apply/#deadlines") == "https://example.eu/Apply"
    assert dedup.normalize_url("https://example.eu/") == dedup.normalize_url("https://example.eu")
    # 路徑的大小寫和查詢字串要保留：它們可能指向不同的頁面
    assert dedup.normalize_url("https://example.eu/apply?id=7") == "https://example.eu/apply?id=7"
    assert dedup.normalize_url("https://example.eu/Apply") != dedup.normalize_url("https://example.eu/apply")


def test_normalize_name_keeps_only_letters_and_digits() -> None:
    # 同一個獎學金，有的頁面用破折號「–」、有的大寫、有的多空白
    assert dedup.normalize_name("Erasmus Mundus Scholarship – SuCat") == "erasmusmundusscholarshipsucat"
    assert dedup.normalize_name("ERASMUS  MUNDUS scholarship-SuCat") == "erasmusmundusscholarshipsucat"
    # 中文字算文字要保留；全形數字轉成半形
    assert dedup.normalize_name("臺灣獎學金（２０２７）") == "臺灣獎學金2027"


def test_find_duplicates_by_same_link_or_same_provider_and_title() -> None:
    # 同一個 DAAD 獎學金從不同列表頁收進來三次：3 和 7 網址相同，3 和 9 提供者加名稱相同
    items = [
        dedup.Candidate(7, "DAAD", "Study Scholarships for Graduates", "http://www.daad.de/scholarship/#apply"),
        dedup.Candidate(3, "DAAD", "DAAD Study Scholarship", "https://daad.de/scholarship"),
        dedup.Candidate(9, "daad", "DAAD study  scholarship", "https://www.daad.de/en/study-scholarship"),
        # 沒有網址、也沒有提供者（或提供者是空字串）的，光名稱一樣不算重複
        dedup.Candidate(12, None, "DAAD Study Scholarship", None),
        dedup.Candidate(13, "", "DAAD Study Scholarship", None),
    ]
    # 7 和 9 名稱、網址都不同，但都跟 3 重複，所以也是同一組（遞移）；整組由最小的 3 代表
    assert dedup.find_duplicates(items) == {7: 3, 9: 3}

    # 真的碰過的問題：五個不同的 Erasmus Mundus 學程都叫同一個名字，但學校和網址不同，不是重複
    erasmus = [
        dedup.Candidate(20, "SuCat consortium", "Erasmus Mundus Scholarships", "https://sucat.eu/scholarships"),
        dedup.Candidate(21, "University of Barcelona", "Erasmus Mundus Scholarships", "https://ub.edu/emjm"),
        dedup.Candidate(22, "KU Leuven", "Erasmus Mundus Scholarships", "https://kuleuven.be/em"),
        dedup.Candidate(23, "Uppsala University", "Erasmus Mundus Scholarships", "https://uu.se/em"),
        dedup.Candidate(24, "IMBRSea consortium", "Erasmus Mundus Scholarships", "https://imbrsea.eu/apply"),
    ]
    assert dedup.find_duplicates(erasmus) == {}
