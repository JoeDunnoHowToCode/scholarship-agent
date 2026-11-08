"""每日檢查的系統通知文字（ADR-075、076）：時間都用台灣時間。"""

from datetime import UTC, date, datetime

from app.features.pipeline import report


def test_report_message_tells_whether_and_why_the_check_ran() -> None:
    # 管理者要知道每一輪做了沒、做了什麼；和上一輪之間沒檢查的日子，也要說明為什麼
    title, lines = report.report_message(
        local_date=date(2026, 11, 1),
        started_at=datetime(2026, 11, 1, 0, 40, tzinfo=UTC),  # 台灣 11-01 08:40
        finished_at=datetime(2026, 11, 1, 19, 10, tzinfo=UTC),  # 台灣 11-02 03:10：拖過午夜，寫出日期
        sources={"extracted": 16, "unchanged": 113, "failed": 18, "skipped": 3, "catalogue": 1},
        new_events=2,
        skipped=[(date(2026, 10, 30), True), (date(2026, 10, 31), False)],
    )
    assert title == "每日檢查完成：11-01"
    assert lines == [
        "08:40 開始，11-02 03:10 收尾",
        "151 個來源：有變 16、沒變 113、抓不到 18、其他 4",
        "這輪產生 2 則通知",
        "10-30 沒有單獨檢查：在等前一輪收尾",
        "10-31 沒有檢查：那天電腦沒開或沒有網路",
    ]


def test_waiting_message_says_why_today_has_not_started() -> None:
    title, lines = report.waiting_message(
        today=date(2026, 11, 1),
        previous_date=date(2026, 10, 31),
        previous_started=datetime(2026, 10, 31, 3, 40, tzinfo=UTC),  # 台灣 10-31 11:40
        now=datetime(2026, 10, 31, 23, 40, tzinfo=UTC),  # 台灣 11-01 07:40：開始 20 小時
    )
    assert title == "11-01 的檢查還沒開始"
    assert lines == ["在等 10-31 那輪收尾（已經開始 20 小時）", "收尾後 15 分鐘內開始"]


def test_stale_message_warns_and_says_today_starts_anyway() -> None:
    title, lines = report.stale_message(
        previous_date=date(2026, 10, 30),
        previous_started=datetime(2026, 10, 29, 22, 40, tzinfo=UTC),  # 台灣 10-30 06:40
        now=datetime(2026, 10, 31, 0, 40, tzinfo=UTC),  # 台灣 10-31 08:40：開始 26 小時
    )
    assert title == "10-30 那輪開始 26 小時還沒收尾"
    assert lines == [
        "可能是收尾壞了，或電腦關機太久；今天照常開始",
        "查原因：backend/data/logs/worker.log",
    ]


def test_report_counts_sources_whose_only_changes_were_unrelated() -> None:
    # ADR-079：只有無關內容變了、沒重抽的來源算「沒變」，另外註明有幾個，用來看重抽比率有沒有下降
    _, lines = report.report_message(
        local_date=date(2026, 11, 5),
        started_at=datetime(2026, 11, 5, 0, 10, tzinfo=UTC),
        finished_at=datetime(2026, 11, 5, 2, 0, tzinfo=UTC),
        sources={"extracted": 5, "unchanged": 100, "noise": 9, "failed": 18},
        new_events=0,
        skipped=[],
    )
    assert lines[1] == "132 個來源：有變 5、沒變 109（其中 9 個只有無關內容變了）、抓不到 18、其他 0"


def test_report_shows_the_day_and_month_ai_cost() -> None:
    # ADR-089：每天知道 AI 花了多少，和本月累計離上限多遠
    _, lines = report.report_message(
        local_date=date(2026, 11, 8),
        started_at=datetime(2026, 11, 8, 0, 10, tzinfo=UTC),
        finished_at=datetime(2026, 11, 8, 2, 0, tzinfo=UTC),
        sources={"extracted": 5, "unchanged": 100},
        new_events=1,
        skipped=[],
        ai_cost=(3.456, 120.4, 7000),  # 今天、本月、上限（新台幣）
    )
    # 接在「這輪產生幾則通知」後面
    assert lines[2:4] == ["這輪產生 1 則通知", "AI 費用：今天約 NT$3.46，本月約 NT$120（上限 NT$7,000）"]


def test_discovery_digest_lists_added_rejected_and_disabled() -> None:
    # ADR-078：每週告訴你 agent 加了哪些來源，看到不對再停用
    added = [(f"Scholarship {n}", f"https://u{n}.eu/s") for n in range(12)]
    title, lines = report.discovery_digest_message(
        added=added,
        rejected=[("A", "留學國家不在歐洲"), ("B", "留學國家不在歐洲"), ("C", "國籍規定排除台灣")],
        disabled=[("Old programme", "連續 3 次抽不到有效獎學金")],
    )
    assert title == "本週新來源：加入 12、排除 3、停用 1"
    # 加入的最多列 10 個，其餘只寫數量
    assert lines[:2] == ["加入：Scholarship 0　https://u0.eu/s", "加入：Scholarship 1　https://u1.eu/s"]
    assert "（還有 2 個，見網頁的設定頁）" in lines
    assert "排除的原因：留學國家不在歐洲 2、國籍規定排除台灣 1" in lines
    assert "停用：Old programme（連續 3 次抽不到有效獎學金）" in lines
    assert lines[-1] == "不對的來源可以在網頁的設定頁停用"


def test_report_lists_newly_unreachable_and_recovered_sources() -> None:
    # 11-08 使用者選 C：抓不到、抓得到了不再一則一則送，併進每日檢查報告
    _, lines = report.report_message(
        local_date=date(2026, 11, 9),
        started_at=datetime(2026, 11, 9, 0, 10, tzinfo=UTC),
        finished_at=datetime(2026, 11, 9, 2, 0, tzinfo=UTC),
        sources={"extracted": 2, "unchanged": 100, "failed": 3},
        new_events=0,
        skipped=[],
        marked=[("MAGMA", "gaierror: [Errno 8] nodename nor servname provided"), ("REPLAY", "httpx.ConnectTimeout: timed out")],
        recovered=["CyberMACS"],
    )
    assert "新標記抓不到 2 個（之後每 7 天試一次）：" in lines
    assert "・MAGMA：網域不存在" in lines and "・REPLAY：連線逾時" in lines
    assert "抓得到了 1 個，回到每天檢查：CyberMACS" in lines


def test_error_kinds_in_plain_words() -> None:
    assert report.error_kind("gaierror: [Errno 8] nodename nor servname provided, or not known") == "網域不存在"
    assert report.error_kind("httpx.ConnectError: [Errno 8] nodename nor servname provided") == "網域不存在"
    assert report.error_kind("httpx.ConnectTimeout: timed out") == "連線逾時"
    assert report.error_kind("TemporaryFetchError: robots.txt 暫時無法讀取（520）") == "對方伺服器錯誤"
    assert report.error_kind("SSLCertVerificationError: certificate verify failed") == "對方憑證或加密設定有問題"
    assert report.error_kind("httpx.ConnectError: [SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED]") == "對方憑證或加密設定有問題"
    assert report.error_kind("httpx.HTTPStatusError: 404 Not Found") == "其他：httpx.HTTPStatusError: 404 Not Found"


def test_new_url_results_are_one_message_a_day() -> None:
    # ADR-093：找新網址的結果一天合成一則
    title, lines = report.new_url_digest_message([
        ("replaced", "CyberMACS", "https://old.example/ → https://new.example/"),
        ("mismatch", "REPLAY", "https://other.example/（新網頁上找不到同一個學程的名稱或主辦單位）"),
        ("not_found", "MAGMA", ""),
        ("not_found", "SERP", ""),
    ]) or ("", [])
    assert title == "找新網址：換了 1 個、對不上 1 個、沒找到 2 個"
    assert lines == [
        "換了：CyberMACS　https://old.example/ → https://new.example/",
        "對不上，沒換：REPLAY　https://other.example/（新網頁上找不到同一個學程的名稱或主辦單位）",
        "沒換的 7 天後再找一次",
    ]
    assert report.new_url_digest_message([("not_found", "MAGMA", "")]) is None  # 全部沒找到：不送


def test_new_url_message_lists_superseded_sources() -> None:
    # 11-08 使用者選 B：舊來源被目錄裡的新來源取代、自動停用，也寫進當天的找新網址通知
    message = report.new_url_digest_message([("superseded", "SERP", "已由另一個來源（#3801）取代，舊來源已停用")])
    assert message is not None
    title, lines = message
    assert title == "找新網址：換了 0 個、對不上 0 個、沒找到 0 個、被取代停用 1 個"
    assert lines[0] == "被取代停用：SERP　已由另一個來源（#3801）取代，舊來源已停用"
