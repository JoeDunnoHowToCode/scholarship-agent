"""背景工作的 worker（ADR-057）：沒網路時不從佇列拿工作，等網路回來。

用法（launchd 會用這個指令啟動）：
uv run rq worker -w app.features.pipeline.worker.OnlineSpawnWorker --with-scheduler
"""

import time
from collections.abc import Callable

from rq import Queue
from rq.job import Job
from rq.worker import SpawnWorker

from app.features.pipeline.jobs import online

WAIT_SECONDS = 30  # 沒網路時，多久再檢查一次


def wait_until_online(
    is_online: Callable[[], bool],
    pause: Callable[[float], None],
    heartbeat: Callable[[], None],
    every: float = WAIT_SECONDS,
) -> int:
    """沒網路就每 every 秒檢查一次，期間持續回報 worker 還活著；回傳等了幾輪。"""
    waited = 0
    while not is_online():
        heartbeat()  # 讓 RQ 知道這個 worker 還活著，不會被當成當掉
        pause(every)
        waited += 1
    return waited


class OnlineSpawnWorker(SpawnWorker):
    """SpawnWorker（macOS 用，避開 fork），多兩條規則：沒網路就先不拿工作；開新程序前補好登記資料。

    工作留在佇列，不會因為沒網路一拿就失敗、白白用掉重試次數；
    電腦睡著或白天沒連網時，最多只有當下正在跑的那一件會受影響。
    """

    def dequeue_job_and_maintain_ttl(
        self, timeout: int | None, max_idle_time: int | None = None
    ) -> tuple[Job, Queue] | None:
        if not online():
            self.log.info("沒有網路：先不拿工作，每 %s 秒檢查一次", WAIT_SECONDS)
            waited = wait_until_online(online, time.sleep, self.heartbeat)
            self.log.info("網路回來了（等了約 %s 分鐘），繼續拿工作", waited * WAIT_SECONDS // 60)
        return super().dequeue_job_and_maintain_ttl(timeout, max_idle_time)

    def fork_work_horse(self, job: Job, queue: Queue) -> None:
        # 筆電睡超過 8 分鐘，worker 在 Redis 的登記資料會過期；醒來後閒著時的心跳只寫回 last_heartbeat，
        # 少了佇列名稱。新程序靠這份資料知道自己負責哪條佇列，少了就不把做完的工作移出中繼佇列，
        # RQ 的整理會把它當成失敗、照重試規則重跑（第 9 天發現，每件最多做 4 次）。缺了就先補回完整的登記資料
        if not self.connection.hexists(self.key, "queues"):
            self.connection.hset(self.key, mapping=self.serialize())
        super().fork_work_horse(job, queue)
