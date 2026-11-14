"""背景工作（第 7 天，ADR-056、057、058），由 RQ 的 worker 執行。

- tick：每 15 分鐘一次（rq cron）。有網路、今天（台灣時間）還沒開始過、前一輪也收尾了（ADR-075），就開始今天的檢查
- process_source：每個到期的來源一件。抓取 → 內容有變才抽取 → 建索引
- finish_daily_run：等上面全部結束（成功或最後失敗都算）才收尾。更新申請期與封存 → 去重 → 評分 → 每日檢查報告（ADR-076）
"""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from redis import Redis
from rq import Queue, Retry, get_current_job
from rq.job import Dependency
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.fetch.http import HttpFetcher
from app.core.llm.gemini import GeminiEmbedder, GeminiLLM, LLMError
from app.features.costs.llm import gemini
from app.features.costs.summary import summarize
from app.features.discovery.duplicates import ai_same
from app.features.discovery.intake import (
    add_weekly_digest,
    pending_candidate_ids,
    review_after_extraction,
)
from app.features.discovery.run import (
    MAX_COST_NTD,
    describe,
    discover,
    new_url_targets,
    notify_new_urls,
    real_deps,
    schools_left_today,
)
from app.features.discovery.trace import clear_old_texts
from app.features.matching.score import score_all
from app.features.notifications.generate import add_system_event, generate
from app.features.notifications.models import Event
from app.features.notifications.send import send_events
from app.features.pipeline import breaker, unreachable
from app.features.pipeline.due import frequency_for, is_due
from app.features.pipeline.errors import (
    CostLimitError,
    classify,
    hopeless_cause,
    root_cause,
)
from app.features.pipeline.models import Run
from app.features.pipeline.report import (
    report_message,
    stale_message,
    waiting_message,
)
from app.features.profiles.service import CURRENT_USER_ID, get_profile
from app.features.scholarships import dedup
from app.features.scholarships.cycles import is_stale, refresh
from app.features.scholarships.extract import extract_source
from app.features.scholarships.models import EMBEDDING_DIMENSIONS, Scholarship
from app.features.scholarships.summary import ensure_summary, needs_summary
from app.features.search.index import index_scholarship, index_source
from app.features.search.models import Chunk
from app.features.sources.catalogue import CATALOGUE_URL, import_programmes
from app.features.sources.fetch import fetch_source, make_picker
from app.features.sources.models import Snapshot, Source, SourceStatus
from app.shared.db import SessionLocal
from app.shared.settings import settings

TAIPEI = ZoneInfo("Asia/Taipei")
# 暫時性錯誤（ADR-056）：1、5、30 分鐘後各重試一次；worker 要加 --with-scheduler 才會照時間重試
RETRY = Retry(max=3, interval=[60, 300, 1800])
SOURCE_TIMEOUT = 30 * 60  # 一個來源最多 30 分鐘（長文件要分段抽取）；RQ 預設只有 3 分鐘
FINISH_TIMEOUT = 60 * 60
RESULT_TTL = 2 * 24 * 3600  # 工作的結果留 2 天，收尾時才讀得到每個來源的結果（RQ 預設只留 500 秒）
SOURCE_MAX_COST_NTD = 5.0  # 一個來源平常不到 NT$1（第 6 天重抽 180 筆約 NT$34）；超過代表有異常
SCORE_MAX_COST_NTD = 20.0
NTD_PER_USD = 32  # 和其他指令一樣的粗估匯率
DISCOVERY_TIMEOUT = 4 * 60 * 60  # 發掘工作最多跑 4 小時（30 所學校，每所幾分鐘）


def queue() -> Queue:
    return Queue(connection=Redis.from_url(settings.redis_url))


def notify_soon() -> None:
    """放一件送出通知的工作（ADR-062）；沒網路時 worker 會等，送失敗依 RETRY 重試。"""
    queue().enqueue(send_events, retry=RETRY, job_timeout=10 * 60, result_ttl=RESULT_TTL)


def score_soon() -> None:
    """放一件評分工作（第 9 天：個人資料改了就在背景重新評分）；沒網路時 worker 會等。

    排在佇列最前面：每天的檢查可能正排著上百件來源工作，不必等它們做完。
    """
    queue().enqueue(score_today, retry=RETRY, job_timeout=FINISH_TIMEOUT, result_ttl=RESULT_TTL, at_front=True)


def notify_breaker(session: Session) -> None:
    """斷路器打開時通知你（ADR-013、056）；去重鍵用打開的時間，同一次打開只通知一次。"""
    row = breaker.get(session)
    if row is None or row.opened_at is None:
        return
    add_system_event(
        session, CURRENT_USER_ID, f"breaker:{row.opened_at.isoformat()}", "斷路器打開：AI 步驟暫停",
        [(row.reason or "")[:200], "處理好之後執行 uv run python -m app.features.pipeline.breaker --reset"],
        datetime.now(UTC),
    )
    session.commit()
    notify_soon()


def online() -> bool:
    """連得到外面的網路嗎（ADR-057：電腦白天常常沒連網）。"""
    try:
        httpx.head(settings.online_check_url, timeout=5)
    except httpx.HTTPError:
        return False
    return True


def taipei_date(moment: datetime | None = None) -> date:
    return (moment or datetime.now(UTC)).astimezone(TAIPEI).date()


def due_source_ids(session: Session, today: date) -> list[int]:
    """今天要檢查的來源（ADR-058）：依獎學金的狀態決定每天、每 7 天或每 30 天；需人工的不檢查。"""
    rows = session.execute(
        select(Source, Scholarship)
        .outerjoin(Scholarship, Scholarship.source_id == Source.id)
        .where(
            Source.enabled.is_(True),
            Source.status == SourceStatus.APPROVED,
            Source.manual_reason.is_(None),
        )
        .options(selectinload(Scholarship.cycles))
        .order_by(Source.id)
    ).all()
    # 發掘 agent 的候選（ADR-078）：每天排進檢查，抽完後決定加入或排除；受每週上限
    due: list[int] = pending_candidate_ids(session, datetime.now(UTC))
    for source, row in rows:
        stale, recheck = False, None
        if row is not None:
            real = [c.closes_at for c in row.cycles if not c.estimated]
            stale = bool(real) and is_stale(max(real), today)
            starts = [c.recheck_from for c in row.cycles if c.estimated and c.recheck_from]
            recheck = min(starts) if starts else None
        if source.unreachable_since is not None:
            # 標記成抓不到的來源（ADR-080）：從最後一次失敗起每 7 天再試一次
            if is_due("weekly", source.last_failed_on, today):
                due.append(source.id)
            continue
        frequency = frequency_for(row.status if row else None, stale)
        last = taipei_date(source.last_checked_at) if source.last_checked_at else None
        if is_due(frequency, last, today, recheck):
            due.append(source.id)
    return due


def process_source(source_id: int) -> dict[str, str]:
    """一個來源的每日流程（ADR-056）。回傳 {"result": 結果代碼, "detail": 說明}，RQ 會存起來給收尾用。

    暫時性錯誤往外丟，RQ 依 RETRY 稍後重跑整件（每一步都冪等，重跑結果一樣）；
    其他錯誤記下原因、不重試；Gemini 額度、金鑰或費用出問題就打開斷路器。
    """
    with SessionLocal() as session:
        source = session.get(Source, source_id)
        if source is None or source.manual_reason:
            return {"result": "skipped", "detail": "來源不存在或需人工"}
        ai_paused = breaker.is_open(session)
        picker, picker_llm = (None, None) if ai_paused else make_picker()
        fetcher = HttpFetcher(settings.fetch_min_interval_seconds)
        llm: GeminiLLM | None = None
        try:
            fetch_source(session, fetcher, source, picker)
            session.commit()
            if source.manual_reason:
                return {"result": "blocked", "detail": source.manual_reason}  # 被擋（ADR-028）
            if source.url == CATALOGUE_URL:
                import_programmes(session)  # 目錄多了新學程，就加進來源清單（第 3 天）
                session.commit()
                return {"result": "catalogue", "detail": "目錄已更新"}
            if ai_paused:
                return {"result": "fetch_only", "detail": "斷路器打開中：只抓取，不抽取"}
            if not session.scalar(select(exists().where(Snapshot.source_id == source.id))):
                return {"result": "skipped", "detail": "沒有快照可以抽"}
            llm = gemini(source_id=source.id)
            summary = extract_source(session, llm, source)
            session.commit()
            # 獎學金說明（docs/summary-plan.md）：整份重抽會換掉 extracted、說明跟著消失，所以抽完就補；
            # 原文沒變的已經是最新版本，不會再呼叫 AI；說明失敗不影響抽取本身
            row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).first()
            if row is not None and needs_summary(row):
                try:
                    ensure_summary(session, llm, row)
                    session.commit()
                except LLMError:
                    session.rollback()
            embedder = GeminiEmbedder(
                settings.embedding_model, settings.google_api_key, EMBEDDING_DIMENSIONS,
                settings.llm_requests_per_minute,
            )
            if source.status == SourceStatus.CANDIDATE:
                index_scholarship(session, embedder, source)  # 先有向量，才能和已有的獎學金比對是不是重複（E＋D）
            # ADR-078：候選就決定加入或排除（含重複比對，規則判斷不了才請 AI）；agent 加的來源檢查品質
            review = review_after_extraction(session, source, summary, datetime.now(UTC), ai_same(llm))
            session.commit()
            if review == "rejected":
                return {"result": "candidate_rejected", "detail": source.review_note or source.name}
            spent = sum(x.cost_usd() for x in (llm, picker_llm) if x is not None) * NTD_PER_USD
            if spent > SOURCE_MAX_COST_NTD:
                raise CostLimitError(f"來源 {source_id} 花了 NT${spent:.1f}，超過 NT${SOURCE_MAX_COST_NTD}")
            if summary == "noise":
                return {"result": "noise", "detail": "只有和獎學金無關的內容變了，沒重抽（ADR-079）"}
            has_chunks = session.scalar(select(exists().where(Chunk.source_id == source.id)))
            if summary == "unchanged" and has_chunks:
                return {"result": "unchanged", "detail": "內容沒變"}
            index_source(session, llm, embedder, source)
            index_scholarship(session, embedder, source)
            session.commit()
            # 加入的候選照常建好原文切段和向量（以前會提早結束，要等隔天才搜尋得到）
            return {"result": "candidate_approved" if review == "approved" else "extracted", "detail": summary}
        # 故意接住所有錯誤：每個錯誤都要分類（ADR-056），認不得的記下原因、跳過，不讓一個來源拖垮整批
        except Exception as error:  # noqa: BLE001
            session.rollback()
            return handle_error(session, source_id, error)
        finally:
            fetcher.close()


def handle_error(session: Session, source_id: int, error: Exception) -> dict[str, str]:
    """依錯誤種類處理（ADR-056）：重試就往外丟、暫停 AI 就打開斷路器、其他記下原因跳過。"""
    kind = classify(error)
    detail = f"{type(error).__name__}: {error}"
    if kind == "retry":
        raise error  # RQ 依 RETRY 稍後重跑整件
    if kind == "fail":
        if not online():
            raise error  # 電腦斷網時 DNS 也會說「網域不存在」：當成暫時的，交給 RQ 重試
        # 重試也不會好（網域不存在、對方憑證有問題）：今天直接算失敗，不重試（11-08 使用者要求）
        cause = hopeless_cause(error) or root_cause(error)  # 例如 gaierror、PageGone，報告才分得出種類
        detail = f"{type(cause).__name__}: {cause}"
        print(f"unreachable 來源 {source_id}：{detail}")
        return {"result": "unreachable", "detail": detail}
    if kind == "pause_ai":
        breaker.open_breaker(session, detail)
        session.commit()
        notify_breaker(session)
        print(f"breaker    來源 {source_id} 打開斷路器：{detail}")
        return {"result": "paused", "detail": detail}
    print(f"skipped    來源 {source_id}：{detail}")
    return {"result": "skipped", "detail": detail}


def outcome_of(source_id: int, is_failed: bool, exc_string: str | None, value: object) -> tuple[int, bool, str]:
    """一件來源工作的結果：（來源 id, 今天算不算失敗, 錯誤說明）。

    重試完還失敗的取錯誤訊息最後一行；回報 unreachable 的（重試沒用、沒重試）也算失敗。
    """
    if is_failed:
        lines = [line for line in (exc_string or "").splitlines() if line.strip()]
        return source_id, True, lines[-1].strip()[:150] if lines else ""
    if isinstance(value, dict) and value.get("result") == "unreachable":
        return source_id, True, str(value.get("detail", ""))[:150]
    return source_id, False, ""


def result_key(is_failed: bool, value: object) -> str:
    """每日報告要數的結果代碼；今天算失敗的一律是 failed。"""
    if is_failed or (isinstance(value, dict) and value.get("result") == "unreachable"):
        return "failed"
    return str(value["result"]) if isinstance(value, dict) else "unknown"


def summarize_dependencies() -> dict[str, int]:
    """收尾時數一數：今天每個來源的工作各是什麼結果；重試後仍失敗的算 failed。"""
    job = get_current_job()
    counts: Counter[str] = Counter()
    if job is None:
        return {}
    for dependency in job.fetch_dependencies():
        value = None if dependency.is_failed else dependency.return_value()
        counts[result_key(dependency.is_failed, value)] += 1
    return dict(counts)


def score_today() -> dict[str, Any]:
    """收尾的評分：AI 只重評內容有變的（ADR-059、060）；斷路器打開或沒有個人資料就跳過。"""
    with SessionLocal(expire_on_commit=False) as session:
        if breaker.is_open(session):
            return {"skipped": "斷路器打開中"}
        profile = get_profile(session, CURRENT_USER_ID)
        if profile is None:
            return {"skipped": "還沒有個人資料"}
        llm = gemini()
        counts: dict[str, Any] = score_all(session, llm, settings.llm_model, profile, SCORE_MAX_COST_NTD)
        return counts


def source_outcomes() -> list[tuple[int, bool, str]]:
    """收尾時看今天每個來源的工作：（來源 id, 重試後還是失敗, 最後一行錯誤訊息）。"""
    job = get_current_job()
    if job is None:
        return []
    outcomes = []
    for dependency in job.fetch_dependencies():
        result = dependency.latest_result() if dependency.is_failed else None
        value = None if dependency.is_failed else dependency.return_value()
        exc = result.exc_string if result is not None else None
        outcomes.append(outcome_of(int(dependency.args[0]), dependency.is_failed, exc, value))
    return outcomes


def track_unreachable(
    session: Session, outcomes: list[tuple[int, bool, str]], now: datetime
) -> tuple[list[tuple[str, str]], list[str]]:
    """依今天的結果更新每個來源的失敗天數（ADR-080）。

    回傳（今天新標記抓不到的（名稱, 錯誤）, 今天恢復的名稱），交給每日報告（11-08 使用者選 C，不再一則一則送）。
    """
    today = taipei_date(now)
    marked: list[tuple[str, str]] = []
    recovered: list[str] = []
    for source_id, failed, error in outcomes:
        source = session.get(Source, source_id)
        if source is None:
            continue
        # 為什麼抓不到（11-09 使用者選 B）：失敗就記下這次的錯誤（沒有錯誤訊息就保留上次的），成功就清掉
        source.last_error = (error or source.last_error) if failed else None
        state = (source.fail_days, source.last_failed_on, source.unreachable_since)
        (source.fail_days, source.last_failed_on, source.unreachable_since), notice = unreachable.next_state(
            state, failed, today
        )
        if notice is None:
            continue
        row = session.scalars(select(Scholarship).where(Scholarship.source_id == source_id)).first()
        name = row.name if row else source.name
        if notice == "unreachable":
            marked.append((name, error))
        else:
            recovered.append(name)
    return marked, recovered


def finish_daily_run(run_id: int) -> str:
    """當天所有來源的工作結束後收尾：更新申請期與封存 → 規則去重 → 評分，結果記在 runs。"""
    sources = summarize_dependencies()
    with SessionLocal() as session, session.begin():
        cycles = refresh(session, datetime.now(UTC))
    dedup.main()  # 規則去重（ADR-048），自己開交易、印出結果
    scores = score_today()
    with SessionLocal() as session, session.begin():
        marked, recovered = track_unreachable(session, source_outcomes(), datetime.now(UTC))  # ADR-080
        clear_old_texts(session, datetime.now(UTC))  # agent 步驟的全文只留 30 天（ADR-089）
        add_weekly_digest(session, datetime.now(UTC))  # 發掘 agent 的每週摘要（ADR-078）
        events = generate(session, CURRENT_USER_ID, datetime.now(UTC))  # 通知事件（ADR-062）
        run = session.get(Run, run_id)
        if run is not None:
            finished = datetime.now(UTC)
            run.finished_at = finished
            # JSONB 欄位整個重新指定（CLAUDE.md 程式規範）
            run.counts = {**run.counts, "sources": sources, "cycles": dict(cycles), "scores": scores, "events": events}
            # 每日檢查報告（ADR-076）：每一輪都讓你知道做了沒、做了什麼；同一輪只送一則（去重鍵 run:id）
            new_events = sum(n for kind, n in events.items() if kind.endswith(":pending"))
            # 這一輪那天（台灣日期）和本月的 AI 費用（ADR-089）
            spent = summarize(session, finished)
            ai_cost = (
                dict(spent.by_day).get(run.local_date, 0.0) * NTD_PER_USD,
                spent.month_usd * NTD_PER_USD,
                settings.monthly_cap_ntd,
            )
            title, lines = report_message(
                run.local_date, run.started_at, finished, sources, new_events, skipped_days(session, run), ai_cost,
                marked, recovered,
            )
            add_system_event(session, CURRENT_USER_ID, f"run:{run.id}", title, lines, finished)
    notify_soon()
    # 收尾後放一件發掘工作（ADR-080、083）：agent 跑得久，另外一件，不拖慢每日報告
    queue().enqueue(discover_today, job_timeout=DISCOVERY_TIMEOUT, result_ttl=RESULT_TTL)
    return f"收尾完成：來源 {sources}；申請期 {dict(cycles)}；評分 {scores}；通知事件 {events}"


def discover_today() -> str:
    """每天收尾後的發掘工作（ADR-080、083）：找新網址 → 搜尋補漏（每週）→ 逐校找（每天最多 30 所）。"""
    now = datetime.now(UTC)
    with SessionLocal() as session:
        if breaker.is_open(session):
            return "斷路器打開中：今天不跑發掘"
        targets, schools = new_url_targets(session, now), schools_left_today(session, now)
    with httpx.Client() as http:
        fetcher = HttpFetcher(settings.fetch_min_interval_seconds)
        try:
            summary = discover(real_deps(http, fetcher, MAX_COST_NTD / NTD_PER_USD), now, schools, True, targets)
        finally:
            fetcher.close()
    with SessionLocal() as session:
        if summary.stopped:
            breaker.open_breaker(session, summary.stopped)  # 例如本月 AI 達到上限（ADR-013、049）
            session.commit()
            notify_breaker(session)
        if notify_new_urls(session, summary.new_urls, now):
            session.commit()
            notify_soon()
    return describe(summary)


def start_run(session: Session, run: Run, source_ids: list[int]) -> None:
    """放進佇列：每個來源一件 process_source，再放一件等它們全部結束才執行的 finish_daily_run。"""
    q = queue()
    jobs = [
        q.enqueue(process_source, source_id, retry=RETRY, job_timeout=SOURCE_TIMEOUT, result_ttl=RESULT_TTL)
        for source_id in source_ids
    ]
    # allow_failure=True：有來源最後失敗也照樣收尾（RQ 預設是前面全部成功才放後面的工作）
    depends_on = Dependency(jobs=jobs, allow_failure=True) if jobs else None
    q.enqueue(finish_daily_run, run.id, depends_on=depends_on, job_timeout=FINISH_TIMEOUT, result_ttl=RESULT_TTL)
    run.counts = {**run.counts, "enqueued": len(jobs)}
    session.commit()


# 前一輪開始這麼久還沒收尾，就當它壞了（或電腦關機太久），不再等（ADR-075）
STALE_RUN = timedelta(hours=24)

StartStep = Literal["already_started", "wait", "stale", "start"]


def decide_start(today_started: bool, previous: Run | None, now: datetime) -> StartStep:
    """開始今天的檢查前的判斷（ADR-075）：今天開始過、在等前一輪收尾、前一輪太久、開始。

    previous 是最近一輪；手動指令不看今天開始過沒，today_started 傳 False。
    """
    if today_started:
        return "already_started"
    if previous is None or previous.finished_at is not None:
        return "start"
    if now - previous.started_at < STALE_RUN:
        return "wait"  # 背壓：前一輪還在做，先不放新的一輪進佇列
    return "stale"


def latest_run(session: Session) -> Run | None:
    """最近一輪（依開始時間）。"""
    return session.scalars(select(Run).order_by(Run.started_at.desc()).limit(1)).first()


def skipped_days(session: Session, run: Run) -> list[tuple[date, bool]]:
    """和上一輪之間沒有單獨檢查的日子（ADR-076），以及那天是不是在等前一輪收尾（寫過「在等」的通知）。"""
    previous = session.scalars(
        select(Run).where(Run.started_at < run.started_at).order_by(Run.started_at.desc()).limit(1)
    ).first()
    if previous is None:
        return []
    days = [previous.local_date + timedelta(days=n) for n in range(1, (run.local_date - previous.local_date).days)]
    if not days:
        return []
    keys = [f"waiting:{day}" for day in days]
    waited = set(session.scalars(select(Event.dedup_key).where(Event.user_id == CURRENT_USER_ID, Event.dedup_key.in_(keys))))
    return [(day, f"waiting:{day}" in waited) for day in days]


def note_waiting(session: Session, today: date, previous: Run, now: datetime) -> None:
    """在等前一輪收尾（ADR-075）：每天只送一則（去重鍵 waiting:日期），之後的 tick 不再重複送。"""
    title, lines = waiting_message(today, previous.local_date, previous.started_at, now)
    if add_system_event(session, CURRENT_USER_ID, f"waiting:{today}", title, lines, now):
        session.commit()
        notify_soon()


def warn_stale(session: Session, previous: Run, now: datetime) -> None:
    """前一輪開始 24 小時以上還沒收尾（ADR-075）：警告一次（去重鍵 stale-run:那一輪的 id），今天照常開始。"""
    title, lines = stale_message(previous.local_date, previous.started_at, now)
    if add_system_event(session, CURRENT_USER_ID, f"stale-run:{previous.id}", title, lines, now):
        session.commit()
        notify_soon()


def tick() -> str:
    """每 15 分鐘一次（ADR-057、075）：有網路、今天（台灣時間）還沒開始過、前一輪也收尾了，就開始今天的檢查。"""
    if not online():
        return "沒有網路，等下一次"
    today = taipei_date()
    now = datetime.now(UTC)
    with SessionLocal() as session:
        today_started = session.scalars(select(Run).where(Run.local_date == today)).first() is not None
        previous = latest_run(session)
        step = decide_start(today_started, previous, now)
        if step == "already_started":
            return "今天已經開始過"
        if step == "wait":
            assert previous is not None  # decide_start 只有在有前一輪時才會回 wait、stale
            note_waiting(session, today, previous, now)
            return "前一輪還沒收尾，等它做完"
        if step == "stale":
            assert previous is not None
            warn_stale(session, previous, now)
        run = Run(local_date=today, started_at=now)
        session.add(run)
        try:
            session.commit()
        except IntegrityError:
            return "今天已經開始過"  # 另一個 tick 同時開始了（runs.local_date 唯一）
        source_ids = due_source_ids(session, today)
        start_run(session, run, source_ids)
    return f"開始今天的檢查：{len(source_ids)} 個來源"
