"""跑一次 agent 並留下紀錄（ADR-082、086、089）：建立執行紀錄 → 跑迴圈 → 寫結果。

用法：uv run python -m app.features.discovery.runner --smoke [--max-cost NT$]   真的跑一次小任務，確認整條路通
"""

import argparse
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.core import prompts
from app.core.fetch.http import HttpFetcher
from app.core.llm.base import ToolCallingLLM
from app.features.costs.llm import gemini
from app.features.costs.usage import NTD_PER_USD
from app.features.discovery.agent import Outcome, run_agent
from app.features.discovery.models import AgentRun
from app.features.discovery.services import (
    fetch_page,
    searches_this_month,
    tavily_search,
)
from app.features.discovery.tools import (
    SEARCHES_PER_MONTH,
    SearchHit,
    SearchUnavailable,
    Toolbox,
)
from app.features.discovery.trace import DbStepLog
from app.shared.db import SessionLocal
from app.shared.settings import settings

SMOKE_VERSION = "agent-smoke-1"


def execute(
    task: str,
    target: str | None,
    system: str,
    task_text: str,
    toolbox: Toolbox,
    with_search: bool,
    max_steps: int,
    max_cost_usd: float,
    make_llm: Callable[[int], ToolCallingLLM],
    sessions: Callable[[], Session] = SessionLocal,
) -> tuple[int, Outcome]:
    """回傳（agent_runs.id, 結果）。出錯時記成 error 再往外丟，讓背景工作照 ADR-056 分類。"""
    with sessions() as session:
        run = AgentRun(task=task, target=target)
        session.add(run)
        session.commit()
        run_id = run.id
    log = DbStepLog(run_id, sessions)
    try:
        outcome = run_agent(make_llm(run_id), system, task_text, toolbox.tools(with_search), log, max_steps, max_cost_usd)
    except Exception as error:
        _finish(sessions, run_id, "error", None, f"{type(error).__name__}: {error}")
        raise
    _finish(sessions, run_id, outcome.result, outcome, outcome.final_text)
    return run_id, outcome


def _finish(sessions: Callable[[], Session], run_id: int, result: str, outcome: Outcome | None, text: str) -> None:
    with sessions() as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            return
        run.result, run.final_text, run.finished_at = result, text[:2000], datetime.now(UTC)
        if outcome is not None:
            run.steps, run.cost_usd = outcome.steps, outcome.cost_usd
        session.commit()


def real_toolbox(http: httpx.Client, fetcher: HttpFetcher, start_urls: list[str], max_submissions: int) -> Toolbox:
    """連網的工具箱：Tavily 搜尋、用現有抓取程式讀網頁；本月剩幾次搜尋從資料庫算。"""
    key = settings.tavily_api_key

    def search(query: str) -> list[SearchHit]:
        if key is None:
            raise SearchUnavailable("沒有 Tavily 金鑰：請在 backend/.env 設定 TAVILY_API_KEY")
        return tavily_search(http, key, query)

    with SessionLocal() as session:
        left = SEARCHES_PER_MONTH - searches_this_month(session, datetime.now(UTC))
    return Toolbox(search, lambda url: fetch_page(fetcher, url), left, start_urls, max_submissions)


def main() -> None:
    parser = argparse.ArgumentParser(description="真的跑一次 agent 小任務")
    parser.add_argument("--smoke", action="store_true", help="找 Lund University 的獎學金頁，確認工具都能用")
    parser.add_argument("--max-cost", type=float, default=1.0, help="這次執行的 AI 費用上限（新台幣）")
    args = parser.parse_args()
    if not args.smoke:
        parser.error("目前只有 --smoke")
    with httpx.Client() as http:
        fetcher = HttpFetcher(settings.fetch_min_interval_seconds)
        try:
            box = real_toolbox(http, fetcher, [], max_submissions=1)
            run_id, outcome = execute(
                "smoke", None, prompts.load(SMOKE_VERSION), "開始", box, True, 8, args.max_cost / NTD_PER_USD,
                make_llm=lambda run_id: gemini(agent_run_id=run_id),
            )
        finally:
            fetcher.close()
    print(f"agent_runs #{run_id}：{outcome.result}，{outcome.steps} 步，約 NT${outcome.cost_usd * NTD_PER_USD:.2f}")
    print(f"最後：{outcome.final_text}")
    print("提交：", [s.url for s in box.submissions] or "沒有")
    print(f"每一步：uv run python -m app.features.discovery.trace {run_id}")


if __name__ == "__main__":
    main()
