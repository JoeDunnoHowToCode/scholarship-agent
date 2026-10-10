"""爬蟲禮儀（ADR-028）：robots.txt 判斷與被擋偵測。"""

from protego import Protego

# 整頁攔截的驗證碼頁才有的特徵；不用「captcha」這種字，
# 因為一般頁面的表單也常內嵌驗證碼元件，那不算被擋
CHALLENGE_MARKERS = (
    "challenge-platform",
    "cf-chl",
    "<title>just a moment",
    "verify you are human",
)


def robots_allows(status: int, robots_txt: str, url: str, user_agent: str) -> bool:
    """依 RFC 9309 判斷能不能抓：robots.txt 回 5xx 視為禁止、4xx 視為允許，200 照規則。"""
    if status >= 500:
        return False
    if status >= 400:
        return True
    # Protego 支援 RFC 9309 的萬用字元（* 和 $），Python 3.13 內建的解析器不支援
    return Protego.parse(robots_txt).can_fetch(url, user_agent)


def detect_block(status: int, body: str) -> str | None:
    """被擋就回傳原因（「403」「429」「captcha」），沒被擋回傳 None。"""
    if status in (403, 429):
        return str(status)
    lowered = body.lower()
    if any(marker in lowered for marker in CHALLENGE_MARKERS):
        return "captcha"
    return None
