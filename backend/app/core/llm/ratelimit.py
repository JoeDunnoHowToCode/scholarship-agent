"""每分鐘請求數上限（ADR-042）：超過就先等，避免被 API 拒絕。"""

import time
from collections import deque
from collections.abc import Callable

WINDOW_SECONDS = 60.0


class RateLimiter:
    """滑動視窗：記住最近 60 秒內每次請求的時間，滿了就等最舊的那次滿 60 秒。

    只管這一個程序；平行跑好幾個程序時，總量是程序數乘上這個上限。
    """

    def __init__(
        self,
        max_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._max = max_per_minute
        self._clock = clock
        self._sleep = sleep
        self._sent: deque[float] = deque()

    def wait(self) -> None:
        now = self._clock()
        # 丟掉已經超過 60 秒的紀錄
        while self._sent and now - self._sent[0] >= WINDOW_SECONDS:
            self._sent.popleft()
        if len(self._sent) >= self._max:
            self._sleep(self._sent[0] + WINDOW_SECONDS - now)
            self._sent.popleft()
            now = self._clock()
        self._sent.append(now)
