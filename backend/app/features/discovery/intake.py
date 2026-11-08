"""候選來源進出資料庫（ADR-078）：提交 → 候選 → 抽取後決定加入或排除；加入後持續檢查品質。

規則本身在 candidates.py（純邏輯）；這裡負責讀寫 sources。呼叫的人負責 commit。
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.features.discovery.tools import Submission
from app.features.sources.models import Source, SourceKind


def add_candidates(
    session: Session, submissions: list[Submission], kind: SourceKind, agent_run_id: int | None
) -> int:
    """agent 的提交變成候選來源；已經有的網址（包括已排除的）略過。回傳新增幾個。"""
    return 0  # 骨架


def pending_candidate_ids(session: Session, now: datetime) -> list[int]:
    """今天要評分的候選（最舊的先），不超過每週上限。"""
    return []  # 骨架


def decide_candidate(session: Session, source: Source, now: datetime) -> str:
    """候選抽取完之後：四條規則都過就加入（approved），否則排除（rejected）並記下原因。"""
    return ""  # 骨架


def track_extraction(session: Session, source: Source, now: datetime) -> bool:
    """agent 加的來源每次重新抽取後：更新連續抽不到的次數，到上限就停用。回傳這次有沒有停用。"""
    return False  # 骨架


def digest_items(
    session: Session, now: datetime
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """最近 7 天：加入（名稱, 網址）、排除（名稱, 原因）、停用（名稱, 原因）。"""
    return [], [], []  # 骨架
