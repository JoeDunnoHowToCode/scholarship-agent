"""寫入與查詢費用紀錄（ADR-089）。呼叫的人負責 commit。"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import prompts
from app.features.costs.models import LLMCall
from app.features.costs.usage import month_start


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
    version = prompts.identify(prompt)
    session.add(LLMCall(
        feature=version.rsplit("-", 1)[0] if version else "unknown",  # extract-12 → extract
        prompt_version=version, model=model, input_tokens=input_tokens, output_tokens=output_tokens,
        cost_usd=cost_usd, error=error, source_id=source_id, run_id=run_id,
    ))


def month_total_usd(session: Session, now: datetime) -> float:
    """本月（台灣時間的月份）到現在花了多少美元。"""
    total = session.scalar(select(func.sum(LLMCall.cost_usd)).where(LLMCall.called_at >= month_start(now)))
    return float(total or 0.0)
