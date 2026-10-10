"""翻頁連結的單元測試（ADR-029：EACEA 目錄含翻頁）。"""

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
