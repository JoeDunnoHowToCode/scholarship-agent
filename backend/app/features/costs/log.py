"""寫入與查詢費用紀錄（ADR-089）。呼叫的人負責 commit。"""

from datetime import datetime

from sqlalchemy.orm import Session


def record_call(
    session: Session,
    prompt: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    error: str | None,
    source_id: int | None = None,
    run_id: int | None = None,
) -> None:
    """記一筆 AI 呼叫；功能與提示詞版本從送出的文字認出來。"""
    # 骨架


def month_total_usd(session: Session, now: datetime) -> float:
    """本月（台灣時間的月份）到現在花了多少美元。"""
    return 0.0  # 骨架
