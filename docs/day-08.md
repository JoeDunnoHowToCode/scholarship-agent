# 第 8 天：Telegram 通知

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。依 ADR-039 的方式分階段做。

目標：每天的檢查跑完後，把四種事件（新獎學金、新年度開放、截止提醒、資料變更）裡適配度 60 分以上的，先記進 events 表（Outbox），再送到你的 Telegram；一次超過 5 則就合併成一則摘要；斷路器打開時也通知你。

## 本計畫記錄的決定

- 通知先寫進 events 表，再由送出工作讀出、合併、送出、標記已送（ADR-062）
- 通知插座收結構化通知，Telegram 轉接頭負責排版、轉義與切段（ADR-063、ADR-005）
- 門檻 60 分指的是適配度（ADR-059、060）；events 表有 user_id（ADR-021）
- 斷路器打開時要通知（ADR-013、056）

## Claude 自行決定（小問題，請事後檢查）

1. events 表欄位：id、user_id、kind（new_scholarship、new_cycle、deadline、change、system）、scholarship_id（可空，連動刪除）、dedup_key（同一位使用者內唯一）、payload（JSONB：標題、內容行、連結）、status（pending 待送、sent 已送、baseline 基準線、failed 失敗）、created_at、sent_at、attempts、last_error
2. 第一次啟用時建基準線：現有的獎學金、申請期與變更紀錄只記成 baseline、不送，不然第一次會一口氣送 180 則「新獎學金」。截止提醒不算歷史，照樣送
3. 門檻放在設定（`notify_threshold`，預設 60），第 10 天的設定頁再改成網頁可調；一筆獎學金有好幾個類別時，看分數最高的那個；斷路器事件不看門檻
4. 新獎學金：代表的獎學金（不是重複的那筆）第一次出現，而且最高分達門檻
5. 新年度開放：出現新的截止日（新的一屆），而且開放中或即將開放、可能適用你（第 7 天的 still_possible）；去重鍵 `cycle:{獎學金}:{截止日}`
6. 截止提醒：剩 30、14、7、3、1 天；只看真的（不是預估）、還沒截止、可能適用你的申請期。每天的檢查不一定每天都跑（電腦沒網路），所以送「還沒送過的最小一格」：例如剩 30 天那次錯過了、現在剩 12 天，就送「14 天」那格，不補送 30 天；去重鍵 `deadline:{獎學金}:{截止日}:{格}`；截止日沒核對過的，內容會註明
7. 剩幾天：用申請期原本時區的截止日期，減掉台灣的今天
8. 資料變更（spec：截止日、金額、資格、文件要求；排版或錯字修改不通知），比整理過的值，不比文字：
   - 截止日：同一屆的截止日期變了
   - 資格：國籍範圍、國家清單或學位清單變了
   - 金額：金額文字裡的數字變了
   - 文件要求：只通知新增的文件種類；變少或變空白不通知，那多半是 AI 這次沒抽到
   - 依據：第 7 天同一天有 49 筆獎學金記了變更，抽看大多是 AI 換了說法、或這次沒抽到
9. 合併：一次要送的待送事件超過 5 則，就合成一則摘要（依類型分組）；5 則以內就各送一則
10. 送出時機：每天的收尾工作最後產生事件，接著放一件 send_events 工作；另外有手動送出的指令
11. Telegram 轉接頭：用 HTML（標題粗體、連結），轉義 `<`、`>`、`&`；超過 4096 字就依行切成好幾則。遇到錯誤時：
    - 429：在 60 秒內照 retry_after 等，再送一次；等太久就丟出例外讓 RQ 重試
    - 網路錯誤與 5xx：丟出例外讓 RQ 重試
    - 400：記成 failed，留下錯誤原因
    - 401、403、404（token 或聊天設定有誤）：保持待送，印出錯誤
12. 聊天 ID：你按過機器人的 Start 之後，自己在終端機執行 `uv run python -m app.core.notify.setup`。程式用 getUpdates 找到你的聊天 ID，寫進 `backend/.env`（`TELEGRAM_CHAT_ID`），再傳一則測試訊息；聊天 ID 不經過這個對話
13. 通知內容用繁體中文，只放獎學金名稱、分數、截止日與連結，不放領域契合的理由（ADR-063）
14. Telegram 轉接頭要等 `backend/.env` 有 `TELEGRAM_BOT_TOKEN` 才寫（CLAUDE.md：不寫目前無法測試的程式）；在那之前先做 events、規則與預覽
15. 預覽指令：`uv run python -m app.features.notifications.preview` 列出待送的事件和會組成的訊息，不送出
16. 純函式（截止提醒的格子、變更判斷、合併、Telegram 排版）由 sub agent 平行做；Claude 做資料表、產生事件、送出工作與實跑

## 待使用者決策

（目前沒有）

## 設計草圖

### 資料表

events（新）：見「Claude 自行決定」第 1 點；（user_id, dedup_key）唯一，所以重跑產生事件不會重複

### 流程

```
每天的收尾 finish_daily_run（第 7 天）
  … 更新申請期 → 去重 → 評分
  └─ generate_events：依第 4–8 點產生事件（去重鍵一樣就跳過）
       └─ 放一件 send_events：讀待送的 → 超過 5 則合併 → 經插座送出 → 標記已送
斷路器打開時：多產生一件 system 事件，送出流程一樣
```

### 介面

```python
# core/notify/base.py（插座）
@dataclass(frozen=True)
class Notification:
    kind: str
    title: str
    lines: tuple[str, ...] = ()
    url: str | None = None

class Notifier(Protocol):
    def send(self, notification: Notification) -> None: ...

# core/notify/telegram.py（轉接頭）
def to_html(notification: Notification) -> str
def split_message(text: str, limit: int = 4096) -> list[str]
class TelegramNotifier: ...

# features/notifications/rules.py（純函式）
REMINDER_DAYS = (30, 14, 7, 3, 1)
def reminder_bucket(days_left: int, sent: set[int]) -> int | None
def deadline_or_eligibility_changes(old: dict, new: dict) -> list[str]
def amount_changed(old: str | None, new: str | None) -> bool
def added_documents(old: list[str], new: list[str]) -> list[str]
def bundle(notifications: list[Notification]) -> list[Notification]   # 超過 5 則合併成摘要
```

### 指令

1. `uv run python -m app.core.notify.setup`：找到聊天 ID、寫進 .env、送測試訊息（你自己執行）
2. `uv run python -m app.features.notifications.preview`：預覽，不送出
3. `uv run python -m app.features.notifications.send`：馬上送出待送的事件

### 不在第 8 天範圍

Telegram 互動按鈕與接收指令（v1.1、#29）、網頁的通知歷史（第 9 天）、在設定頁改門檻（第 10 天）

## 測試哪些行為

| 檔案 | 行為 |
| --- | --- |
| test_notification_rules.py | 截止提醒的格子（含錯過的格子）；截止日與資格的變更；金額數字的變更；新增的文件；超過 5 則合併 |
| test_notify_telegram.py | 轉成 HTML 並轉義；超過 4096 字依行切段 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 純函式（紅綠循環）

- [ ] R1 截止提醒的格子 -> verify: `uv run pytest tests/test_notification_rules.py -k reminder`
- [ ] R2 截止日與資格的變更 -> verify: `uv run pytest tests/test_notification_rules.py -k eligibility`
- [ ] R3 金額數字的變更與新增的文件 -> verify: `uv run pytest tests/test_notification_rules.py -k "amount or documents"`
- [ ] R4 超過 5 則合併成摘要 -> verify: `uv run pytest tests/test_notification_rules.py -k bundle`
- [ ] T1 轉成 HTML 並轉義 -> verify: `uv run pytest tests/test_notify_telegram.py -k html`
- [ ] T2 超過 4096 字依行切段 -> verify: `uv run pytest tests/test_notify_telegram.py -k split`

### 2. 資料表與產生事件（Claude）

- [ ] 遷移：events -> verify: `uv run alembic upgrade head` 與 `\d events`
- [ ] 第一次產生事件建基準線 -> verify: 貼出 baseline 與 pending（截止提醒）的筆數
- [ ] 再產生一次不會重複 -> verify: 第二次新增 0 筆
- [ ] 預覽 -> verify: 貼出預覽的訊息

### 3. Telegram（要先有 token）

- [ ] setup：找到聊天 ID、寫進 .env、送測試訊息 -> verify: 你收到測試訊息；`.env` 有 `TELEGRAM_CHAT_ID`（只看有沒有）
- [ ] send_events：待送變已送，再送一次是 0 則 -> verify: 貼出筆數，你收到訊息
- [ ] 斷路器打開時通知 -> verify: 手動打開斷路器，你收到通知；之後恢復

### 4. 串進每天的流程

- [ ] 收尾最後產生事件、放送出工作 -> verify: `uv run python -m app.features.pipeline.run --source ID`，貼出收尾與送出的結果

### 5. 收尾

- [ ] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

## 執行時發現

（實作與實跑中遇到的事）
