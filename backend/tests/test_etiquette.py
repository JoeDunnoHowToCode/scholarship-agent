"""爬蟲禮儀的單元測試（ADR-028）：被擋偵測與 robots.txt 判斷。"""

import pytest

from app.core.fetch import etiquette


@pytest.mark.parametrize(
    "body",
    ["<html><p>Scholarships</p></html>", '<form><div class="g-recaptcha"></div></form>'],
    ids=["plain_page", "embedded_captcha_widget"],
)
def test_detect_block_normal_response_is_not_blocked(body: str) -> None:
    # 一般頁面就算表單裡內嵌驗證碼元件，也不算被擋
    assert etiquette.detect_block(200, body) is None


def test_detect_block_status_403() -> None:
    # 403 Forbidden：網站拒絕我們
    assert etiquette.detect_block(403, "Forbidden") == "403"


def test_detect_block_status_429() -> None:
    # 429 Too Many Requests：網站嫌我們太頻繁
    assert etiquette.detect_block(429, "Too Many Requests") == "429"


def test_detect_block_captcha_page() -> None:
    # 整頁都是「先證明你是人」的攔截頁，即使狀態是 200 也算被擋
    body = (
        "<html><title>Just a moment...</title>"
        "<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'></script>"
        "</html>"
    )
    assert etiquette.detect_block(200, body) == "captcha"


def test_robots_4xx_means_allowed() -> None:
    # RFC 9309：robots.txt 不存在（例如教育部回 404）就視為允許
    url = "https://ws.moe.edu.tw/001/x.pdf"
    assert etiquette.robots_allows(404, "", url, "python-httpx/0.28.1") is True
