"""agent 的三種工具（ADR-084）：用假的搜尋與讀網頁測試，不連網。"""

from typing import Any

import pytest

from app.features.discovery.agent import StopAgent, Tool
from app.features.discovery.tools import (
    PAGE_CHARS,
    PAGE_LINKS,
    Page,
    SearchHit,
    SearchUnavailable,
    Toolbox,
    page_links,
)
from app.features.sources.links import Link

HITS = [SearchHit("Lund Global Scholarship", "https://www.lunduniversity.lu.se/scholarships", "Tuition fee scholarship")]


def search(query: str) -> list[SearchHit]:
    return HITS


def read(url: str) -> Page:
    return Page(url, "Scholarships for master's students", [Link("https://www.lu.se/apply", "How to apply")])


def tool(box: Toolbox, name: str) -> Tool:
    found = {t.spec.name: t for t in box.tools()}
    assert name in found, f"沒有 {name} 工具"
    return found[name]


def use(box: Toolbox, name: str, **args: Any) -> str:
    return tool(box, name).run(args)


def test_offers_exactly_three_tools() -> None:
    box = Toolbox(search, read, searches_left=10)
    assert sorted(t.spec.name for t in box.tools()) == ["read_page", "search", "submit"]
    # 逐校找不給搜尋（只在學校網站裡找）
    assert sorted(t.spec.name for t in box.tools(with_search=False)) == ["read_page", "submit"]


def test_submit_only_accepts_urls_seen_in_this_run() -> None:
    box = Toolbox(search, read, searches_left=10, start_urls=["https://www.lu.se/"])
    # AI 自己編的網址：拒收
    assert "沒看過" in use(box, "submit", url="https://made-up.example/scholarship", reason="猜的")
    assert box.submissions == []
    # 搜尋結果裡的網址、讀過的頁面上的連結：可以
    use(box, "search", query="Lund scholarship")
    use(box, "read_page", url="https://www.lu.se/")
    assert "已提交" in use(box, "submit", url="https://www.lunduniversity.lu.se/scholarships", reason="獎學金頁")
    assert "已提交" in use(box, "submit", url="https://www.lu.se/apply", reason="申請頁")
    # 同一個網址再提交一次不重複
    use(box, "submit", url="https://www.lu.se/apply", reason="又一次")
    assert [s.url for s in box.submissions] == ["https://www.lunduniversity.lu.se/scholarships", "https://www.lu.se/apply"]


def test_submissions_are_capped_per_run() -> None:
    box = Toolbox(search, read, searches_left=10, max_submissions=1)
    use(box, "search", query="q")
    use(box, "read_page", url=HITS[0].url)
    use(box, "submit", url=HITS[0].url, reason="一")
    assert "上限" in use(box, "submit", url="https://www.lu.se/apply", reason="二")
    assert len(box.submissions) == 1


def test_read_page_only_opens_seen_urls_and_truncates() -> None:
    long_page = Page("https://www.lu.se/", "字" * (PAGE_CHARS + 500), [Link(f"https://www.lu.se/{n}", f"連結{n}") for n in range(200)])
    box = Toolbox(search, lambda url: long_page, searches_left=10, start_urls=["https://www.lu.se/"])
    assert "沒看過" in use(box, "read_page", url="https://elsewhere.example/")
    result = use(box, "read_page", url="https://www.lu.se/")
    assert "已截斷" in result and "字" * PAGE_CHARS in result and "字" * (PAGE_CHARS + 1) not in result
    assert f"https://www.lu.se/{PAGE_LINKS - 1}" in result and f"https://www.lu.se/{PAGE_LINKS}" not in result


def test_search_stops_the_run_when_the_quota_is_used_up() -> None:
    box = Toolbox(search, read, searches_left=1)
    assert "Lund Global Scholarship" in use(box, "search", query="q")  # 第一次可以，結果列出標題與網址
    with pytest.raises(StopAgent, match="本月"):
        use(box, "search", query="q")  # 本月次數用完


def test_search_service_errors_stop_the_run() -> None:
    def broken(query: str) -> list[SearchHit]:
        raise SearchUnavailable("Tavily 額度用完（432）")

    with pytest.raises(StopAgent, match="432"):
        use(Toolbox(broken, read, searches_left=10), "search", query="q")


def test_page_links_include_other_sites_but_not_files() -> None:
    html = (
        '<a href="/apply">Apply</a><a href="https://other.eu/x">Partner</a>'
        '<a href="/guide.pdf">PDF</a><a href="mailto:a@b.eu">Mail</a>'
    )
    links = page_links(html, "https://www.lu.se/")
    assert [(link.url, link.text) for link in links] == [("https://www.lu.se/apply", "Apply"), ("https://other.eu/x", "Partner")]
