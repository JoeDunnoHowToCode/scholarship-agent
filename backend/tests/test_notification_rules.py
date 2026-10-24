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


def test_eligibility_and_deadline_changes_compare_normalized_values() -> None:
    # 截止日：同一個日期，只是標籤或引用換了說法（AI 重抽常這樣）：不通知
    old_windows = [
        {"label": "Partner countries", "closes_year": 2027, "closes_month": 1, "closes_day": 15,
         "evidence": "Deadline: 15 January 2027"},
    ]
    reworded = [
        {"label": "非歐盟申請人", "closes_year": 2027, "closes_month": 1, "closes_day": 15,
         "evidence": "Applications close on 15 January 2027"},
    ]
    assert rules.describe_change("windows", old_windows, reworded) is None
    # 截止日真的改了、又多了第二輪：通知，日期排序後用「、」連接
    moved = [
        {"label": "第二輪", "closes_year": 2027, "closes_month": 3, "closes_day": 1, "evidence": None},
        {"label": "第一輪", "closes_year": 2027, "closes_month": 1, "closes_day": 20, "evidence": None},
    ]
    assert rules.describe_change("windows", old_windows, moved) == "截止日：2027-01-15 → 2027-01-20、2027-03-01"
    # 年月日不齊全的截止日不算，所以這裡新的等於沒有截止日
    no_year = [{"label": None, "closes_year": None, "closes_month": 1, "closes_day": 20, "evidence": None}]
    assert rules.describe_change("windows", old_windows, no_year) is None
    # 舊的沒有截止日（新的一屆，另外通知；舊資料可能還沒有這個欄位）、新的沒抽到（多半是 AI 漏抽）：不通知
    assert rules.describe_change("windows", [], moved) is None
    assert rules.describe_change("windows", None, moved) is None
    assert rules.describe_change("windows", old_windows, []) is None

    # 國籍資格的範圍變了：用中文寫出前後
    assert rules.describe_change("nationality_scope", "all", "listed") == "國籍資格：不限國籍 → 只限列出的國家"
    assert (
        rules.describe_change("nationality_scope", "excluded", "unclear")
        == "國籍資格：列出的國家以外都可以 → 原文沒寫"
    )
    assert rules.describe_change("nationality_scope", "listed", "listed") is None

    # 國家清單：國碼不分大小寫、不管順序；只寫有變的部分，國碼排序
    assert rules.describe_change("nationalities", ["tw", "KR"], ["KR", "TW"]) is None
    assert rules.describe_change("nationalities", ["TW", "KR"], ["TW", "JP", "DE"]) == "國籍清單：新增 DE、JP；移除 KR"
    assert rules.describe_change("nationalities", ["TW"], ["tw", "jp"]) == "國籍清單：新增 JP"
    assert rules.describe_change("nationalities", ["TW", "KR"], ["TW"]) == "國籍清單：移除 KR"
    # 有一邊是空清單（AI 有時沒把 EU 這種集合展開成國碼）：不通知
    assert rules.describe_change("nationalities", [], ["FR", "DE"]) is None
    assert rules.describe_change("nationalities", ["FR", "DE"], []) is None

    # 學位：照學士、碩士、博士的順序寫，不管原本的順序
    assert rules.describe_change("degrees", ["master"], ["phd", "master"]) == "可讀學位：碩士 → 碩士、博士"
    assert rules.describe_change("degrees", ["phd", "master"], ["master", "phd"]) is None
    # 新的是空清單（多半是 AI 漏抽）：不通知；舊的是空清單：寫「原文沒寫」
    assert rules.describe_change("degrees", ["master"], []) is None
    assert rules.describe_change("degrees", [], ["bachelor", "master"]) == "可讀學位：原文沒寫 → 學士、碩士"

    # 其他欄位（例如補助內容）不通知
    assert rules.describe_change("coverage", "學費", "學費、生活費") is None
