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
