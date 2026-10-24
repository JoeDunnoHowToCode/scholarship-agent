"""通知判斷規則的單元測試（ADR-062、063）：截止提醒的格子、變更判斷、合併成摘要。"""

from app.features.notifications import rules


def test_reminder_bucket_sends_the_current_bucket_once_and_skips_missed_ones() -> None:
    # 截止前 30、14、7、3、1 天各提醒一次
    assert rules.REMINDER_DAYS == (30, 14, 7, 3, 1)
    # 剛好剩 30 天：送「30 天」那格
    assert rules.reminder_bucket(30, set()) == 30
    # 剩 30 天那次電腦沒網路、沒跑到，現在剩 12 天：送「14 天」那格，不補送 30 天
    assert rules.reminder_bucket(12, set()) == 14
    # 「14 天」那格昨天送過了，今天剩 13 天：不再送，也不退回去送「30 天」
    assert rules.reminder_bucket(13, {14}) is None
    # 剩 7 天：送「7 天」那格
    assert rules.reminder_bucket(7, {30, 14}) == 7
    # 今天截止（剩 0 天）：算「1 天」那格
    assert rules.reminder_bucket(0, set()) == 1
    # 還有 31 天以上：還不用提醒；已經截止：不提醒
    assert rules.reminder_bucket(31, set()) is None
    assert rules.reminder_bucket(-1, set()) is None
