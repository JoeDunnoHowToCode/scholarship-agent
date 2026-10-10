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
