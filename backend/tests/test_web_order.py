"""網頁列表排序的單元測試（第 9 天，ADR-059）。"""

from app.features.scholarships import listing


def test_list_groups_by_time_status_then_score() -> None:
    # 每一列：（名稱, 時間狀態, 分數）；時間狀態來自評分的時間檢查：pass 還能申請、unclear 時間待確認、fail 已截止或不適用
    rows = [
        ("已截止但很適合", "fail", 95.0),
        ("還能申請、分數低", "pass", 40.0),
        ("時間待確認", "unclear", 80.0),
        ("還能申請、分數高", "pass", 90.0),
        ("還沒評分", None, None),  # 沒有個人資料或還沒評分：沒有時間狀態也沒有分數
    ]
    ordered = sorted(rows, key=lambda row: listing.list_order(row[1], row[2]))
    # 先依時間狀態分組（還能申請 → 時間待確認 → 已截止或不適用），同組依分數由高到低；還沒評分的排最後
    assert [name for name, _, _ in ordered] == [
        "還能申請、分數高",
        "還能申請、分數低",
        "時間待確認",
        "已截止但很適合",
        "還沒評分",
    ]


def test_card_cycle_picks_the_nearest_applicable_round_else_the_nearest_open_one() -> None:
    # ADR-077（11-04 修改）：卡片上一律寫「申請日期」（11-07 由「截止日期」改名），邏輯上先挑適合你的那一輪
    from datetime import UTC, datetime

    from app.features.scholarships.models import Cycle

    def cycle(scope: str, codes: list[str], closes: datetime, status: str = "open") -> Cycle:
        return Cycle(
            nationality_scope=scope, nationalities=codes, funding="scholarship", status=status,
            closes_at=closes, opens_at=None, estimated=False, verification="supported",
        )

    eu_only = cycle("listed", ["DE", "FR"], datetime(2027, 1, 10, tzinfo=UTC))  # 比較早截止，但只限歐盟
    everyone = cycle("all", [], datetime(2027, 2, 12, tzinfo=UTC))
    closed = cycle("all", [], datetime(2026, 10, 1, tzinfo=UTC), status="closed")
    # 有國籍（台灣）：挑適用的最早一輪
    assert listing.card_cycle([eu_only, everyone, closed], "TW") is everyone
    # 沒填個人資料：挑所有還沒截止的裡最早的
    assert listing.card_cycle([eu_only, everyone, closed], None) is eu_only
    # 沒有適用你的：退回所有還沒截止的裡最早的
    assert listing.card_cycle([eu_only, closed], "TW") is eu_only
    # 全部截止：沒有
    assert listing.card_cycle([closed], "TW") is None


def test_same_score_puts_the_open_round_before_the_upcoming_one() -> None:
    # 11-07：只在「同一組、同分」時，卡片上那一輪已經開放的排前面；分數不同時還是分數高的在前
    from datetime import UTC, datetime

    from app.features.scholarships.models import Cycle

    now = datetime(2027, 3, 1, tzinfo=UTC)

    def cycle(opens: datetime | None, closes: datetime) -> Cycle:
        return Cycle(opens_at=opens, closes_at=closes, estimated=False)

    open_now = cycle(datetime(2027, 2, 1, tzinfo=UTC), datetime(2027, 4, 1, tzinfo=UTC))
    upcoming = cycle(datetime(2027, 3, 15, tzinfo=UTC), datetime(2027, 4, 1, tzinfo=UTC))
    assert listing.is_open_now(open_now, now)
    assert not listing.is_open_now(upcoming, now)
    assert not listing.is_open_now(None, now)  # 沒有可顯示的申請期

    # 每一列：（名稱, 時間狀態, 分數, 卡片上那一輪是否已開放）
    rows = [
        ("即將開放、同分", "pass", 90.0, False),
        ("已開放、同分", "pass", 90.0, True),
        ("即將開放、分數高", "pass", 95.0, False),
        ("已開放、分數低", "pass", 80.0, True),
    ]
    ordered = sorted(rows, key=lambda row: listing.list_order(row[1], row[2], row[3]))
    assert [name for name, *_ in ordered] == ["即將開放、分數高", "已開放、同分", "即將開放、同分", "已開放、分數低"]
