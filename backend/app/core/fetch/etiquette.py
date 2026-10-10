"""爬蟲禮儀（ADR-028）：robots.txt 判斷與被擋偵測。"""

# 整頁攔截的驗證碼頁才有的特徵；不用「captcha」這種字，
# 因為一般頁面的表單也常內嵌驗證碼元件，那不算被擋
CHALLENGE_MARKERS = (
    "challenge-platform",
    "cf-chl",
    "<title>just a moment",
    "verify you are human",
)


def robots_allows(status: int, robots_txt: str, url: str, user_agent: str) -> bool:
    return status < 500


def detect_block(status: int, body: str) -> str | None:
    """被擋就回傳原因（「403」「429」「captcha」），沒被擋回傳 None。"""
    if status in (403, 429):
        return str(status)
    lowered = body.lower()
    if any(marker in lowered for marker in CHALLENGE_MARKERS):
        return "captcha"
    return None
