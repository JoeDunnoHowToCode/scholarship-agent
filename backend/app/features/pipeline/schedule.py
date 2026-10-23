"""rq cron 的設定（ADR-006、057）：每 15 分鐘放一件 tick。

用法：uv run rq cron app.features.pipeline.schedule

rq cron 啟動時會馬上放一次 interval 工作，所以登入或開機後立刻就會檢查要不要補跑。
不用 cron 字串：rq 2.12 的 cron 字串依 UTC 計算，改由 tick 自己用台灣時間判斷。
"""

from rq.cron import register

from app.features.pipeline.jobs import tick

register(tick, queue_name="default", interval=15 * 60)
