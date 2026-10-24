"""通知判斷規則的單元測試（ADR-062、063）：截止提醒的格子、變更判斷、合併成摘要。"""

from app.core.notify.base import Notification
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


def test_bundle_merges_more_than_five_into_a_digest_grouped_by_kind() -> None:
    breaker = Notification(kind="system", title="斷路器打開：暫停抓取網頁")
    change = Notification(
        kind="change", title="DAAD 資料變更", lines=("金額：€934 → €992",), url="https://example.org/daad"
    )
    first = Notification(
        kind="deadline", title="學程 20 剩 7 天截止", lines=("截止日：2027-01-15",), url="https://example.org/20"
    )
    new = Notification(kind="new_scholarship", title="新獎學金：Eiffel 獎學金", url="https://example.org/eiffel")
    unknown = Notification(kind="unknown", title="沒有分組的類型")
    cycle = Notification(kind="new_cycle", title="學程 35 新年度開放", url="https://example.org/35")
    second = Notification(kind="deadline", title="教育部留學獎學金剩 14 天截止", url="https://example.org/moe")

    # 沒有通知：什麼都不送
    assert rules.bundle([]) == []
    # 5 則以內（系統通知不算）：照原樣各送各的，系統通知排最前面
    assert rules.bundle([change, first, breaker, new, cycle, second]) == [
        breaker, change, first, new, cycle, second,
    ]
    # 超過 5 則：合併成一則摘要，依類型分組、每組先寫標題，同一組照原本的順序；系統通知照樣單獨送
    assert rules.bundle([change, first, breaker, new, unknown, cycle, second]) == [
        breaker,
        Notification(
            kind="digest",
            title="今天有 6 則獎學金通知",
            lines=(
                "【截止提醒】", "學程 20 剩 7 天截止", "教育部留學獎學金剩 14 天截止",
                "【新年度開放】", "學程 35 新年度開放",
                "【新獎學金】", "新獎學金：Eiffel 獎學金",
                "【資料變更】", "DAAD 資料變更",
                "【其他】", "沒有分組的類型",
            ),
            url=None,
        ),
    ]


def test_deadline_changes_compare_only_within_the_same_intake() -> None:
    # 官網把上一屆換成下一屆（2026 → 2027）：那是新年度開放（另外通知），不是截止日變更（子 agent 提出）
    last = [{"intake": None, "closes_year": 2026, "closes_month": 1, "closes_day": 15}]
    next_year = [{"intake": None, "closes_year": 2027, "closes_month": 1, "closes_day": 15}]
    assert rules.describe_change("windows", last, next_year) is None
    # 同一屆（入學年度寫 2027/28）從 2026-12-15 改到 2027-01-10：跨了年，還是同一屆，要通知
    december = [{"intake": "2027/28", "closes_year": 2026, "closes_month": 12, "closes_day": 15}]
    january = [{"intake": "2027/2028", "closes_year": 2027, "closes_month": 1, "closes_day": 10}]
    assert rules.describe_change("windows", december, january) == "截止日：2026-12-15 → 2027-01-10"
    # 哪一屆：入學年度裡第一個四位數年份；沒寫入學年度就用截止的年份
    assert rules.cycle_year("2027-2029 cohort", 2026) == 2027
    assert rules.cycle_year(None, 2026) == 2026


def test_changes_the_ai_probably_missed_are_not_reported() -> None:
    # 舊的文件清單是空的：多半是之前漏抽，不把全部文件都當成新增（子 agent 提出）
    assert rules.describe_change("requirements", [], [{"doc_type": "cv"}]) is None
    assert rules.describe_change("requirements", None, [{"doc_type": "cv"}]) is None
    # 國籍資格是空值或不認得的值（舊資料）：不通知，也不會出錯
    assert rules.describe_change("nationality_scope", None, "all") is None
    assert rules.describe_change("nationality_scope", "all", "everyone") is None


def test_amount_and_document_changes_are_not_notified() -> None:
    # ADR-064（使用者第 8 天的決定）：金額不影響能不能申請；文件要求公告後很少改、
    # 系統偵測到的多半是 AI 每次抽取不同 → 兩種都不推播，點進詳細頁就看得到
    assert rules.describe_change("amount", "€1,400 per month", "€1,500 per month") is None
    before = [{"doc_type": "cv"}]
    after = [{"doc_type": "cv"}, {"doc_type": "language_test"}]
    assert rules.describe_change("requirements", before, after) is None
