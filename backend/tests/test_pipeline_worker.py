"""worker 的單元測試（ADR-057）：沒網路時先等，不從佇列拿工作。"""

import pytest
from redis import ConnectionPool, Redis
from redis.connection import parse_url
from rq import Queue
from rq.job import JobStatus

from app.features.pipeline import worker
from app.shared.settings import settings


def test_wait_until_online_holds_jobs_until_the_network_is_back() -> None:
    # 第 7 天實跑：電腦睡了 5 小時，期間每小時短暫醒來，沒網路還照樣拿工作，110 件把重試次數用光
    # 改成：沒網路就每 30 秒檢查一次，期間回報 worker 還活著，網路回來才回去拿工作
    answers = iter([False, False, True])
    pauses: list[float] = []
    beats: list[int] = []
    waited = worker.wait_until_online(lambda: next(answers), pauses.append, lambda: beats.append(1), every=30)
    assert waited == 2
    assert pauses == [30, 30]
    assert len(beats) == 2
    # 一開始就有網路：馬上回去拿工作，不等
    assert worker.wait_until_online(lambda: True, pauses.append, lambda: None) == 0


def test_spawned_job_leaves_the_intermediate_queue_after_the_worker_record_is_rebuilt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 第 9 天發現：筆電睡超過 8 分鐘，worker 在 Redis 的登記資料過期；醒來後閒著時的心跳只寫回
    # last_heartbeat，少了佇列名稱。新程序讀不到佇列，就不把做完的工作移出中繼佇列，
    # RQ 每 10 分鐘的整理把它當成失敗、照重試規則重跑（每件最多做 4 次）
    # 要 Redis（docker compose）；用第 15 號資料庫，不碰 worker 用的那個
    # 網址裡的資料庫號碼會蓋過 from_url 的參數，所以先拆開網址再換號碼
    redis = Redis(connection_pool=ConnectionPool(**{**parse_url(settings.redis_url), "db": 15}))
    assert redis.connection_pool.connection_kwargs["db"] == 15
    redis.flushdb()
    queue = Queue("default", connection=redis)
    job = queue.enqueue("math.sqrt", 4)
    spawn_worker = worker.OnlineSpawnWorker([queue], connection=redis)

    calls: list[int] = []

    def online_after_sleep() -> bool:
        # 第一次拿工作前：登記資料過期，再被閒著時的心跳重建（只剩 last_heartbeat）
        if not calls:
            redis.delete(spawn_worker.key)
            spawn_worker.heartbeat()
        calls.append(1)
        return True

    monkeypatch.setattr(worker, "online", online_after_sleep)
    try:
        spawn_worker.work(burst=True)
        assert job.get_status(refresh=True) == JobStatus.FINISHED
        assert redis.llen(f"{queue.key}:intermediate") == 0
    finally:
        redis.flushdb()
