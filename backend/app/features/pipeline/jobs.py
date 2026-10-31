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
from app.core.llm.gemini import GeminiEmbedder, GeminiLLM
from app.features.matching.score import score_all
from app.features.notifications.generate import add_system_event, generate
from app.features.notifications.models import Event
from app.features.notifications.send import send_events
from app.features.pipeline import breaker
from app.features.pipeline.due import frequency_for, is_due
from app.features.pipeline.errors import CostLimitError, classify
from app.features.pipeline.models import Run
from app.features.pipeline.report import report_message, stale_message, waiting_message
from app.features.profiles.service import CURRENT_USER_ID, get_profile
from app.features.scholarships import dedup
from app.features.scholarships.cycles import is_stale, refresh
from app.features.scholarships.extract import extract_source
from app.features.scholarships.models import EMBEDDING_DIMENSIONS, Scholarship
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
    due: list[int] = []
    for source, row in rows:
        stale, recheck = False, None
        if row is not None:
            real = [c.closes_at for c in row.cycles if not c.estimated]
            stale = bool(real) and is_stale(max(real), today)
            starts = [c.recheck_from for c in row.cycles if c.estimated and c.recheck_from]
            recheck = min(starts) if starts else None
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
            llm = GeminiLLM(settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute)
            summary = extract_source(session, llm, source)
            session.commit()
            spent = sum(x.cost_usd() for x in (llm, picker_llm) if x is not None) * NTD_PER_USD
            if spent > SOURCE_MAX_COST_NTD:
                raise CostLimitError(f"來源 {source_id} 花了 NT${spent:.1f}，超過 NT${SOURCE_MAX_COST_NTD}")
            has_chunks = session.scalar(select(exists().where(Chunk.source_id == source.id)))
            if summary == "unchanged" and has_chunks:
                return {"result": "unchanged", "detail": "內容沒變"}
            embedder = GeminiEmbedder(
                settings.embedding_model, settings.google_api_key, EMBEDDING_DIMENSIONS,
                settings.llm_requests_per_minute,
            )
            index_source(session, llm, embedder, source)
            index_scholarship(session, embedder, source)
            session.commit()
            return {"result": "extracted", "detail": summary}
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
    if kind == "pause_ai":
        breaker.open_breaker(session, detail)
        session.commit()
        notify_breaker(session)
        print(f"breaker    來源 {source_id} 打開斷路器：{detail}")
        return {"result": "paused", "detail": detail}
    print(f"skipped    來源 {source_id}：{detail}")
    return {"result": "skipped", "detail": detail}


def summarize_dependencies() -> dict[str, int]:
    """收尾時數一數：今天每個來源的工作各是什麼結果；重試後仍失敗的算 failed。"""
    job = get_current_job()
    counts: Counter[str] = Counter()
    if job is None:
        return {}
    for dependency in job.fetch_dependencies():
        if dependency.is_failed:
            counts["failed"] += 1
            continue
        value = dependency.return_value()
        counts[value["result"] if isinstance(value, dict) else "unknown"] += 1
    return dict(counts)


def score_today() -> dict[str, Any]:
    """收尾的評分：AI 只重評內容有變的（ADR-059、060）；斷路器打開或沒有個人資料就跳過。"""
    with SessionLocal(expire_on_commit=False) as session:
        if breaker.is_open(session):
            return {"skipped": "斷路器打開中"}
        profile = get_profile(session, CURRENT_USER_ID)
        if profile is None:
            return {"skipped": "還沒有個人資料"}
        llm = GeminiLLM(settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute)
        counts: dict[str, Any] = score_all(session, llm, settings.llm_model, profile, SCORE_MAX_COST_NTD)
        return counts


def finish_daily_run(run_id: int) -> str:
    """當天所有來源的工作結束後收尾：更新申請期與封存 → 規則去重 → 評分，結果記在 runs。"""
    sources = summarize_dependencies()
    with SessionLocal() as session, session.begin():
        cycles = refresh(session, datetime.now(UTC))
    dedup.main()  # 規則去重（ADR-048），自己開交易、印出結果
    scores = score_today()
    with SessionLocal() as session, session.begin():
        events = generate(session, CURRENT_USER_ID, datetime.now(UTC))  # 通知事件（ADR-062）
        run = session.get(Run, run_id)
        if run is not None:
            finished = datetime.now(UTC)
            run.finished_at = finished
            # JSONB 欄位整個重新指定（CLAUDE.md 程式規範）
            run.counts = {**run.counts, "sources": sources, "cycles": dict(cycles), "scores": scores, "events": events}
            # 每日檢查報告（ADR-076）：每一輪都讓你知道做了沒、做了什麼；同一輪只送一則（去重鍵 run:id）
            new_events = sum(n for kind, n in events.items() if kind.endswith(":pending"))
            title, lines = report_message(
                run.local_date, run.started_at, finished, sources, new_events, skipped_days(session, run)
            )
            add_system_event(session, CURRENT_USER_ID, f"run:{run.id}", title, lines, finished)
    notify_soon()
    return f"收尾完成：來源 {sources}；申請期 {dict(cycles)}；評分 {scores}；通知事件 {events}"


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
