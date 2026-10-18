"""重複獎學金比對規則的單元測試（ADR-048）。"""

from app.features.scholarships import dedup


def test_normalize_url_ignores_scheme_www_fragment_and_trailing_slash() -> None:
    # 同一個申請頁，有人抄成 HTTP、加 www、帶著 #錨點，仍是同一個網址
    assert dedup.normalize_url("HTTP://www.Example.eu/Apply/#deadlines") == "https://example.eu/Apply"
    assert dedup.normalize_url("https://example.eu/") == dedup.normalize_url("https://example.eu")
    # 路徑的大小寫和查詢字串要保留：它們可能指向不同的頁面
    assert dedup.normalize_url("https://example.eu/apply?id=7") == "https://example.eu/apply?id=7"
    assert dedup.normalize_url("https://example.eu/Apply") != dedup.normalize_url("https://example.eu/apply")
