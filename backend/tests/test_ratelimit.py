"""限速器的單元測試（ADR-042）。"""

from app.core.llm import ratelimit


def test_waits_until_the_oldest_request_leaves_the_window() -> None:
    # 每分鐘最多 2 次：第 3 次要等到第 1 次滿 60 秒才能送
    now = [0.0]
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    limiter = ratelimit.RateLimiter(2, clock=lambda: now[0], sleep=sleep)
    limiter.wait()
    now[0] = 10.0
    limiter.wait()
    now[0] = 20.0
    limiter.wait()
    assert slept == [40.0]
