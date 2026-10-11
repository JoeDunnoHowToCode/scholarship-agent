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
