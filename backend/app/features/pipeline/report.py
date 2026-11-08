"""每日檢查的系統通知（ADR-075、076）：每日檢查報告、在等前一輪收尾、前一輪太久。

這裡只產生文字（純函式，好測試）；tick 與收尾工作把它寫成系統事件，各自一則、不併進摘要。
"""

from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# 系統通知的標題，以及內容的每一行
Message = tuple[str, list[str]]


DIGEST_LISTED = 10  # 每週摘要最多列幾個加入的來源（「Claude 自行決定」第 24 點）


def day(value: date) -> str:
    """日期寫成 11-01。"""
    return value.strftime("%m-%d")


def clock(moment: datetime, local_date: date) -> str:
    """台灣時間；不在這一輪那天的（例如拖過午夜），前面加上日期。"""
    taipei = moment.astimezone(TAIPEI)
    return taipei.strftime("%H:%M") if taipei.date() == local_date else taipei.strftime("%m-%d %H:%M")


def report_message(
    local_date: date,
    started_at: datetime,
    finished_at: datetime,
    sources: dict[str, int],
    new_events: int,
    skipped: list[tuple[date, bool]],
    ai_cost: tuple[float, float, float] | None = None,
    marked: list[tuple[str, str]] | None = None,
    recovered: list[str] | None = None,
) -> Message:
    """每日檢查報告：哪一天、何時開始與收尾（台灣時間）、來源結果、這輪產生幾則通知。

    skipped：和上一輪之間沒有單獨檢查的日子，以及那天是不是在等前一輪收尾。
    """
    total = sum(sources.values())
    # 來源工作的結果（process_source 回傳的代碼）；failed 是重試完還是失敗的，多半是網站連不上
    changed, failed = sources.get("extracted", 0), sources.get("failed", 0)
    # noise：網頁有變，但只有無關內容變了、沒重抽（ADR-079），算進「沒變」並另外註明
    noise = sources.get("noise", 0)
    unchanged = sources.get("unchanged", 0) + noise
    noise_note = f"（其中 {noise} 個只有無關內容變了）" if noise else ""
    lines = [
        f"{clock(started_at, local_date)} 開始，{clock(finished_at, local_date)} 收尾",
        (
            f"{total} 個來源：有變 {changed}、沒變 {unchanged}{noise_note}、抓不到 {failed}、"
            f"其他 {total - changed - unchanged - failed}"
        ),
        f"這輪產生 {new_events} 則通知",
    ]
    if ai_cost is not None:
        today_ntd, month_ntd, cap_ntd = ai_cost
        lines.append(f"AI 費用：今天約 NT${today_ntd:,.2f}，本月約 NT${month_ntd:,.0f}（上限 NT${cap_ntd:,.0f}）")
    if marked:
        # 連續 3 天抓不到（ADR-080）：併進報告，不再一則一則送（11-08 使用者選 C）
        lines.append(f"新標記抓不到 {len(marked)} 個（之後每 7 天試一次）：")
        lines += [f"・{name}：{error_kind(error)}" for name, error in marked]
    if recovered:
        lines.append(f"抓得到了 {len(recovered)} 個，回到每天檢查：" + "、".join(recovered))
    for skipped_day, waited in skipped:
        reason = "沒有單獨檢查：在等前一輪收尾" if waited else "沒有檢查：那天電腦沒開或沒有網路"
        lines.append(f"{day(skipped_day)} {reason}")
    return f"每日檢查完成：{day(local_date)}", lines


def waiting_message(today: date, previous_date: date, previous_started: datetime, now: datetime) -> Message:
    """今天的檢查還沒開始：在等前一輪收尾。"""
    hours = int((now - previous_started).total_seconds() // 3600)
    return f"{day(today)} 的檢查還沒開始", [
        f"在等 {day(previous_date)} 那輪收尾（已經開始 {hours} 小時）",
        "收尾後 15 分鐘內開始",  # tick 每 15 分鐘一次
    ]


def stale_message(previous_date: date, previous_started: datetime, now: datetime) -> Message:
    """前一輪開始太久還沒收尾：可能壞了，今天照常開始。"""
    hours = int((now - previous_started).total_seconds() // 3600)
    return f"{day(previous_date)} 那輪開始 {hours} 小時還沒收尾", [
        "可能是收尾壞了，或電腦關機太久；今天照常開始",
        "查原因：backend/data/logs/worker.log",
    ]


def discovery_digest_message(
    added: list[tuple[str, str]], rejected: list[tuple[str, str]], disabled: list[tuple[str, str]]
) -> Message:
    """發掘 agent 的每週摘要（ADR-078）：加入（名稱, 網址）、排除與停用（名稱, 原因）。"""
    title = f"本週新來源：加入 {len(added)}、排除 {len(rejected)}、停用 {len(disabled)}"
    lines = [f"加入：{name}　{url}" for name, url in added[:DIGEST_LISTED]]
    if len(added) > DIGEST_LISTED:
        lines.append(f"（還有 {len(added) - DIGEST_LISTED} 個，見網頁的設定頁）")
    if rejected:
        # 排除的不逐一列名稱，只統計原因：用來看規則是不是太嚴或太鬆
        reasons = Counter(reason for _, reason in rejected)
        lines.append("排除的原因：" + "、".join(f"{reason} {n}" for reason, n in reasons.most_common()))
    lines += [f"停用：{name}（{reason}）" for name, reason in disabled]
    lines.append("不對的來源可以在網頁的設定頁停用")
    return title, lines


def new_url_found_message(name: str, old: str, new: str) -> Message:
    """找新網址（ADR-080）：確認是同一個學程，已經換網址。"""
    return f"找到新網址：{name}", [f"舊：{old}", f"新：{new}", "回到每天檢查，資料會照常抓取與核對"]


def new_url_mismatch_message(name: str, url: str, reason: str) -> Message:
    """找新網址（ADR-080）：agent 提議的網址對不上，沒有換。"""
    return f"新網址對不上，沒有換：{name}", [f"agent 找到：{url}", f"原因：{reason}", "7 天後再找一次"]


def error_kind(error: str) -> str:
    """抓不到的原因換成白話的種類（11-08：抓不到的通知併進每日報告）。"""
    lowered = error.lower()
    if "nodename nor servname" in lowered or "name or service not known" in lowered or "gaierror" in lowered:
        return "網域不存在"
    if "timeout" in lowered or "timed out" in lowered:
        return "連線逾時"
    if "ssl" in lowered or "certificate" in lowered:
        return "對方憑證或加密設定有問題"
    if "robots.txt 暫時無法讀取" in error or "5xx" in lowered or "server error" in lowered:
        return "對方伺服器錯誤"
    return f"其他：{error[:80]}"
