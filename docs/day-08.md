# 第 8 天：Telegram 通知

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。依 ADR-039 的方式分階段做。

目標：每天的檢查跑完後，把四種事件（新獎學金、新年度開放、截止提醒、資料變更）裡適配度 60 分以上的，先記進 events 表（Outbox），再送到你的 Telegram；一次超過 5 則就合併成一則摘要；斷路器打開時也通知你。

## 本計畫記錄的決定

- 通知先寫進 events 表，再由送出工作讀出、合併、送出、標記已送（ADR-062）
- 通知插座收結構化通知，Telegram 轉接頭負責排版、轉義與切段（ADR-063、ADR-005）
- 門檻 60 分指的是適配度（ADR-059、060）；events 表有 user_id（ADR-021）
- 斷路器打開時要通知（ADR-013、056）
- 執行中決定：通知只看可能影響能不能申請的變更（截止日、國籍資格、可讀學位），官網真的改了才算變更（ADR-064）

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
   - 執行中依 ADR-064 改了：金額與文件要求不通知；國籍資格變成「原文沒寫」不通知；另外加上核對原文（第 28–31 點）
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
17. 子 agent 的工作目錄是從「已推上遠端的版本」建立的，所以通知插座先 commit 並推上去，子 agent 才拿得到
18. 改寫 `.env` 只動一個鍵、其他行原封不動，用測試釘住（.env 裡有 Gemini 金鑰與 token）
19. Telegram 的 HTTP 呼叫：token 只從設定讀、不印出；網路錯誤改丟不帶原始例外的暫時錯誤（原始訊息可能含有網址，網址含 token）；429 在 60 秒內就照 retry_after 等一次；5xx 算暫時錯誤
20. 設定指令會印出找到的聊天名稱讓你確認是自己（只出現在你的終端機），以防有別人先傳訊息給機器人
21. 標題或內容行裡的換行換成空格，每個 HTML 標籤都在同一行，依行切段才不會切斷標籤（子 agent 提出的風險）
22. 「新年度開放」的去重鍵改成「哪一屆」（入學年度的第一個年份，沒寫就用截止年份），同一屆只通知一次；剛通知過「新獎學金」的，不再另外通知新年度
23. 「資料變更」的標題直接帶變更內容；摘要只列標題，這樣也看得懂（不用改既有的摘要測試）
24. 截止日的變更只比同一屆的：官網把上一屆換成下一屆，是新年度開放，不是截止日變更（子 agent 提出）
25. 舊的文件清單是空的、國籍資格是空值或不認得的值：不通知、不出錯（子 agent 提出）
26. 斷路器打開時通知，去重鍵用打開的時間（同一次只通知一次）；用指令手動打開也會通知
27. 設定加上 `hide_input_in_errors`：設定出錯時，錯誤訊息不印出輸入的值（執行時發現第 1 點）
28. 核對原文（ADR-064 的做法）：會推播的欄位（截止日、國籍範圍、國家清單、學位），要有一句引用「只出現在新版網頁」或「只出現在舊版網頁」，才記成變更。ADR-064 寫的是前者；我加上後者，才抓得到官網刪掉一輪截止日這種改動（新的引用都是舊版就有的句子）
29. 引用不在自己那一版原文裡（AI 改寫過），不能當證據，略過；找引用的方式和驗證者一樣（全形轉半形、不管空白、刪節號、表格切段）
30. 新舊兩版原文：用抽取結果記下的快照雜湊（`meta.snapshots`）找回快照檔，用同一個函式轉成文字（網頁取可見文字、PDF 用 pdfplumber），和抽取時核對用的原文一樣
31. 其他欄位（金額、補助內容、語言、其他資格、類別、文件要求）不通知，照舊記變更紀錄；網頁要不要顯示這些紀錄，第 9 天做網頁時再看（和 #55 有關）
32. 實作時調整第 28、29 點：引用在原文裡找到的程度分三級（逐字找到、只有用表格的寬鬆找法找到、找不到），新舊兩版的程度不一樣才算官網改了。原因：寬鬆找法允許引用最後不到 6 個字的一小段出現在附近任何地方，「Deadline: January 15」在改成 16 日的新版裡，只要附近有個「5」就算找到，會漏掉只改一個數字的截止日。分三級之後，AI 改寫過的引用（兩版都找不到）和 PDF 表格的引用（兩版都只能寬鬆找到）都不會被誤判
33. 快照紀錄找不到（理論上不會發生，ADR-019 不刪快照）：少了那一頁的原文，那一頁的引用就當成找不到，不讓抽取失敗

## 待使用者決策

1. ~~改兩個既有測試~~：已由 ADR-064 決定。國籍資格變成「原文沒寫」不通知；文件要求整個不通知，所以不用改成中文
2. ~~「金額」與「文件要求」的變更通知~~：已由 ADR-064 決定，兩種都不通知
3. 截止日「改到已經過去的日期」要不要通知（執行時發現第 7 點，ReSound）
4. 刪不刪 PIONEER 那 7 筆測試造成的變更紀錄（執行時發現第 9 點）

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

# features/notifications/rules.py（純函式；實作時依子 agent 的寫法調整了名稱）
REMINDER_DAYS = (30, 14, 7, 3, 1)
def reminder_bucket(days_left: int, sent: set[int]) -> int | None
def cycle_year(intake: str | None, closes_year: int) -> int            # 哪一屆
def describe_change(field: str, old: Any, new: Any) -> str | None      # 截止日、資格（ADR-064 拿掉金額、文件）

# features/scholarships/changes.py（ADR-064 核對原文）
QUOTE_KEYS = {"nationality_scope": ..., "nationalities": ..., "degrees": ..., "windows": ...}  # 欄位 → 引用
def website_changed(field, old, new, old_text, new_text) -> bool    # 有引用只在新版或只在舊版出現
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
| test_notification_rules.py | 截止提醒的格子（含錯過的格子）；截止日與資格的變更；~~金額數字的變更；新增的文件~~（ADR-064 改成不通知）；超過 5 則合併 |
| test_changes.py | ADR-064：引用只在新版或只在舊版網頁出現才算官網改了；AI 改寫過的引用不算證據 |
| test_notify_telegram.py | 轉成 HTML 並轉義；超過 4096 字依行切段；實作時補：每個標籤都在同一行 |
| test_notify_setup.py | 實作時補：改寫 .env 只動一個鍵 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 純函式（紅綠循環）

- [x] R1 截止提醒的格子 -> verify: `uv run pytest tests/test_notification_rules.py -k reminder`

  ```
  1 passed, 6 deselected in 0.02s
  ```
- [x] R2 截止日與資格的變更 -> verify: `uv run pytest tests/test_notification_rules.py -k eligibility`

  ```
  1 passed, 6 deselected in 0.02s
  ```
- [x] R3 金額數字的變更與新增的文件 -> verify: `uv run pytest tests/test_notification_rules.py -k "amount or documents"`

  ```
  2 passed, 5 deselected in 0.02s
  ```
- [x] R4 超過 5 則合併成摘要 -> verify: `uv run pytest tests/test_notification_rules.py -k bundle`

  ```
  1 passed, 6 deselected in 0.02s
  ```
- [x] T1 轉成 HTML 並轉義 -> verify: `uv run pytest tests/test_notify_telegram.py -k html`

  ```
  2 passed, 2 deselected in 0.03s   ← 含實作時補的「每個標籤都在同一行」
  ```
- [x] T2 超過 4096 字依行切段 -> verify: `uv run pytest tests/test_notify_telegram.py -k split`

  ```
  2 passed, 2 deselected in 0.02s   ← 子 agent 多補一個「空行要留著」
  ```

實作時補的規則（「Claude 自行決定」第 18、21、24、25 點），同樣紅綠循環：

- [x] R5 截止日只比同一屆的 -> verify: `uv run pytest tests/test_notification_rules.py -k same_intake`

  ```
  1 passed, 6 deselected in 0.02s
  ```
- [x] R6 AI 多半漏抽的變更不通知 -> verify: `uv run pytest tests/test_notification_rules.py -k missed`

  ```
  2 passed, 5 deselected in 0.02s   ← 另一個是名稱裡也有 missed 的 R1
  ```
- [x] S1 改寫 .env 只動一個鍵 -> verify: `uv run pytest tests/test_notify_setup.py`

  ```
  1 passed in 0.02s
  ```

執行中依 ADR-064 調整（使用者的決定，也就是同意改既有測試；改測試各自一個紅色 commit）：

- [x] R7 金額與文件要求的變更不通知 -> verify: `uv run pytest tests/test_notification_rules.py -k not_notified`

  ```
  1 passed, 5 deselected in 0.03s   ← 取代原本 R3 的兩個測試
  ```
- [x] R8 國籍資格變成「原文沒寫」不通知 -> verify: `uv run pytest tests/test_notification_rules.py -k eligibility`

  ```
  1 passed, 5 deselected in 0.03s   ← R2 裡那一行改成不通知
  ```
- [x] C1 有一句引用只出現在新版或只出現在舊版網頁，才算官網改了 -> verify: `uv run pytest tests/test_changes.py -k one_version`

  ```
  1 passed, 4 deselected in 0.02s
  ```
- [x] C2 AI 改寫過的引用不算證據 -> verify: `uv run pytest tests/test_changes.py -k rewrote`

  ```
  1 passed, 4 deselected in 0.02s
  ```
- [x] C2b 只改了最後幾個字（1 月 15 日 → 16 日）也算（實作時發現，「Claude 自行決定」第 32 點） -> verify: `uv run pytest tests/test_changes.py -k last_few`

  ```
  1 passed, 4 deselected in 0.02s
  ```
- [x] C3 抽取時，會推播的欄位只記官網真的改了的變更 -> verify: 回測已記下的截止日變更；再用真的 `save()` 重播（交易最後還原，不花 AI 費用）。原本打算實跑一個來源，改成重播：實跑要等網頁剛好又變了才會重抽，重播可以指定真的變更和雜訊各測一次

  ```
  回測（快照歷史重建新舊兩版原文）：
    10-23 截止日變更 35 筆 → 核對後留下 17 筆；原本會通知 3 筆 → 2 筆
    10-24 截止日變更 27 筆 → 核對後留下  9 筆；原本會通知 3 筆 → 1 筆
    留下的抽看都是官網真的改了，例如 Master LIVE「19 Nov 2026 to 21 Jan 2027」→「18 Nov 2026 to 20 Jan 2027」、
    學程 179 把 2025/26 的三輪換成 2026/27、學程 50 的開放日從 Oct. 15th 改成 Oct. 16
  重播 save()：
    變更 #400（獎學金 97，Master LIVE）重播後寫入：['windows']
    變更 #274（獎學金 6）重播後寫入：沒有
    變更 #279（獎學金 10）重播後寫入：沒有
    changes 表重播後仍是 453 筆（交易已還原）
  ```

### 2. 資料表與產生事件（Claude）

- [x] 遷移：events -> verify: `uv run alembic upgrade head` 與 `\d events`

  ```
  Running upgrade d209140c2cbd -> a5da0858fb77, events   （降級、再升級也跑過）
  events: id, user_id, kind, scholarship_id (FK cascade), dedup_key, payload jsonb, status default 'pending',
          created_at, sent_at, attempts default 0, last_error；UNIQUE (user_id, dedup_key)
  ```
- [x] 第一次產生事件建基準線 -> verify: 貼出 baseline 與 pending（截止提醒）的筆數

  ```
  {'new_scholarship:baseline': 21, 'new_cycle:baseline': 5, 'change:baseline': 5}
  （適配度 60 分以上的 21 筆裡，30 天內沒有截止的，所以沒有截止提醒）
  ```
- [x] 再產生一次不會重複 -> verify: 第二次新增 0 筆

  ```
  新增 0 筆
  ```
- [x] 預覽 -> verify: 貼出預覽的訊息

  ```
  $ uv run python -m app.features.notifications.send --preview
  待送的訊息 0 則：
  ```

### 3. Telegram（要先有 token）

- [ ] setup：找到聊天 ID、寫進 .env、送測試訊息 -> verify: 你收到測試訊息；`.env` 有 `TELEGRAM_CHAT_ID`（只看有沒有）

  ```
  token 有設定: True ｜聊天 ID 有設定: True      ← 你在自己的終端機跑完 setup；等你確認收到測試訊息
  ```
- [ ] send_events：待送變已送，再送一次是 0 則 -> verify: 貼出筆數，你收到訊息

  ```
  21:22:47 worker 執行 send_events：事件 32 new_scholarship（DEAI，100 分）pending → sent，嘗試 1 次、沒有錯誤
  $ uv run python -m app.features.notifications.send
  {}                                             ← 再送一次是 0 則；等你確認收到 DEAI 那則
  ```
- [ ] 斷路器打開時通知 -> verify: 手動打開斷路器，你收到通知；之後恢復

  ```
  $ uv run python -m app.features.pipeline.breaker --open "第 8 天測試：手動打開斷路器"
  斷路器打開中（2026-10-24 14:21 UTC）：第 8 天測試：手動打開斷路器
  事件 34 system sent：建立 14:21:49 UTC、送出 14:21:50 UTC，嘗試 1 次、沒有錯誤
  $ uv run python -m app.features.pipeline.breaker --reset
  斷路器關著：AI 步驟照常執行                       ← 等你確認收到「斷路器打開」那則
  ```

### 4. 串進每天的流程

- [x] 收尾最後產生事件、放送出工作 -> verify: `uv run python -m app.features.pipeline.run --source ID`，貼出收尾與送出的結果

  改用今天真的每日檢查當證據（比手動跑一個來源更完整）：

  ```
  data/logs/worker.log
  21:21:50 finish_daily_run(3)   ← 早上被刪掉紀錄的那一輪，重試的來源最後都結束了，照樣收尾
  21:22:47 send_events()          ← 產生 new:188（pending）與 cycle 基準線，送出 1 則
  21:40:02 finish_daily_run(4)   ← 今天這一輪收尾：runs.counts 的 events 是 {}（沒有新事件）
  21:40:03 send_events()          ← 沒有待送的
  ```

### 5. 收尾

- [ ] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

## 執行時發現

1. token 外洩：你把 `TELEGRAM_BOT_TOKEN` 加進 .env 時，設定類別還沒宣告這個欄位，pydantic 報錯時把值印在錯誤訊息裡；我又用管線把測試輸出接給 tail，沒擋住、也沒發現測試失敗就推上去了。修正：宣告欄位、加 `hide_input_in_errors`、推之前的檢查改用 `set -o pipefail`；token 請你撤銷換新
2. 同一個原因讓背景工作在 10:16–10:19 一啟動就失敗（日誌記了 408 次），今天那輪檢查刪掉紀錄後重新開始（105 個來源）
3. 第一次產生事件：新獎學金 21、新年度開放 5、資料變更 5 都記成基準線；再產生一次新增 0
4. 資料變更的雜訊：基準線裡的 5 筆，PIONEER 的金額從「around 419 euros（德國的交換補助）」變成「5,613.10 EUR（學費）」，是 AI 抽了不同的金額；EDISS 的金額多抽到 800／310€。文件要求也有類似情形。數量不大（只有適配度 60 分以上的才通知）
5. 送出的實測要等新的 token 與聊天 ID
6. 雜訊的根本原因（使用者要求先找源頭）：抓網頁時，雜湊算的是整頁可見文字，頁面上每天會變的東西（更新時間、新聞列表）讓雜湊每天都變 → 整頁重抽 → AI 每次抽的結果略有不同 → 新舊兩份 AI 結果的差異被記成變更。核對原文（第 28–33 點）處理了「記成變更」這一段；整頁每天重抽（10-23 有 49 筆、10-24 有 35 筆獎學金重抽）還是會花 AI 費用，另外處理
7. ReSound（獎學金 87）目前的資料是錯的：官網寫「Applications for ReSound 2027 are now open and will close on Tuesday 12th January 2027」，AI 這次卻抽了同一頁上 2025/26 那一屆的句子（2026-01-20 截止），還標成 2027 屆，所以現在顯示已截止。核對原文擋不住這種情況（官網那句確實改寫過），通知會寫「截止日：2027-01-12 → 2026-01-20」
8. 驗證者的寬鬆找法有同樣的漏洞（第 32 點）：AI 的引用如果只有最後一兩個字和原文不同（例如把 16 日寫成 15 日），附近剛好有那個數字就會被當成找到，接著 AI 查核員看的是引用本身，也會判定「有依據」。第 3 天起就是這樣，今天沒改，列入報告
9. 10-20 的 7 筆變更紀錄（PIONEER，獎學金 181）是我第 7 天測試時拿掉 meta 造成的，不是官網改的；其中 1 筆已記成基準線事件，沒有送出。要刪掉請你決定
10. 早上刪掉紀錄的那一輪（run 3），它排進佇列的工作還在：重試的來源全部結束後，21:21 照樣執行收尾，還產生並送出了第一則真的通知（DEAI）。收尾找不到 run 3 的紀錄就不寫統計，沒有出錯；所以 run 4 記的 events 是空的
11. 今天這一輪有 19 個來源最後失敗（例如 robots.txt 回 525，對方網站的暫時錯誤），明天會再試；原因還沒逐一看
