"""三種發掘任務（ADR-080、083）：逐校找、搜尋補漏、找新網址。每個任務跑一次 agent，再把結果寫回資料庫。

用法：uv run python -m app.features.discovery.run --universities 10 --search --new-urls 1 --max-cost 20
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial

import httpx
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core import prompts
from app.core.fetch.http import HttpFetcher
from app.core.llm.base import ToolCallingLLM
from app.features.costs.llm import gemini
from app.features.costs.usage import NTD_PER_USD, TAIPEI
from app.features.discovery.intake import add_candidates
from app.features.discovery.models import AgentRun, University
from app.features.discovery.new_url import decide_new_url
from app.features.discovery.runner import execute, real_toolbox
from app.features.discovery.services import fetch_page
from app.features.discovery.tasks import new_url_task, search_task, university_task
from app.features.discovery.tools import Page, Toolbox
from app.features.discovery.universities import PER_DAY, RESEARCH_AFTER, todays_batch
from app.features.notifications.generate import add_system_event
from app.features.pipeline.errors import classify
from app.features.pipeline.report import new_url_digest_message
from app.features.profiles.service import CURRENT_USER_ID, get_profile
from app.features.scholarships.models import Scholarship
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal
from app.shared.settings import settings

UNIVERSITY_VERSION = "agent-university-1"
SEARCH_VERSION = "agent-search-1"
NEW_URL_VERSION = "agent-new-url-1"
STEPS = {"universities": 15, "search": 25, "new_url": 15}  # 「Claude 自行決定」第 5 點
SUBMISSIONS = {"universities": 3, "search": 10, "new_url": 1}
MAX_COST_NTD = 2.0  # 每次 agent 執行最多花多少（「Claude 自行決定」第 5 點）
NEW_URL_EVERY = timedelta(days=7)  # 同一個來源 7 天找一次新網址（和 ADR-080 的每 7 天重試一致）


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
    with deps.sessions() as session:
        school = session.get(University, school_id)
        if school is None:
            return 0
        task, homepage = university_task(school.name, school.country, school.homepage), school.homepage
    box = deps.toolbox([homepage], SUBMISSIONS["universities"])
    run_id, outcome = execute(
        "universities", f"university:{school_id}", prompts.load(UNIVERSITY_VERSION), task, box,
        False, STEPS["universities"], deps.max_cost_usd, deps.make_llm, deps.sessions,  # 只在學校網站裡找，不給搜尋
    )
    with deps.sessions() as session:
        added = add_candidates(session, box.submissions, SourceKind.UNIVERSITY, run_id)
        school = session.get(University, school_id)
        if school is not None:
            school.last_searched_at, school.last_result = now, outcome.result
        session.commit()
    return added


def run_search(deps: Deps, now: datetime) -> int | None:
    """搜尋補漏，回傳新增幾個候選；這週（台灣時間的 ISO 週）已經搜尋過就回傳 None。"""
    today = now.astimezone(TAIPEI).date()
    monday = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time(), TAIPEI)
    with deps.sessions() as session:
        if session.scalar(select(exists().where(AgentRun.task == "search", AgentRun.started_at >= monday))):
            return None
        # 個人資料只經過 search_task（裡面只用 applicant_text：科系、領域，ADR-087）
        task = search_task(get_profile(session, CURRENT_USER_ID), today)
    box = deps.toolbox([], SUBMISSIONS["search"])
    run_id, _ = execute(
        "search", None, prompts.load(SEARCH_VERSION), task, box,
        True, STEPS["search"], deps.max_cost_usd, deps.make_llm, deps.sessions,
    )
    with deps.sessions() as session:
        added = add_candidates(session, box.submissions, SourceKind.INSTITUTION, run_id)
        session.commit()
    return added


def run_new_url(deps: Deps, source_id: int, now: datetime) -> tuple[str, str, str] | None:
    """替抓不到的來源找新網址，回傳（結果, 名稱, 說明）；結果是 replaced、mismatch、not_found。

    這個來源 7 天內找過就回傳 None。
    """
    target = f"source:{source_id}"
    with deps.sessions() as session:
        recent = AgentRun.task == "new_url", AgentRun.target == target, AgentRun.started_at >= now - NEW_URL_EVERY
        source = session.get(Source, source_id)
        if source is None or session.scalar(select(exists().where(*recent))):
            return None
        row = session.scalars(select(Scholarship).where(Scholarship.source_id == source_id)).first()
        name, old = source.name, source.url
        task = new_url_task(name, row.name if row else None, row.provider if row else None, old)
    box = deps.toolbox([], SUBMISSIONS["new_url"])
    execute(
        "new_url", target, prompts.load(NEW_URL_VERSION), task, box,
        True, STEPS["new_url"], deps.max_cost_usd, deps.make_llm, deps.sessions,
    )
    if not box.submissions:
        return "not_found", name, ""
    url = box.submissions[0].url
    try:
        page = deps.read(url)  # 用程式再打開一次，確認的是我們自己抓到的內容，不是 agent 說的
    # 故意接住所有錯誤：打不開新網址就當成對不上，不讓一個來源拖垮整批
    except Exception as error:  # noqa: BLE001
        return "mismatch", name, f"{url}（打不開：{type(error).__name__}）"
    with deps.sessions() as session:
        source = session.get(Source, source_id)
        if source is None:
            return None
        replaced, reason = decide_new_url(session, source, url, page.text)
        superseded = not replaced and not source.enabled  # 目錄裡已有新來源，舊的被停用（11-08 使用者選 B）
        session.commit()
    if replaced:
        return "replaced", name, f"{old} → {url}"
    return ("superseded", name, reason) if superseded else ("mismatch", name, f"{url}（{reason}）")


def new_url_targets(session: Session, now: datetime) -> list[int]:
    """今天要找新網址的來源：被標成抓不到（ADR-080）、還啟用中、7 天內沒找過。"""
    searched = select(AgentRun.target).where(AgentRun.task == "new_url", AgentRun.started_at >= now - NEW_URL_EVERY)
    recent = {target for target in session.scalars(searched) if target}
    rows = session.scalars(
        select(Source.id).where(Source.unreachable_since.is_not(None), Source.enabled.is_(True)).order_by(Source.id)
    )
    return [source_id for source_id in rows if f"source:{source_id}" not in recent]


@dataclass
class Summary:
    new_urls: list[tuple[str, str, str]]  # 找新網址的結果
    searched: int | None  # 搜尋補漏新增幾個候選；這週已經搜尋過是 None
    schools: int  # 逐校找了幾所
    candidates: int  # 逐校找新增幾個候選
    errors: int  # 出錯跳過的任務數
    stopped: str | None  # 暫停 AI 的原因（例如每月上限）；有值代表整批停下


def discover(deps: Deps, now: datetime, schools: list[int], search: bool, new_urls: list[int]) -> Summary:
    """依序跑：找新網址 → 搜尋補漏 → 逐校找。暫停 AI 的錯誤就整批停下；其他錯誤跳過那個任務。"""
    summary = Summary([], None, 0, 0, 0, None)

    def attempt(task: Callable[[], object]) -> tuple[bool, object]:
        """跑一個任務：（成功了沒, 結果）。暫停 AI 的錯誤記在 summary.stopped，呼叫的人看到就停。"""
        try:
            return True, task()
        # 故意接住所有錯誤：每個錯誤都要分類（ADR-056），一個任務出錯不拖垮整批
        except Exception as error:  # noqa: BLE001
            if classify(error) == "pause_ai":
                summary.stopped = f"{type(error).__name__}: {error}"
            else:
                summary.errors += 1
                print(f"discovery  任務出錯，跳過：{type(error).__name__}: {error}")
            return False, None

    for source_id in new_urls:
        ok, result = attempt(partial(run_new_url, deps, source_id, now))
        if summary.stopped:
            return summary
        if ok and isinstance(result, tuple):
            summary.new_urls.append(result)
    if search:
        ok, result = attempt(partial(run_search, deps, now))
        if summary.stopped:
            return summary
        summary.searched = result if ok and isinstance(result, int) else None
    for school_id in schools:
        ok, result = attempt(partial(run_university, deps, school_id, now))
        if summary.stopped:
            return summary
        summary.schools += 1
        if ok and isinstance(result, int):
            summary.candidates += result
        elif not ok:
            _retry_school_later(deps, school_id, now)
    return summary


def _retry_school_later(deps: Deps, school_id: int, now: datetime) -> None:
    """出錯的學校 7 天後再試，不要每天都排第一個佔名額（「Claude 自行決定」第 29 點）。"""
    with deps.sessions() as session:
        school = session.get(University, school_id)
        if school is not None:
            school.last_result = "error"
            school.last_searched_at = now - RESEARCH_AFTER + timedelta(days=7)
            session.commit()


def real_deps(http: httpx.Client, fetcher: HttpFetcher, max_cost_usd: float) -> Deps:
    """連網的版本：Gemini（費用記到每次執行）、Tavily、現有的抓取程式。"""
    return Deps(
        make_llm=lambda run_id: gemini(agent_run_id=run_id),
        toolbox=lambda starts, limit: real_toolbox(http, fetcher, starts, limit),
        read=lambda url: fetch_page(fetcher, url),
        max_cost_usd=max_cost_usd,
    )


def schools_left_today(session: Session, now: datetime, per_day: int = PER_DAY) -> list[int]:
    """今天還能找的學校：每天最多 per_day 所，今天已經找過的算進去（工作重跑也不會多找）。"""
    today = datetime.combine(now.astimezone(TAIPEI).date(), datetime.min.time(), TAIPEI)
    done = session.scalar(select(func.count()).select_from(University).where(University.last_searched_at >= today))
    return [school.id for school in todays_batch(session, now, max(0, per_day - int(done or 0)))]


def notify_new_urls(session: Session, results: list[tuple[str, str, str]], now: datetime) -> bool:
    """找新網址的結果一天合成一則（ADR-093）；全部都沒找到就不送。呼叫的人負責 commit。"""
    message = new_url_digest_message(results)
    if message is None:
        return False
    title, lines = message
    return add_system_event(session, CURRENT_USER_ID, f"new-url-day:{now.astimezone(TAIPEI).date()}", title, lines, now)


def describe(summary: Summary) -> str:
    searched = "這週已搜尋過" if summary.searched is None else f"新增候選 {summary.searched}"
    found = sum(1 for kind, _, _ in summary.new_urls if kind == "replaced")
    text = (
        f"找新網址 {len(summary.new_urls)} 個（換了 {found}）；搜尋補漏：{searched}；"
        f"逐校找 {summary.schools} 所、新增候選 {summary.candidates}；出錯跳過 {summary.errors}"
    )
    return text + (f"；暫停：{summary.stopped}" if summary.stopped else "")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="手動跑發掘任務（每天收尾後也會自動跑）")
    parser.add_argument("--universities", type=int, default=0, help="逐校找幾所")
    parser.add_argument("--search", action="store_true", help="搜尋補漏（每週一次，這週跑過就略過）")
    parser.add_argument("--new-urls", type=int, default=0, help="替幾個抓不到的來源找新網址")
    parser.add_argument("--max-cost", type=float, default=MAX_COST_NTD, help="每次 agent 執行的 AI 費用上限（新台幣）")
    args = parser.parse_args()
    now = datetime.now(UTC)
    with SessionLocal() as session:
        schools = [s.id for s in todays_batch(session, now, args.universities)] if args.universities else []
        targets = new_url_targets(session, now)[: args.new_urls]
    with httpx.Client() as http:
        fetcher = HttpFetcher(settings.fetch_min_interval_seconds)
        try:
            summary = discover(real_deps(http, fetcher, args.max_cost / NTD_PER_USD), now, schools, args.search, targets)
        finally:
            fetcher.close()
    with SessionLocal() as session:
        notify_new_urls(session, summary.new_urls, now)
        session.commit()
    print(describe(summary))
    for kind, name, detail in summary.new_urls:
        print(f"  {kind:<9} {name}　{detail}")


if __name__ == "__main__":
    main()
