"""列表卡片的申請日期只寫日期與狀態，不接原文標籤（docs/ui-review-2.md B3）。

原文標籤（例如 NEW ERASMUS MUNDUS CALL）留在詳細頁的申請期與通知裡；卡片上 82 筆因為它變成中英混雜的一長行。
"""

from datetime import UTC, datetime

from app.features.matching.score import describe_cycle
from app.features.scholarships.models import Cycle


def test_describe_cycle_can_leave_out_the_label() -> None:
    brussels = Cycle(
        opens_at=datetime(2026, 10, 31, 23, 0, tzinfo=UTC), closes_at=datetime(2027, 1, 15, 22, 59, tzinfo=UTC),
        timezone="Europe/Brussels", timezone_assumed=False, status="open", estimated=False, verification="supported",
        label="Partner countries", evidence=None,
    )
    now = datetime(2026, 11, 4, tzinfo=UTC)
    assert describe_cycle(brussels, now, label=False) == "2026-11-01 → 2027-01-15（開放中）"
    # 預設照舊附上標籤：通知與時間原因還是要知道是哪一期
    assert describe_cycle(brussels, now) == "2026-11-01 → 2027-01-15（開放中）Partner countries"
