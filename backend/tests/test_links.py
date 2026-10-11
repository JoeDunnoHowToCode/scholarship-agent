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


def test_candidate_links_excludes_files_and_non_web_links() -> None:
    # 檔案（看路徑的副檔名，大小寫不拘）不是網頁，交給 AI 挑也打不開；
    # mailto:、javascript:、ftp:// 也不是 http/https 網頁，都不留
    html = """
    <a href="brochure.PDF">Brochure</a>
    <a href="/files/form.pdf?v=2">Application form</a>
    <a href="a.doc">doc</a><a href="a.docx">docx</a>
    <a href="a.xls">xls</a><a href="a.xlsx">xlsx</a>
    <a href="a.ppt">ppt</a><a href="a.pptx">pptx</a>
    <a href="a.zip">zip</a><a href="a.jpg">jpg</a><a href="a.jpeg">jpeg</a>
    <a href="a.png">png</a><a href="a.gif">gif</a><a href="a.svg">svg</a>
    <a href="a.mp4">mp4</a>
    <a href="mailto:info@example.eu">Email us</a>
    <a href="javascript:void(0)">Menu</a>
    <a href="ftp://example.eu/archive">Archive</a>
    <a href="admission.html">Admission</a>
    """
    assert links.candidate_links(html, PAGE_URL) == [
        links.Link(url="https://www.example.eu/programme/admission.html", text="Admission"),
    ]
