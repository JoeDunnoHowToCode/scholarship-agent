"""翻頁連結的單元測試（ADR-029：EACEA 目錄含翻頁）。"""

import pytest

from app.features.sources import pagination

PAGE_URL = "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en"


def test_pagination_urls_keeps_same_path_page_links() -> None:
    # 只要同一路徑的 ?page=數字，轉成完整網址、去掉重複；其他連結都不跟
    html = """
    <a href="?page=1">2</a>
    <a href="?page=2">3</a>
    <a href="?page=1">next</a>
    <a href="/other_en?page=3">other path</a>
    <a href="https://example.org/scholarships/erasmus-mundus-catalogue_en?page=4">other site</a>
    <a href="?sort=name">sort</a>
    <a href="#top">top</a>
    """
    assert pagination.pagination_urls(html, PAGE_URL) == [
        f"{PAGE_URL}?page=1",
        f"{PAGE_URL}?page=2",
    ]


def test_pagination_urls_drops_fragments() -> None:
    # 實際抓 EACEA 時發現翻頁連結帶 #main-content；
    # # 後面的錨點只在瀏覽器裡跳位置，伺服器收到的是同一頁，不能當成另一個網址
    html = '<a href="?page=1">2</a><a href="?page=1#main-content">2</a>'
    assert pagination.pagination_urls(html, PAGE_URL) == [f"{PAGE_URL}?page=1"]


@pytest.mark.parametrize(
    ("page_zero_is_first", "expected"),
    [
        (True, [PAGE_URL, f"{PAGE_URL}?page=1"]),
        (False, [f"{PAGE_URL}?page=0", f"{PAGE_URL}?page=1"]),
    ],
    ids=["setting_on", "setting_off"],
)
def test_pagination_urls_page_zero_setting(
    page_zero_is_first: bool, expected: list[str]
) -> None:
    # EACEA 的 ?page=0 就是首頁本身（實測內容雜湊相同）；只有打開設定的來源才這樣換
    html = '<a href="?page=0">1</a><a href="?page=1">2</a>'
    urls = pagination.pagination_urls(html, PAGE_URL, page_zero_is_first=page_zero_is_first)
    assert urls == expected


def test_missing_pages_warning_first_run_is_silent() -> None:
    # 第一次抓沒有「上次頁數」可以比，不警示
    assert pagination.missing_pages_warning(None, 1) is None


def test_missing_pages_warning_when_pages_drop_to_one() -> None:
    # 上次 11 頁、這次只剩 1 頁：翻頁很可能失效了（門檻 C）
    assert (
        pagination.missing_pages_warning(11, 1)
        == "只抓到 1 頁（上次 11 頁），翻頁可能失效"
    )


@pytest.mark.parametrize(
    ("previous", "current"),
    [(11, 6), (1, 1)],
    ids=["fewer_but_not_one", "always_one_page"],
)
def test_missing_pages_no_warning_unless_many_pages_drop_to_one(
    previous: int, current: int
) -> None:
    # 門檻 C：頁數減少但不是只剩 1 頁、或本來就只有 1 頁，都不警示
    assert pagination.missing_pages_warning(previous, current) is None
