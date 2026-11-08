"""三種發掘任務（ADR-080、083）：逐校找、搜尋補漏、找新網址。每個任務跑一次 agent，再把結果寫回資料庫。

用法：uv run python -m app.features.discovery.run --universities 10 --search --new-urls 1 --max-cost 20
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.llm.base import ToolCallingLLM
from app.features.discovery.tools import Page, Toolbox
from app.shared.db import SessionLocal

UNIVERSITY_VERSION = "agent-university-1"
SEARCH_VERSION = "agent-search-1"
NEW_URL_VERSION = "agent-new-url-1"
STEPS = {"universities": 15, "search": 25, "new_url": 15}  # 「Claude 自行決定」第 5 點
SUBMISSIONS = {"universities": 3, "search": 10, "new_url": 1}


@dataclass
class Deps:
    """任務需要的外部能力；測試時全部換成假的。"""

    make_llm: Callable[[int], ToolCallingLLM]  # agent_runs.id → 模型（費用記到這次執行）
    toolbox: Callable[[list[str], int], Toolbox]  # （起點網址, 最多提交幾個）→ 工具箱
    read: Callable[[str], Page]  # 找新網址時，打開 agent 提議的網址再確認一次
    max_cost_usd: float
    sessions: Callable[[], Session] = SessionLocal


def run_university(deps: Deps, school_id: int, now: datetime) -> int:
    """逐校找一所學校，回傳新增幾個候選。"""
    return 0  # 骨架


def run_search(deps: Deps, now: datetime) -> int | None:
    """搜尋補漏，回傳新增幾個候選；這週（台灣時間的 ISO 週）已經搜尋過就回傳 None。"""
    return None  # 骨架


def run_new_url(deps: Deps, source_id: int, now: datetime) -> tuple[str, str, str] | None:
    """替抓不到的來源找新網址，回傳（結果, 名稱, 說明）；結果是 replaced、mismatch、not_found。

    這個來源 7 天內找過就回傳 None。
    """
    return None  # 骨架
