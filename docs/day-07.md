# 第 7 天：背景工作、排程與重試

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。依 ADR-039 的方式分階段做。

目標：評分改成只算適配度；預估的下一屆不再落在過去；用 RQ 讓每個來源各自跑一條流程，錯誤依種類處理，Gemini 出問題就打開斷路器；每天第一次有網路時自動跑當天的檢查；登入後由 launchd 自動啟動。

## 本計畫記錄的決定

- 重試、退避與失敗隔離：每個來源各自一條流程；錯誤分成重試、不重試、打開斷路器三種（ADR-056）
- 第一版留在本機，雲端部署之後再做；每天第一次有網路時補跑（ADR-057）
- 預估的下一屆：24 個月內往後推，超過就標「資料過舊」、每月檢查（ADR-058）
- 評分只算適配度：國籍、學位、領域契合、想去的國家；時間、補助、名額只顯示（ADR-059、060）
- 登入後由 launchd 自動啟動 worker 與排程器（ADR-061）

## Claude 自行決定（小問題，請事後檢查）

1. 「想去的國家」怎麼比對：類別的留學國家（類別沒寫就用獎學金的）和你想去的國家有交集 → 10 分；沒有交集 → 0 分；獎學金沒寫留學國家 → 5 分（資料沒寫給 5 分，和 score-3 的規則一致）；你沒填 → 不評
2. 權重：領域契合 70%、想去的國家 30%。例子：領域滿分、但不在你想去的國家 → 70 分（還是達到第 8 天 60 分的通知門檻）；國家對、領域只有 3 分 → 51 分。只填其中一項就只用那一項；兩項都沒填 → 100 分，再套硬性條件的上限（ADR-060）
3. 時間條件照樣計算、存下原因，給網頁分組顯示（第 9 天），但不再算進上限
4. 每個來源一件工作 `process_source(id)`，在同一件工作裡依序做抓取 →（內容有變才）抽取 → 建索引。不拆成三件工作串起來，因為 RQ 的工作鏈在前一件失敗時，後面的會一直停在「等待」，等著「全部做完再評分」的收尾工作就永遠等不到；整件重試也是安全的（冪等）
5. 每天的收尾工作 `finish_daily_run()`：等當天所有來源的工作結束（成功或最後失敗都算，RQ 的 `Dependency(allow_failure=True)`）之後，依序更新申請期與封存 → 去重 → 評分（內容沒變就沿用）
6. 排程不用 cron 字串，用 rq cron 的「每 15 分鐘」放一件 `tick()`：它判斷有沒有網路、今天（台灣時間）跑過沒、哪些來源到期。rq cron 2.12 的 cron 字串依 UTC 計算（3.0 才改成本地時間），由 tick 自己用台灣時間判斷比較不會錯；rq cron 啟動時會立刻放一次 interval 工作，所以登入後馬上就會補跑
7. 判斷有沒有網路：連 `captive.apple.com`（macOS 自己檢查網路用的網址）；連不上就等下一個 tick
8. 檢查頻率（ADR-058）：使用中的每天；封存、24 個月內的，從預估開放前一個月（recheck_from）起每 7 天；資料過舊的每 30 天；目錄來源和還沒抽出獎學金的來源每天；需人工的不檢查
9. 「資料過舊」不另外存欄位：由最近一次真的截止日即時算出來（超過 730 天）
10. 錯誤分類（ADR-056）：
    - 重試（1、5、30 分鐘後）：網路錯誤與逾時、網站 5xx、Gemini 的 429、5xx 與逾時
    - 不重試、記下原因：網站的 404 等 4xx；被擋（403、429、robots、驗證碼 → 需人工，ADR-028）；AI 抽出的資料重試後仍驗證不過
    - 打開斷路器：Gemini 回 402（額度用完）、401 或 403（金鑰有問題）
    - Gemini 的錯誤在我們的轉接頭裡都包成 `LLMError`，原本的錯誤留在 `__cause__`，分類時往裡面找狀態碼
11. 斷路器的狀態存在 PostgreSQL 的一張小表：打開時記下原因與時間；AI 步驟看到打開就跳過（抓取照做，網頁有變的，恢復後會補抽，因為抽取時比對的是快照雜湊）；恢復用指令；第 8 天加 Telegram 通知
12. ADR-056 原本寫「429 重試」，和 ADR-028「網站回 429 算被擋」衝突；已更正成只有 Gemini 的 429 才重試
13. 這次執行的費用上限：每件 `process_source` 和評分都帶 `--max-cost` 的同一套檢查，超過就打開斷路器（第 10 天的每月上限共用同一個斷路器）
14. macOS 的 worker 用 `SpawnWorker`（用 posix_spawn 代替 fork，避開 macOS 的 fork 問題），加 `--with-scheduler`（有間隔的重試需要）
15. launchd 兩個登入項目：worker、rq cron；KeepAlive（當掉自動重開）；日誌寫到 `backend/data/logs/`；安裝與移除各一個指令
16. docker-compose.yml 的 postgres、redis 加 `restart: unless-stopped`；Docker Desktop 要開「登入時啟動」，這個在 Docker Desktop 的設定裡，由你自己開
17. 評分提示詞改成 score-4，只評領域契合
18. 改舊測試要你同意（Gate 2）：`test_weighted_total_rescales_over_the_scored_items` 釘住的是四項權重和「一項都沒有是 0 分」；ADR-059、060 改了規則，這個測試要改成兩項權重和「都沒填是 100 分」，在自己的 commit 改
19. 預估：新增 `estimate_after(..., today)`，一直加一年直到截止日在今天以後；原本的 `estimate_next` 和它的測試不動
20. 純函式（錯誤分類、到期判斷、預估往後推、國家比對）由 sub agent 平行做，Claude 做資料表、工作、排程與實跑

## 待使用者決策

（目前沒有；第 18 點要你同意改舊測試）

## 設計草圖

### 資料表

breakers（新）：name（例如 ai）、opened_at（空白代表關著）、reason

runs（新）：每天的檢查一筆：local_date（台灣日期，唯一）、started_at、finished_at、counts（JSONB：檢查、抽取、失敗、跳過的筆數）

matches：sub_scores 改成 field、country 兩項；checks 的 time 只留給顯示

### 流程

```
每 15 分鐘 tick()
  ├─ 沒網路 → 等下一次
  ├─ 今天（台灣時間）已經開始過 → 不再開始
  └─ 開始今天的檢查：算出到期的來源
       ├─ 每個來源放一件 process_source(id)，暫時性錯誤重試 1、5、30 分鐘
       │     抓取 → 內容有變才抽取 → 建索引；斷路器打開時跳過 AI 步驟
       └─ finish_daily_run()：等上面全部結束（成功或失敗）
             更新申請期與封存（含預估、資料過舊）→ 去重 → 評分
```

### 介面（純函式）

```python
# features/pipeline/errors.py
def classify(error: BaseException) -> Literal["retry", "skip", "pause_ai"]

# features/pipeline/due.py
def is_due(frequency: Literal["daily", "weekly", "monthly"], last_checked: datetime | None,
           now: datetime, recheck_from: date | None) -> bool

# features/scholarships/cycles.py
def estimate_after(opens_at: datetime | None, closes_at: datetime, intake: str | None, today: date) -> Estimate
def is_stale(latest_close: datetime, today: date) -> bool

# features/matching/checks.py
def country_score(targets: list[str], countries: list[str]) -> float | None
WEIGHTS = {"field": 0.70, "country": 0.30}
def weighted_total(scores: dict[str, float | None]) -> float   # 一項都沒有 → 100
```

### 指令

1. `uv run rq worker -w rq.worker.SpawnWorker --with-scheduler`（由 launchd 啟動）
2. `uv run rq cron app.features.pipeline.schedule`（由 launchd 啟動）
3. `uv run python -m app.features.pipeline.run`：馬上跑一次今天的檢查（不管今天跑過沒）
4. `uv run python -m app.features.pipeline.breaker [--reset]`：看或恢復斷路器
5. `uv run python -m app.features.pipeline.launchd install|uninstall`
6. `uv run rq info`：看佇列；`uv run rq requeue --all`：重跑失敗的工作

### 不在第 7 天範圍

Telegram 通知（第 8 天）、網頁的分組顯示（第 9 天）、每週搜尋新來源（第 10 天）、雲端部署（#44）

## 測試哪些行為

| 檔案 | 行為 |
| --- | --- |
| test_matching_checks.py | 國家比對（有交集、沒交集、獎學金沒寫、你沒填）；新權重、只填一項、兩項都沒填 |
| test_cycles.py | 預估往後推到今天以後；超過 24 個月算資料過舊 |
| test_pipeline_errors.py | 網路錯誤與 5xx 重試；4xx、被擋、AI 驗證不過不重試；Gemini 402、401、403 打開斷路器；Gemini 429 重試；包在 LLMError 裡的原因也認得出來 |
| test_pipeline_due.py | 每天、每 7 天（從 recheck_from 起）、每 30 天；從沒檢查過的一定到期 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 評分只算適配度（ADR-059、060）

- [ ] C1 國家比對 -> verify: `uv run pytest tests/test_matching_checks.py -k country`
- [ ] C2 改舊的權重測試（自己的 commit，第 18 點） -> verify: `uv run pytest tests/test_matching_checks.py -k weighted`（先紅）
- [ ] C3 新權重與都沒填是 100 分 -> verify: `uv run pytest tests/test_matching_checks.py -k weighted`
- [ ] 評分指令：時間不算進上限、提示詞 score-4、加上國家分數；spec 的評分段落改寫 -> verify: `uv run python -m app.features.matching.score --max-cost 10` 貼出結果
- [ ] 再跑一次評分，全部沿用 -> verify: 貼出「沿用 N、重算 0」

### 2. 預估的下一屆（ADR-058）

- [ ] E1 預估往後推到今天以後 -> verify: `uv run pytest tests/test_cycles.py -k estimate_after`
- [ ] E2 超過 24 個月算資料過舊 -> verify: `uv run pytest tests/test_cycles.py -k stale`
- [ ] cycles 指令套用 -> verify: `uv run python -m app.features.scholarships.cycles`，再查截止日在過去的預估筆數（應為 0）與資料過舊的筆數

### 3. 背景工作（ADR-056）

- [ ] 加入 rq -> verify: `uv pip show rq | head -2`
- [ ] P1 錯誤分類 -> verify: `uv run pytest tests/test_pipeline_errors.py`
- [ ] P2 到期判斷 -> verify: `uv run pytest tests/test_pipeline_due.py`
- [ ] 遷移：breakers、runs -> verify: `uv run alembic upgrade head` 與 `\d breakers`、`\d runs`
- [ ] process_source 與 finish_daily_run -> verify: 放 3 個來源的工作，`uv run rq worker -w rq.worker.SpawnWorker --burst --with-scheduler` 跑完，貼出結果與收尾工作的輸出
- [ ] 暫時性錯誤會重試 -> verify: 放一件抓 `http://127.0.0.1:9/`（本機沒有服務、一定連不上）的工作，貼出它 1 分鐘後重跑的紀錄
- [ ] 斷路器 -> verify: 用指令打開斷路器，跑一個內容有變的來源，貼出「跳過 AI」；恢復後再跑，貼出有抽取

### 4. 排程與補跑（ADR-057）

- [ ] tick：沒網路就等、今天開始過就不再開始、只放到期的來源 -> verify: 手動執行 tick 兩次，貼出第二次沒有重複放工作
- [ ] rq cron 設定 -> verify: `uv run rq cron app.features.pipeline.schedule` 啟動，貼出它馬上放了一次 tick

### 5. 登入後自動啟動（ADR-061）

- [ ] docker-compose 加自動重啟 -> verify: `docker inspect` 顯示 restart=unless-stopped
- [ ] launchd 安裝與移除 -> verify: `launchctl list | grep scholarship` 與日誌
- [ ] 登出再登入後自動跑 -> verify: 你登出再登入一次後，貼出日誌裡的 tick 與當天的檢查

### 6. 收尾

- [ ] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

## 執行時發現

（實作與實跑中遇到的事）
