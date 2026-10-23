"""worker 的單元測試（ADR-057）：沒網路時先等，不從佇列拿工作。"""

from app.features.pipeline import worker


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
