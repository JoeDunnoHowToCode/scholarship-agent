"""學程首頁候選連結的單元測試（ADR-031 第 3 層）。"""

from app.features.sources import links

PAGE_URL = "https://www.example.eu/programme/"


def test_candidate_links_keeps_same_site_absolute_urls() -> None:
    # 相對網址轉成完整網址；只留同一個網站的連結，開頭的 www. 有沒有都算同站
    html = """
    <a href="apply">How to   apply</a>
    <a href="https://example.eu/scholarships">Scholarships</a>
    <a href="https://WWW.EXAMPLE.EU/contact">Contact</a>
    <a href="https://other.eu/partner">Partner university</a>
    <a href="https://sub.example.eu/news">Subdomain news</a>
    """
    assert links.candidate_links(html, PAGE_URL) == [
        links.Link(url="https://www.example.eu/programme/apply", text="How to apply"),
        links.Link(url="https://example.eu/scholarships", text="Scholarships"),
        links.Link(url="https://WWW.EXAMPLE.EU/contact", text="Contact"),
    ]


def test_candidate_links_removes_fragments_duplicates_and_the_page_itself() -> None:
    # # 後面的錨點只在瀏覽器裡跳位置，去掉後才比較；同一網址只留第一次出現的那個（連同它的文字）；
    # 連回本頁的連結（不論有沒有結尾的 /）沒有新資訊，也不留。
    # 只有圖示沒有文字的連結，改用 aria-label 或 title 當文字
    html = """
    <a href="apply#deadlines" aria-label="Apply now"><img src="arrow.svg"></a>
    <a href="apply">Apply</a>
    <a href="#main-content">Skip to content</a>
    <a href="https://www.example.eu/programme">Home</a>
    <a href="contact" title="Contact us"></a>
    <a href="news"><span></span></a>
    """
    assert links.candidate_links(html, PAGE_URL) == [
        links.Link(url="https://www.example.eu/programme/apply", text="Apply now"),
        links.Link(url="https://www.example.eu/programme/contact", text="Contact us"),
        links.Link(url="https://www.example.eu/programme/news", text=""),
    ]
