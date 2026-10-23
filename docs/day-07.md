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
21. 子 agent 查到金鑰無效時 Gemini 常回 400（內容寫 API_KEY_INVALID），不一定是 401；模型名稱打錯回 404。兩種都改成打開斷路器（ADR-056 的「金鑰有問題」）；其他 400 照樣跳過
22. robots.txt 回 5xx 原本當成被擋、永遠標需人工；改成暫時錯誤（TemporaryFetchError），稍後重試，照 RFC 9309 當下仍然不抓。因此卡住的 4 個來源（41、50、110、219）已解除需人工
23. Gemini 的每日額度用完也是 429：不另外分辨，照樣重試。斷路器要手動恢復，用在隔天就自動恢復的額度上反而麻煩；付費方案的每日額度也遠高於我們的用量
24. `matching.top` 先套用 ADR-059 的顯示規則：依時間狀態分組（還能申請 → 時間待確認 → 已截止或不適用），同一組再依分數排；網頁在第 9 天
25. 預估的依據寫在預估申請期的 evidence 欄（例如「依 2025 年的日期推估」）；預估一旦落在過去，cycles 就重新產生
26. 抽取結果沒變、而且已經有段落索引時，不重建索引（避免每天重寫 6,135 段）
27. process_source 回傳 {result, detail}，結果在 Redis 留 2 天，收尾時統計每種結果幾件；收尾的結果存進 runs.counts
28. tick 和來源的工作放在同一個佇列：當天的檢查還在跑時，tick 會排在後面，輪到時只會回「今天已經開始過」，不影響結果
29. 收尾時斷路器打開就不評分；評分本身遇到 AI 錯誤是逐筆記失敗，不會打開斷路器（同樣的錯誤通常會先在抽取時打開）
30. 抓取遇到 5xx 與網路錯誤改成往外丟，背景工作才能重試；手動的 fetch 指令接住後照舊跳過、保留已抓到的頁面
31. 容器的自動重啟用 `docker update` 直接改，避免重建容器打斷正在跑的檢查
32. worker 改用 `OnlineSpawnWorker`（SpawnWorker 加一條規則）：每次拿工作前檢查有沒有網路，沒網路就每 30 秒檢查一次、持續回報還活著，網路回來才拿；這樣沒網路時工作留在佇列，不會白白用掉重試（執行時發現第 8 點）
33. 檢查網路用的網址改成設定值（`online_check_url`，預設 captive.apple.com），測試時可以讓 worker 以為沒網路
34. `launchd install` 重裝時，bootout 之後先等舊的程式真的結束，再重新載入（不然會出現「Bootstrap failed: 5: Input/output error」）

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
def is_due(frequency: Literal["daily", "weekly", "monthly"], last_checked: date | None,
           today: date, recheck_from: date | None = None) -> bool   # 都用台灣日期

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
| test_pipeline_worker.py | 實跑後補：沒網路時先等，網路回來才拿工作 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 評分只算適配度（ADR-059、060）

- [x] C1 國家比對 -> verify: `uv run pytest tests/test_matching_checks.py -k country`

  ```
  2 passed, 6 deselected in 0.03s   ← 另一個是名稱也有 country 的「沒有國家清單」測試
  ```
- [x] C2 改舊的權重測試（自己的 commit，第 18 點） -> verify: `uv run pytest tests/test_matching_checks.py -k weighted`（先紅）

  ```
  E       AssertionError: assert 100.0 == 70.0
  E        +  where 100.0 = <function weighted_total ...>({'field': 10, 'country': 0})
  ```
- [x] C3 新權重與都沒填是 100 分 -> verify: `uv run pytest tests/test_matching_checks.py -k weighted`

  ```
  1 passed, 7 deselected in 0.04s
  ```
- [x] 評分指令：時間不算進上限、提示詞 score-4、加上國家分數；spec 的評分段落改寫 -> verify: `uv run python -m app.features.matching.score --max-cost 10` 貼出結果

  ```
  評分 221 筆（領域契合：AI 沿用 0、重算 221、失敗 0、沒填不評 0）；上限 20：2、上限 80：6、沒有上限：213
  tokens：輸入 39,906、輸出 11,370，約 US$0.040（NT$1.3）
  ```
- [x] 再跑一次評分，全部沿用 -> verify: 貼出「沿用 N、重算 0」

  ```
  評分 221 筆（領域契合：AI 沿用 221、重算 0、失敗 0、沒填不評 0）；上限 20：2、上限 80：6、沒有上限：213
  tokens：輸入 0、輸出 0，約 US$0.000（NT$0.0）
  ```

### 2. 預估的下一屆（ADR-058）

- [x] E1 預估往後推到今天以後 -> verify: `uv run pytest tests/test_cycles.py -k estimate_after`

  ```
  1 passed, 8 deselected in 0.37s
  ```
- [x] E2 超過 24 個月算資料過舊 -> verify: `uv run pytest tests/test_cycles.py -k stale`

  ```
  1 passed, 8 deselected in 0.31s
  ```
- [x] cycles 指令套用 -> verify: `uv run python -m app.features.scholarships.cycles`，再查截止日在過去的預估筆數（應為 0）與資料過舊的筆數

  ```
  這次封存 0 筆、喚回 0 筆、新增預估申請期 5 筆；資料過舊 9 筆
  預估在過去 0、預估在未來 67
  51 MUrCS 2027-02-09 依 2025 年的日期推估｜117 TISE 2027-05-31｜136 2027-02-14｜138 CYBERUS 2027-02-02
  （之後重建一次申請期，讓舊的預估也標上依據：67 / 67 個預估都有註明）
  ```

### 3. 背景工作（ADR-056）

- [x] 加入 rq -> verify: `uv pip show rq | head -2`

  ```
  Name: rq
  Version: 2.12.0
  ```
- [x] P1 錯誤分類 -> verify: `uv run pytest tests/test_pipeline_errors.py`

  ```
  23 passed in 0.40s   ← 子 agent 的 20 個，加上 Claude 補的金鑰無效／模型不存在、robots.txt 暫時讀不到
  ```
- [x] P2 到期判斷 -> verify: `uv run pytest tests/test_pipeline_due.py`

  ```
  8 passed in 0.02s
  ```
- [x] 遷移：breakers、runs -> verify: `uv run alembic upgrade head` 與 `\d breakers`、`\d runs`

  ```
  Running upgrade f64bbe6d16f0 -> d209140c2cbd, breakers and runs   （降級、再升級也跑過）
  breakers: id bigint identity, name varchar(32) unique, opened_at timestamptz, reason text
  runs: id bigint identity, local_date date unique, started_at, finished_at, counts jsonb default '{}'
  ```
- [x] process_source 與 finish_daily_run -> verify: 放 3 個來源的工作，`uv run rq worker -w rq.worker.SpawnWorker --burst --with-scheduler` 跑完，貼出結果與收尾工作的輸出

  ```
  process_source (92,)  {'result': 'unchanged', 'detail': '內容沒變'}
  process_source (179,) {'result': 'unchanged', 'detail': '內容沒變'}
  process_source (55,)  ConnectTimeout → 排程重試（見下一項）；收尾工作等它有最後結果
  收尾（來源 227 那次）：收尾完成：來源 {'extracted': 1}；申請期 {...'stale': 9}；評分 {'scored': 221, 'reused': 220, 'computed': 1, ...}
  ```
- [x] 暫時性錯誤會重試 -> verify: 放一件抓 `http://127.0.0.1:9/`（本機沒有服務、一定連不上）的工作，貼出它 1 分鐘後重跑的紀錄

  ```
  實跑時剛好遇到真的連不上的網站（clide.umk.pl 逾時，同一所大學的 www.umk.pl 正常），就用它驗證：
  14:52:11 process_source(55) → httpx.ConnectTimeout → 分類 retry → 排程中
  14:53:55 process_source(55) 重跑（約 1 分鐘後）→ 又逾時 → 排程中，剩下重試次數 1
  另外用本機假網站確認抓取會把錯誤丟出去：robots.txt 回 503 → TemporaryFetchError → retry；網頁回 503 → HTTPStatusError → retry；連 127.0.0.1:9 → ConnectError → retry；三種都沒有被標需人工
  ```
- [x] 斷路器 -> verify: 用指令打開斷路器，跑一個內容有變的來源，貼出「跳過 AI」；恢復後再跑，貼出有抽取

  ```
  斷路器打開中（2026-10-23 06:55 UTC）：測試：手動打開，驗證會跳過 AI
  來源 227： {'result': 'fetch_only', 'detail': '斷路器打開中：只抓取，不抽取'}
  收尾：評分 {'skipped': '斷路器打開中'}
  斷路器關著：AI 步驟照常執行
  來源 227： {'result': 'extracted', 'detail': '類別 1、文件 9、窗口 3…'}
  收尾：評分 {'scored': 221, 'reused': 220, 'computed': 1, ...}
  ```

### 4. 排程與補跑（ADR-057）

- [x] tick：沒網路就等、今天開始過就不再開始、只放到期的來源 -> verify: 手動執行 tick 兩次，貼出第二次沒有重複放工作

  ```
  今天（台灣）: 2026-10-23 有網路: True 到期的來源: 160
  1) 今天已經開始過          ← 手動測試留下的紀錄
  （刪掉測試的紀錄）
  2) 開始今天的檢查：160 個來源
  3) 今天已經開始過
  runs: 2 | 2026-10-23 | {"enqueued": 160}；佇列 159 件＋1 件執行中
  ```
- [x] rq cron 設定 -> verify: `uv run rq cron app.features.pipeline.schedule` 啟動，貼出它馬上放了一次 tick

  ```
  14:58:47 Registered 'app.features.pipeline.jobs.tick' to run on default every 900 seconds
  14:58:47 Enqueued job tick to queue default
  ```

### 5. 登入後自動啟動（ADR-061）

- [x] docker-compose 加自動重啟 -> verify: `docker inspect` 顯示 restart=unless-stopped

  ```
  /scholarship-agent-postgres-1 restart=unless-stopped
  /scholarship-agent-redis-1 restart=unless-stopped
  （用 docker update 改執行中的容器，沒有重啟；compose 檔也加上，之後重建一致）
  ```
- [x] launchd 安裝與移除 -> verify: `launchctl list | grep scholarship` 與日誌

  ```
  已安裝並啟動：local.scholarship-agent.worker（~/Library/LaunchAgents/local.scholarship-agent.worker.plist）
  已安裝並啟動：local.scholarship-agent.cron（~/Library/LaunchAgents/local.scholarship-agent.cron.plist）
  local.scholarship-agent.worker：執行中（PID 83540），上次結束代碼 0
  local.scholarship-agent.cron：執行中（PID 83542），上次結束代碼 0
  worker.log: 15:00:11 default: app.features.pipeline.jobs.process_source(12)
  cron.log:   15:00:12 Enqueued job tick to queue default
  ```
- [x] W1 沒網路時 worker 先等、不拿工作（實跑後補，第 32 點） -> verify: `uv run pytest tests/test_pipeline_worker.py`；再開一個以為沒網路的 worker

  ```
  1 passed in 0.78s
  $ ONLINE_CHECK_URL=http://127.0.0.1:9 uv run rq worker -w app.features.pipeline.worker.OnlineSpawnWorker
  21:17:59 *** Listening on default...
  21:17:59 沒有網路：先不拿工作，每 30 秒檢查一次      ← 45 秒內一件都沒拿
  21:18:42 Worker ... warm shut down requested         ← 送出停止訊號，正常結束
  ```
- [x] 登出再登入後自動跑 -> verify: 你登出再登入一次後，貼出日誌裡的 tick 與當天的檢查

  ```
  last：joe console Fri Oct 23 21:11 still logged in（上一次是 10/18 11:12）
  local.scholarship-agent.cron   21:11:31 啟動（PID 91643）
  local.scholarship-agent.worker 21:11:31 啟動（PID 91664）
  scholarship-agent-postgres-1 / redis-1：Up About a minute（Docker Desktop 登入時啟動，AutoStart=true）
  worker.log 21:11:17 could not connect to Redis instance ... retrying in 2 seconds...   ← 登出時 Docker 先停了
  worker.log 21:12:14 Worker ... started with PID 91916 → 21:12:14 process_source(99)    ← 接著做今天剩下的工作
  cron.log   21:12:17 Enqueued job tick to queue default                                ← 登入後馬上放 tick
  ```

### 6. 收尾

- [x] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

  ```
  143 passed in 1.16s
  All checks passed!
  Success: no issues found in 72 source files
  ```

## 執行時發現

1. 評分只算適配度之後，上限 20 的剩 2 筆、上限 80 的 6 筆，213 筆沒有上限；分數多半是 10 的倍數，前幾名常常同分，所以 `matching.top` 先依時間狀態分組（第 24 點）
2. 預估：往後推 5 個申請期（4 筆獎學金，依 2025 年的日期），資料過舊 9 筆（2022–2024 年）；重建一次申請期後，67 個預估都有標推估依據
3. 子 agent 的疑慮：金鑰無效回 400、模型不存在回 404（第 21 點）；每日額度的 429（第 23 點）；robots.txt 5xx 會卡住來源（第 22 點）
4. 實跑時 clide.umk.pl 連不上（同校的 www.umk.pl 正常）：照 ADR-056 在 1 分鐘、5 分鐘、30 分鐘後重試，都失敗才算最後失敗
5. 停止 worker 時，停止訊號也會送到正在做工作的子程序，那件工作被中斷；因為有重試設定，RQ 把它排回去（來源 13，剩 2 次重試）。登出時正在跑的工作也會這樣補做
6. 今天（2026-10-23）到期的來源 160 個（可檢查的 194 個裡，封存而且還沒到每週、每月檢查時間的不算）；SpawnWorker 每件約 15–20 秒，主要是啟動新程序與禮貌的抓取間隔
7. 日誌（worker.log、cron.log）會一直變大，沒有輪替；併入 #32（觀測與追蹤）
8. 電腦睡眠吃掉重試：15:05 網路斷了、15:09 睡著，之後每小時短暫醒來做系統維護（此時沒網路，DNS 也查不到）；worker 照樣拿工作，一拿就失敗，110 件在 5 小時內用完 3 次重試。追一件（來源 119）：15:06 失敗、16:32 重試失敗、19:36 維護喚醒時重試失敗 → 最後失敗。根本原因是「沒網路還拿工作」，不是網站的問題 → 第 32 點。失敗的來源沒有更新檢查時間，隔天會再到期
9. RQ 的「中繼清單」副作用：失敗的工作另外被補記「Job was stuck in intermediate queue」，其中 68 件同時還在佇列裡；冪等所以重跑不會寫錯資料，只是統計看起來比較亂
10. 一輪完整檢查要 1 到 1.5 小時：ADR-028 同一個網站每次請求隔 5 秒、一個來源常有好幾頁，加上每件工作要啟動新程序；之後想加快，可以依網站分組平行跑（和第 3 天的 `--shard` 一樣，保住每個網站的間隔）
11. 登出時 launchd 會停掉 worker，正在做的工作被中斷後會照重試規則補做；Docker 比 worker 先停，worker 會一直重試連 Redis，登入後自己接上
