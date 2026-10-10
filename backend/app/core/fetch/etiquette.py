"""爬蟲禮儀（ADR-028）：robots.txt 判斷與被擋偵測。"""


def detect_block(status: int, body: str) -> str | None:
    if status in (403, 429):
        return str(status)
    return None
