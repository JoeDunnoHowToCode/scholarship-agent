"""AI 挑連結（ADR-031 第 3 層）：從學程首頁的候選連結裡，挑出申請與獎學金頁。"""

from pydantic import BaseModel, Field

from app.core.llm.base import StructuredLLM
from app.features.sources.links import Link

PROMPT_VERSION = "links-1"  # 改提示詞就要改版本號
MAX_PICKS = 3  # 每個學程最多再抓 3 頁（docs/day-03.md「Claude 自行決定」第 5 點）
MAX_CANDIDATES = 200  # 連結太多的網站只給前 200 個，避免提示詞太長

PROMPT = """你在幫忙找留學獎學金的資訊。下面是「{name}」學程首頁（{url}）上的連結。
請挑出最多 {max_picks} 個最可能寫著以下資訊的頁面：申請方式與截止日、獎學金（金額、名額、資格）、
入學資格、要交的文件。只能從清單裡挑，網址要照抄；都不相關就回傳空清單。

連結清單（連結文字 | 網址）：
{links}
"""


class PickedLinks(BaseModel):
    urls: list[str] = Field(description="挑中的網址，照抄清單裡的網址，最多 3 個")


def pick_links(llm: StructuredLLM, name: str, url: str, links: list[Link]) -> list[str]:
    candidates = links[:MAX_CANDIDATES]
    listing = "\n".join(f"- {link.text or '（無文字）'} | {link.url}" for link in candidates)
    prompt = PROMPT.format(name=name, url=url, max_picks=MAX_PICKS, links=listing)
    picked = llm.extract(prompt, PickedLinks).urls
    # 只收清單裡真的有的網址：防止模型編造或改寫網址
    allowed = {link.url for link in candidates}
    return [u for u in dict.fromkeys(picked) if u in allowed][:MAX_PICKS]
