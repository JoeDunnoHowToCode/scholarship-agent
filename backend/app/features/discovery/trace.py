"""把 agent 的每一步寫進資料庫（ADR-089），以及清掉超過 30 天的全文。

用法：uv run python -m app.features.discovery.trace <agent_run_id>   照順序印出某次執行的每一步
"""

import argparse
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.llm.base import Turn
from app.features.discovery.models import AgentRun, AgentStep
from app.shared.db import SessionLocal

KEEP_FULL_TEXT = timedelta(days=30)  # ADR-089
SUMMARY_CHARS = 200  # 「Claude 自行決定」第 8 點


class DbStepLog:
    """符合 agent.StepLog。每一步用自己的連線馬上 commit：執行到一半當掉，前面的步驟也還在。"""

    def __init__(self, agent_run_id: int, sessions: Callable[[], Session] = SessionLocal) -> None:
        self.agent_run_id = agent_run_id
        self._sessions = sessions

    def model(self, number: int, turn: Turn) -> None:
        message = turn.message
        calls = "；".join(f"呼叫 {c.name}({json.dumps(c.args, ensure_ascii=False)})" for c in message.tool_calls)
        full = "\n".join(part for part in (message.content, calls) if part)
        self._add(AgentStep(
            agent_run_id=self.agent_run_id, number=number, kind="model", summary=full[:SUMMARY_CHARS],
            full_text=full, input_tokens=turn.input_tokens, output_tokens=turn.output_tokens,
        ))

    def tool(self, number: int, name: str, args: dict[str, Any], result: str) -> None:
        self._add(AgentStep(
            agent_run_id=self.agent_run_id, number=number, kind="tool", tool=name, args=args,
            summary=result[:SUMMARY_CHARS], full_text=result,
        ))

    def _add(self, step: AgentStep) -> None:
        with self._sessions() as session:
            session.add(step)
            session.commit()


def clear_old_texts(session: Session, now: datetime) -> int:
    """把超過 30 天的全文清成空白，回傳清了幾筆；摘要、參數、tokens 保留。呼叫的人負責 commit。"""
    cleared = session.execute(
        update(AgentStep)
        .where(AgentStep.created_at < now - KEEP_FULL_TEXT, AgentStep.full_text.is_not(None))
        .values(full_text=None)
    )
    return int(cleared.rowcount)  # type: ignore[attr-defined]


def main() -> None:
    parser = argparse.ArgumentParser(description="照順序印出某次 agent 執行的每一步")
    parser.add_argument("agent_run_id", type=int)
    parser.add_argument("--full", action="store_true", help="印出全文（30 天內才有）")
    args = parser.parse_args()
    with SessionLocal() as session:
        run = session.get(AgentRun, args.agent_run_id)
        if run is None:
            raise SystemExit(f"沒有這次執行：{args.agent_run_id}")
        print(f"#{run.id} {run.task} {run.target or ''}：{run.result or '進行中'}，{run.steps} 步，約 US${run.cost_usd:.4f}")
        if run.final_text:
            print(f"  最後：{run.final_text[:SUMMARY_CHARS]}")
        steps = session.scalars(select(AgentStep).where(AgentStep.agent_run_id == run.id).order_by(AgentStep.id))
        for step in steps:
            head = f"{step.number:>3} {step.kind:<5}"
            if step.kind == "tool":
                head += f" {step.tool} {json.dumps(step.args, ensure_ascii=False)}"
            else:
                head += f" [tokens {step.input_tokens}/{step.output_tokens}]"
            print(head)
            text = step.full_text if args.full and step.full_text is not None else step.summary
            print("      " + text.replace("\n", "\n      "))


if __name__ == "__main__":
    main()
