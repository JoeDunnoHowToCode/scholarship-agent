"""變更紀錄比對的單元測試（ADR-020）。"""

from app.features.scholarships import changes


def test_ignores_formatting_only_differences() -> None:
    # 每次重新抽取，模型會換空白、大小寫、清單順序，或換一句引用；內容沒變就不該記成變更
    old = {
        "amount": "EUR 1,400 per month",
        "coverage": "Tuition fees and living costs",
        "nationalities": ["Sweden", "Denmark"],
        "other_eligibility": None,
        "windows": [
            {
                "closes_year": 2027,
                "closes_month": 1,
                "closes_day": 31,
                "label": "Partner countries",
                "funding": "scholarship",
                "evidence": "Deadline: 31 January 2027",
            }
        ],
        "categories": [
            {
                "name": "北歐國家",
                "quota": 10,
                "degrees": ["master", "phd"],
                "degree_conditions": None,
                "quota_evidence": "(1)北歐國家(丹麥、瑞典、挪威、芬蘭、冰島)：10 名。",
                "degrees_evidence": "得攻讀碩士或博士學位",
            }
        ],
        "requirements": [
            {"doc_type": "cv", "details": "max 2 pages", "category": None, "evidence": "CV (max 2 pages)"},
            {"doc_type": "transcript", "details": None, "category": None, "evidence": "Official transcripts"},
        ],
    }
    new = {
        "amount": "  eur 1,400   PER month ",  # 多了空白、大小寫不同
        "coverage": "Ｔｕｉｔｉｏｎ fees and living costs",  # 全形字
        "nationalities": ["Denmark", "Sweden"],  # 順序不同
        "other_eligibility": "",  # 空字串等於沒有
        "windows": [
            {
                "closes_year": 2027,
                "closes_month": 1,
                "closes_day": 31,
                "label": "partner  countries",
                "funding": "scholarship",
                "evidence": "The application deadline is 31 January 2027.",  # 換了一句引用
            }
        ],
        "categories": [
            {
                "name": "北歐國家",
                "quota": 10,
                "degrees": ["phd", "master"],
                "degree_conditions": None,
                "quota_evidence": "北歐國家：10 名",
                "degrees_evidence": "得攻讀碩士或博士學位。",
            }
        ],
        "requirements": [
            {"doc_type": "transcript", "details": None, "category": None, "evidence": "Transcripts of records"},
            {"doc_type": "cv", "details": "Max 2 pages", "category": None, "evidence": "Curriculum vitae, max 2 pages"},
        ],
    }
    assert changes.diff_important(old, new) == []


def test_detects_real_changes_in_field_order_with_original_values() -> None:
    # 主辦單位調高月領金額、截止日從 1/31 提前到 1/15、拿掉成績單；這些都要記下來
    old_windows = [{"closes_year": 2027, "closes_month": 1, "closes_day": 31, "label": None, "evidence": "31 Jan 2027"}]
    new_windows = [{"closes_year": 2027, "closes_month": 1, "closes_day": 15, "label": None, "evidence": "15 Jan 2027"}]
    old_requirements = [
        {"doc_type": "cv", "details": "max 2 pages", "category": None, "evidence": "CV (max 2 pages)"},
        {"doc_type": "transcript", "details": None, "category": None, "evidence": "Official transcripts"},
    ]
    new_requirements = [
        {"doc_type": "cv", "details": "max 2 pages", "category": None, "evidence": "CV (max 2 pages)"},
    ]
    old = {
        "amount": "EUR 1,200 per month ",  # 結尾多一個空白：紀錄裡要保留原本的樣子
        "coverage": "Tuition fees",
        "windows": old_windows,
        "requirements": old_requirements,
    }
    # 新資料的欄位順序打亂；結果仍要依 IMPORTANT_FIELDS 的順序排
    new = {
        "requirements": new_requirements,
        "windows": new_windows,
        "coverage": "Tuition fees",
        "amount": "EUR 1,400 per month",
    }
    assert changes.diff_important(old, new) == [
        changes.Change("amount", "EUR 1,200 per month ", "EUR 1,400 per month"),
        changes.Change("windows", old_windows, new_windows),
        changes.Change("requirements", old_requirements, new_requirements),
    ]


def test_only_a_sentence_found_in_just_one_version_of_the_website_is_a_change() -> None:
    # ADR-064：官網真的改了才算。old_page、new_page 是新舊兩版網頁的原文（可見文字）
    old_page = "Last updated: 23 October 2026\nApplication deadline: 15 January 2027\nInterviews: 20 January 2027"
    old = {
        "windows": [
            {"closes_year": 2027, "closes_month": 1, "closes_day": 15,
             "evidence": "Application deadline: 15 January 2027"},
        ]
    }
    # 官網只有更新時間變了（每天都會變的動態內容），AI 這次挑了面試日期那一句：兩句新舊兩版都有，不算
    same_page = "Last updated: 24 October 2026\nApplication deadline: 15 January 2027\nInterviews: 20 January 2027"
    picked_other = {
        "windows": [
            {"closes_year": 2027, "closes_month": 1, "closes_day": 20, "evidence": "Interviews: 20 January 2027"},
        ]
    }
    assert changes.website_changed("windows", old, picked_other, old_page, same_page) is False
    # 截止日延長：新的引用只在新版網頁出現 → 官網真的改了
    extended_page = (
        "Last updated: 24 October 2026\nApplication deadline extended to 31 January 2027\nInterviews: 20 January 2027"
    )
    extended = {
        "windows": [
            {"closes_year": 2027, "closes_month": 1, "closes_day": 31,
             "evidence": "Application deadline extended to 31 January 2027"},
        ]
    }
    assert changes.website_changed("windows", old, extended, old_page, extended_page) is True

    # 官網刪掉第二輪：新的引用舊版也有，但第二輪那句只在舊版出現 → 也算官網改了
    two_rounds = "Round 1 deadline: 15 January 2027\nRound 2 deadline: 1 March 2027"
    one_round = "Round 1 deadline: 15 January 2027"
    old_rounds = {
        "windows": [
            {"closes_year": 2027, "closes_month": 1, "closes_day": 15, "evidence": "Round 1 deadline: 15 January 2027"},
            {"closes_year": 2027, "closes_month": 3, "closes_day": 1, "evidence": "Round 2 deadline: 1 March 2027"},
        ]
    }
    new_rounds = {
        "windows": [
            {"closes_year": 2027, "closes_month": 1, "closes_day": 15, "evidence": "Round 1 deadline: 15 January 2027"},
        ]
    }
    assert changes.website_changed("windows", old_rounds, new_rounds, two_rounds, one_round) is True

    # 國籍資格、國家清單看 nationality_evidence；學位看 degrees_evidence
    all_open = {"nationality_evidence": "Open to students of all nationalities."}
    eu_only = {"nationality_evidence": "Only EU citizens are eligible."}
    assert changes.website_changed(
        "nationality_scope", all_open, eu_only, "Open to students of all nationalities.", "Only EU citizens are eligible."
    ) is True
    # 同一頁兩句都有，AI 只是這次挑了另一句：不算
    both = "Open to students of all nationalities. Only EU citizens are eligible."
    assert changes.website_changed("nationalities", all_open, eu_only, both, both) is False
    master = {"degrees_evidence": "This is a two-year Master programme."}
    master_and_phd = {"degrees_evidence": "PhD candidates may also apply."}
    assert changes.website_changed(
        "degrees", master, master_and_phd,
        "This is a two-year Master programme.", "This is a two-year Master programme. PhD candidates may also apply.",
    ) is True


def test_quotes_the_ai_rewrote_are_not_evidence() -> None:
    # 引用要逐字出現在自己那一版的原文裡，才能當證據；AI 改寫過的句子哪一版都找不到
    page = "Application deadline: 15 January 2027"
    original = {
        "windows": [
            {"closes_year": 2027, "closes_month": 1, "closes_day": 15,
             "evidence": "Application deadline: 15 January 2027"},
        ]
    }
    rewritten = {
        "windows": [
            {"closes_year": 2027, "closes_month": 1, "closes_day": 20, "evidence": "The deadline is 20 January 2027"},
        ]
    }
    # 官網沒變：新的引用是改寫的 → 不能說它是新版才有的句子
    assert changes.website_changed("windows", original, rewritten, page, page) is False
    # 舊的引用是改寫的 → 不能說官網刪掉了它
    assert changes.website_changed("windows", rewritten, original, page, page) is False
    # 沒附引用、舊資料沒有申請窗口：沒有證據
    assert changes.website_changed("degrees", {"degrees_evidence": None}, {"degrees_evidence": None}, page, page) is False
    assert changes.website_changed("windows", {}, original, page, page) is False
