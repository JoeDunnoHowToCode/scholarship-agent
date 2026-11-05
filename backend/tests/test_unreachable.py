"""天天抓不到的來源（ADR-080）。"""

from datetime import date

from app.features.pipeline import unreachable

D1, D2, D3 = date(2026, 11, 6), date(2026, 11, 7), date(2026, 11, 8)


def test_three_failed_days_mark_a_source_and_success_brings_it_back() -> None:
    fresh: unreachable.State = (0, None, None)
    # 第一次失敗：記一天
    assert unreachable.next_state(fresh, True, D1) == ((1, D1, None), None)
    # 同一天又失敗（例如重跑）：不重複算
    assert unreachable.next_state((1, D1, None), True, D1) == ((1, D1, None), None)
    # 第三個失敗的日子：標記成抓不到，通知你
    assert unreachable.next_state((2, D2, None), True, D3) == ((3, D3, D3), "unreachable")
    # 已經標記過，之後每週再試又失敗：照算，不再通知
    week_later = date(2026, 11, 15)
    assert unreachable.next_state((3, D3, D3), True, week_later) == ((4, week_later, D3), None)
    # 標記過的成功了：歸零，通知你恢復了
    assert unreachable.next_state((4, week_later, D3), False, date(2026, 11, 22)) == ((0, None, None), "recovered")
    # 平常的成功：歸零，不用通知
    assert unreachable.next_state((1, D1, None), False, D2) == ((0, None, None), None)
