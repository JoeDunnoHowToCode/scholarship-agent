"""找新網址（ADR-080）：抓不到的來源，由 agent 找現在的官方網址；確認是同一個學程才換。"""


def same_programme(names: list[str], provider: str | None, page_text: str) -> bool:
    """新網頁是不是同一個學程：找得到名稱或縮寫，而且（主辦單位有特別的字時）找得到其中一個。

    不分大小寫、忽略標點（「Claude 自行決定」第 12 點）。
    """
    return False  # 骨架
