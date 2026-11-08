# 第 10 天：發掘 agent、費用紀錄與設定頁

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 直接推 main）。段 1 是重構（只走 Gate 1、3，前後各貼一次完整測試結果）。

目標：做完之後，

- 每次 AI 呼叫都有紀錄，看得到本月花多少、哪個功能最花錢；超過每月上限，AI 步驟自動暫停並通知你
- agent 每週自己去英國與北歐大學的網站找碩士獎學金頁，也用搜尋找大學以外的獎學金；夠格的來源自動加入每日檢查，每週用 Telegram 告訴你加了哪些
- 抓不到的來源，由 agent 去找現在的官方網址，確認是同一個學程才換
- 網頁有設定頁（通知門檻、每月上限、斷路器、agent 加的來源可以停用）和紀錄頁（費用、agent 每一步）

## 本計畫依據的決定

- 新來源自動評分、自動加入，每週摘要（ADR-078）
- 抓不到的來源由 agent 找新網址（ADR-080）
- agent 迴圈自己寫，用 Gemini 的函式呼叫，在 RQ 工作裡跑（ADR-082）
- 擴大來源：逐校找＋搜尋補漏，範圍是歐洲碩士、英國與北歐優先（ADR-083）
- 提示注入防護：只有搜尋、讀網頁、提交三種工具，看不到個人資料（ADR-084）
- 搜尋用 Tavily 免費方案（ADR-085）
- 觀測用自己的資料表；每次呼叫記一筆、agent 步驟存全文 30 天、呼叫前檢查每月上限（ADR-086、089）
- 個資與金鑰：假個資測試＋commit 前秘密掃描（ADR-087）
- 提示詞放檔案，一版一檔（ADR-088）
- 每月 AI 費用上限 NT$7,000，超過就暫停並通知（ADR-013、049），和現有斷路器共用（ADR-056）
- 模型存取仍經過 core/llm 的 LangChain 轉接頭（ADR-010）；迴圈本身是我們的程式

## 分六段做（會超過一天）

| 段 | 內容 | 做完就有 | 估計 |
| --- | --- | --- | --- |
| 1 提示詞搬到檔案（重構） | 12 個提示詞照原版本號搬到 `prompts/`，文字一字不差 | 提示詞可以並排比較；agent 的提示詞有地方放 | 約 2 小時 |
| 2 費用紀錄與每月上限 | 每次 AI 呼叫記一筆、呼叫前檢查本月總額、`costs` 指令 | 知道錢花在哪；上限真的會擋 | 約半天 |
| 3 agent 核心 | 迴圈、三種工具、步驟紀錄與 30 天清理、假個資測試、秘密掃描 | 一個能跑、會停、有紀錄的 agent | 約 1 天 |
| 4 候選評分與自動加入 | 規則評分、每週上限、連續抽不到就停用、每週摘要 | agent 提交的東西有把關 | 約半天 |
| 5 三種任務 | 大學名單與逐校找、搜尋補漏、找新網址 | 來源真的變多；抓不到的來源有機會修好 | 約 1 天＋背景執行 |
| 6 網頁 | 設定頁、紀錄頁 | 在網頁調門檻與上限、停用來源、看 agent 做了什麼 | 約半天到 1 天 |

每段做完：跑完整檢查、推 main、寫學習卡（`docs/learning/day-10.md`）。

## 設計草圖

### 資料表（新增或修改，每段用自己的 Alembic 遷移，讀過再套用）

- `llm_calls`（段 2）：每次 AI 呼叫一筆。時間、功能（例如 `extract`、`score`、`agent:search`）、提示詞名稱與版本、模型、輸入與輸出 tokens、費用（美元）、成功或錯誤種類；可連到 `runs`、`sources`、`agent_runs`（都可以空）
- `agent_runs`（段 3）：每次 agent 執行一筆。任務種類、目標（學校或來源，可以空）、開始與結束時間、結果（提交了、沒找到、步數到上限、費用到上限、出錯）、步數、費用
- `agent_steps`（段 3）：每一步一筆。第幾步、種類（AI 回覆或工具）、工具名稱、參數（JSONB）、一句話摘要、全文（AI 完整回覆或工具結果，30 天後清成空白）、tokens
- `universities`（段 5）：學校名稱、國家、首頁、名單出處、上次找的時間、上次的結果
- `sources`（段 4、5）：
  - 狀態多一個「已排除」：被規則擋掉的網址留著，agent 下次提交同一個網址就直接略過
  - 新增「連續抽不到有效獎學金的次數」
  - 新增「由哪次 agent 執行提交」
- `app_settings`（段 6）：通知門檻、每月上限（新台幣），帶 `user_id`

### 介面

- core/llm 多一個「工具呼叫」的插座：給它對話紀錄和工具清單，回傳 AI 的文字、要呼叫的工具與參數、tokens。Gemini 轉接頭用 LangChain 實作，功能程式只依賴插座
- core/llm 多一個「用量回呼」介面，轉接頭在每次呼叫前後各叫一次：
  - 呼叫前：檢查上限，超過就丟錯誤、不呼叫
  - 呼叫後：記錄 tokens
  - 寫資料庫的實作放在 features，core 不碰資料庫
- agent 的工具（`features/discovery/tools.py`）：
  - `search(query)`：Tavily，回傳標題、網址、摘要
  - `read_page(url)`：用現有的 core/fetch 抓取（遵守 robots.txt、每站限速、被擋就停，ADR-028），回傳可見文字（截斷）和頁面上的連結清單（截斷）
  - `submit(url, reason)`：提交候選來源或新網址
- 迴圈（`features/discovery/agent.py`）：AI 回覆 → 有工具呼叫就執行並把結果交回 → 直到 AI 說完成、步數或費用到上限。每一步寫進 `agent_steps`

### 邊界情況

- AI 編造網址：`submit` 只收這次執行中真的出現過的網址，也就是搜尋結果或讀過的頁面上的連結。做法和現有的挑連結（`pick.py`）一樣
- AI 呼叫不存在的工具或參數格式錯：把錯誤當成工具結果交回 AI，不讓程式當掉；算一步
- 工具出錯（網站連不到、被擋、Tavily 額度用完）：同上，結果寫明原因；額度用完時這次執行直接結束
- 跑到一半超過每月上限：下一次 AI 呼叫前就停，打開斷路器並通知（和現有費用斷路器同一套）
- 提示注入（ADR-084）：網頁原文會進到 agent 的對話；agent 沒有改資料庫或讀個資的工具，提交的東西還要過段 4 的規則
- 換錯網址：段 5 換網址前，程式確認學程名稱和主辦單位出現在新網頁上，對不上就不換、只通知
- 同一個網址重複提交：`sources.url` 唯一限制擋住；已排除的網址直接略過
- 重複執行（RQ 冪等）：同一個學校、同一週的搜尋任務、同一個來源同一週的找新網址，已經跑過就不再跑

### 不做（這次範圍外）

- 評估資料集與模型比較（#30，第 11 天前決定）
- 持續整合（#42）
- Phoenix、LangSmith 等外部追蹤服務（ADR-086）
- 登入、雲端部署（公開版）
- 英國與北歐以外的大學名單；研究實習等非碩士獎學金（ADR-083）

## 步驟

### 段 1 提示詞搬到檔案（重構）

1. 先跑完整測試，貼結果（重構前）
2. 新增 pin 測試並單獨 commit：記下 12 個提示詞目前文字的雜湊，測試「依名稱與版本載入的文字，雜湊等於原本的」。它一開始會因為載入函式不存在而失敗，這是預期的；搬完才會通過
3. 新增 `backend/app/core/prompts.py`：`load(version) -> str`，例如 `load("extract-12")` 讀 `backend/prompts/extract/12.md`；版本不存在就丟錯誤（實作時改成只傳版本號：版本號常數本來就存在，檔名直接由它決定，兩者不會對不上）
4. 一個一個搬：`extract-12` → `prompts/extract/12.md`，其他依此類推；程式改成載入。原本的版本號常數保留，因為它是快取鍵
5. 跑完整測試，貼結果（重構後）

### 段 2 費用紀錄與每月上限

1. `llm_calls` 資料表與遷移
2. 用量回呼介面；Gemini 轉接頭在呼叫前後叫它
3. 寫資料庫的實作：
   - 呼叫前：查本月（台灣時間的月份）總額，達到上限就丟 `MonthlyCapError`（它是現有的 `CostLimitError`，背景工作遇到會打開斷路器並通知）
   - 呼叫後：寫一筆紀錄，包括失敗的呼叫
4. 現有指令與 RQ 工作改成都帶這個回呼，每個呼叫都標上功能名稱
5. `uv run python -m app.features.costs`：印出本月總額、依功能分、最近 7 天每天的總額
6. 每日報告多一行：今天 AI 花了多少

### 段 3 agent 核心

1. core/llm 的工具呼叫插座與 Gemini 實作；用一個真的小呼叫確認 Gemini 3.5 Flash-Lite 的函式呼叫可以用（`--max-cost 1`）
2. `agent_runs`、`agent_steps` 資料表與遷移
3. 迴圈，用假的 LLM 照劇本回覆來測試：
   - 完成就停
   - 步數上限
   - 不存在的工具
   - 工具出錯
   - 費用上限
4. 三種工具，各自用假的回應測試：
   - `submit` 只收看過的網址
   - `read_page` 截斷並列出連結
   - `search` 每月次數上限
5. 假個資測試（ADR-087）：用帶記號的假國籍和假姓名跑 agent，檢查送給 AI 和 Tavily 的所有文字都沒有這些記號
6. 每天跑完時，清掉超過 30 天的 `agent_steps.全文`，數字與摘要留著
7. 秘密掃描（ADR-087）：用 Homebrew 安裝 gitleaks（安裝前會先問你），hook 放在 repo 的 `.githooks/pre-commit`，用 `git config core.hooksPath .githooks` 啟用；用一個假金鑰確認會被擋
8. 指令 `uv run python -m app.features.discovery.trace <agent_run_id>`：照順序印出某次執行的每一步

### 段 4 候選評分與自動加入

1. agent 提交 → 建立候選來源 → 照現有流程抓取、抽取、核對引用
2. 規則評分，不另外呼叫 AI：
   - 留學國家在歐洲
   - 至少一筆獎學金通過核對
   - 國籍規定沒有明確排除台灣
   - 申請期是最近兩個入學年度，或沒寫

   全部符合就加入每日檢查，否則標成已排除並記下原因
3. 每週候選上限：超過的提交留到下週
4. 連續 3 次抽不到有效獎學金的來源自動停用
5. 每週 Telegram 摘要：加入了哪些（名稱＋網址）、排除幾個與原因、停用了哪些；網頁設定頁可以停用

### 段 5 三種任務

1. 大學名單：英國與北歐（瑞典、芬蘭、丹麥、挪威、冰島）。從各國官方的高等教育機構名單建立，存成種子（ADR-026）。實作時先查證每個名單的官方出處；查不到可下載的官方名單，就回報給你，不自己編
2. 逐校找：agent 從學校首頁出發，找「國際碩士生獎學金」相關頁面，最多提交 3 頁。每天跑完日常檢查後處理一批還沒找過的學校；全部找過一輪後，每所學校每年重找一次
3. 搜尋補漏：每週一次。agent 的輸入只有範圍（英國、北歐、其他歐洲國家、碩士）和 `applicant_text`（科系、想讀的領域），自己想搜尋字，找大學以外的獎學金（政府、駐台辦事處、基金會）
4. 找新網址：被標成抓不到的來源（ADR-080），每 7 天一次。agent 拿到學程名稱、主辦單位、舊網址，提交新網址。程式確認新網頁上找得到學程名稱或縮寫和主辦單位：對得上就換網址、照常抓取與核對，並通知你；對不上就不換，只通知
5. 先在背景跑一次真的：逐校找 10 所學校、搜尋補漏一次、找新網址一次。貼出提交數、加入數、排除數與費用

### 段 6 網頁

1. `app_settings` 資料表與 API：通知門檻（0–100）、每月上限（1–7,000 新台幣，不能超過 ADR-049 的上限）
2. 斷路器狀態與「恢復」按鈕（API 呼叫現有的 reset）
3. agent 加的來源列表：名稱、網址、加入時間、目前的獎學金數；可以停用
4. 紀錄頁：本月總額、依功能分、最近的 agent 執行；點進去看每一步（30 天內有全文）
5. `npm run gen:api`、`npm run build`；用瀏覽器確認畫面（截圖不含評分理由與個資，依記憶裡的規則）

### 文件

- `docs/spec.md`：「候選來源經使用者核准才加入」改成自動加入（ADR-078）
- `docs/adr.md` 的 #27 筆記：標成已由 ADR-078、082、083 決定
- `docs/progress.md`：每段做完更新

## 測試與檔案

| 行為 | 測試檔 | 對象 |
| --- | --- | --- |
| 提示詞搬過去文字不變 | `tests/test_prompts.py` | `core/prompts.py` |
| 費用計算、本月總額、呼叫前擋上限 | `tests/test_costs.py` | `features/costs/` |
| 呼叫紀錄真的寫進資料庫（交易回滾） | `tests/test_costs_db.py` | `features/costs/` |
| 轉接頭的工具呼叫 | `tests/test_llm_tools.py` | `core/llm/gemini.py` |
| agent 迴圈的停止條件與錯誤處理 | `tests/test_agent_loop.py` | `features/discovery/agent.py` |
| 一次執行的紀錄（結果、步數、費用） | `tests/test_agent_runner_db.py` | `features/discovery/runner.py` |
| Tavily、讀網頁、本月搜尋次數 | `tests/test_agent_services.py` | `features/discovery/services.py` |
| 三種工具 | `tests/test_agent_tools.py` | `features/discovery/tools.py` |
| 假個資不會送出去 | `tests/test_agent_privacy.py` | `features/discovery/` |
| 每一步的紀錄與全文 30 天清理 | `tests/test_agent_trace_db.py` | `features/discovery/trace.py` |
| 候選規則、每週上限、自動停用 | `tests/test_candidates.py` | `features/discovery/candidates.py` |
| 候選進出資料庫、排進每天的檢查、每週摘要 | `tests/test_candidates_db.py` | `features/discovery/intake.py` |
| 每週摘要訊息 | `tests/test_pipeline_messages.py` | `features/pipeline/report.py` |
| 大學名單與每批挑選 | `tests/test_universities.py` | `features/discovery/universities.py` |
| 同一學程檢查與換網址 | `tests/test_new_url.py` | `features/discovery/new_url.py` |
| 三種任務、每天的發掘串接 | `tests/test_discovery_run_db.py` | `features/discovery/run.py` |
| 重試沒用的錯誤當天直接算失敗（ADR-094） | `tests/test_pipeline_errors.py`、`tests/test_pipeline_outcomes.py` | `features/pipeline/errors.py`、`jobs.py` |
| 設定 API（門檻、上限範圍、停用來源） | `tests/test_settings_api.py` | `features/settings/api.py` |
| 紀錄 API | `tests/test_costs_api.py` | `features/costs/api.py` |

## 完成標準

### 段 1（11-08 完成）
- [x] 重構前完整測試全過 -> verify: `cd backend && uv run pytest -q`
  ```
  195 passed, 1 warning in 1.21s
  ```
- [x] 12 個提示詞依名稱與版本載入，文字雜湊和搬之前相同 -> verify: `cd backend && uv run pytest tests/test_prompts.py -q`
- [x] 版本不存在時丟錯誤 -> verify: `cd backend && uv run pytest tests/test_prompts.py -q`
  ```
  紅（92347e6）：14 failed in 0.39s（12 個雜湊不同、模組沒用檔案、DID NOT RAISE）
  綠（c4a1798）：14 passed in 0.36s
  ```
- [x] 重構後完整檢查全過 -> verify: `cd backend && uv run pytest && uv run ruff check . && uv run mypy app`
  ```
  209 passed, 1 warning in 1.09s
  All checks passed!
  Success: no issues found in 93 source files
  ```

### 段 2（11-08 完成）
- [x] 一次呼叫的費用依 tokens 與價格算對 -> verify: `cd backend && uv run pytest tests/test_llm_hook.py -q`
  ```
  紅（ec73125 骨架後）：4 failed（after_call 沒被叫、DID NOT RAISE）
  綠（3ce7ee5）：4 passed in 0.22s
  ```
- [x] 本月總額以台灣時間的月份計算 -> verify: `cd backend && uv run pytest tests/test_costs.py -q`
  ```
  紅：2 failed in 0.02s　綠（40b42da）：2 passed in 0.01s
  ```
- [x] 本月總額達到上限時，下一次呼叫前就擋下；背景工作遇到會打開斷路器 -> verify: `cd backend && uv run pytest tests/test_costs_db.py -q`
  ```
  紅（447158d）：assert 0.0 == 1.0　綠（3ee05e6）：2 passed in 0.33s
  ```
- [x] 成功與失敗的呼叫都寫進 `llm_calls`，並認出提示詞版本 -> verify: `cd backend && uv run pytest tests/test_costs_db.py tests/test_prompts.py -q`
  ```
  紅（c4bfd2f）：assert [] == [('links', 'l...imeoutError')]　綠（558da53）：1 passed
  identify 紅（d4203f6）：assert None == 'links-1'　綠（b7fd352）：15 passed
  實測（b85bc91）：一次 ask 寫入 route route-2 324/87 tokens、answer answer-2 2122/66 tokens
  ```
- [x] `costs` 指令印出本月總額與依功能分 -> verify: `cd backend && uv run python -m app.features.costs`
  ```
  本月 AI 費用：約 NT$0.04（上限 NT$7,000）
  依功能（本月）：answer 1 次、route 1 次
  最近 7 天（台灣日期）：11-08  約 NT$0.04
  ```
- [x] 每日報告多一行今日 AI 費用 -> verify: `cd backend && uv run pytest tests/test_pipeline_messages.py -q`
  ```
  紅（d2c5a91）：assert ['這輪產生 1 則通知'] == [...]　綠（4da0688）：6 passed
  真的資料庫上跑一次：「AI 費用：今天約 NT$0.04，本月約 NT$0（上限 NT$7,000）」
  完整檢查：220 passed；ruff、mypy 無問題
  ```

### 段 3（11-08 完成）
- [x] Gemini 3.5 Flash-Lite 的函式呼叫實際可用 -> verify: `cd backend && uv run python -m app.features.discovery.runner --smoke --max-cost 1`
  ```
  agent_runs #23：done，4 步，約 NT$0.18
  提交： ['https://www.lunduniversity.lu.se/study/admission-degree-studies/scholarships-and-awards/lund-university-global-scholarship']
  llm_calls：agent-smoke-1 共 4 筆，都連到 agent_run 23
  ```
- [x] 轉接頭把對話轉成 Gemini 的格式、回傳工具呼叫 -> verify: `cd backend && uv run pytest tests/test_llm_tools.py -q`
  ```
  紅（ed3aef7）：2 failed　綠（5adef5d）：2 passed
  ```
- [x] AI 說完成時迴圈停止 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
- [x] 步數到上限時停止並記下結果 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
- [x] 不存在的工具與工具出錯都變成工具結果，不讓程式當掉 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
- [x] 費用到上限時停止 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
  ```
  紅（6d072be）：5 failed in 0.03s　綠（e68b07d）：5 passed in 0.01s
  ```
- [x] `submit` 拒收這次沒看過的網址 -> verify: `cd backend && uv run pytest tests/test_agent_tools.py -q`
- [x] `read_page` 截斷文字並列出連結 -> verify: `cd backend && uv run pytest tests/test_agent_tools.py -q`
- [x] `search` 超過每月次數上限就回報錯誤 -> verify: `cd backend && uv run pytest tests/test_agent_tools.py tests/test_agent_services.py -q`
  ```
  工具 紅（9861ed2）：7 failed　綠（d022b82）：7 passed
  Tavily、讀網頁、本月次數 紅（1068787 骨架後）：6 failed　綠（b4a7903）：6 passed
  ```
- [x] 假國籍與假姓名的記號不出現在送給 AI 與 Tavily 的文字裡 -> verify: `cd backend && uv run pytest tests/test_agent_privacy.py -q`
  ```
  紅：assert ('Computer Science' in '')　綠（fcf217c）：1 passed
  ```
- [x] 超過 30 天的全文被清掉，數字與摘要保留 -> verify: `cd backend && uv run pytest tests/test_agent_trace_db.py -q`
  ```
  紅（c4ec56b）：2 failed　綠（4b0413a）：2 passed
  ```
- [x] 每一步都寫進 `agent_steps`，trace 指令照順序印出 -> verify: `cd backend && uv run python -m app.features.discovery.trace 23`
  ```
  #23 smoke ：done，4 步，約 US$0.0056
    1 model [tokens 466/18]  呼叫 search(...)
    1 tool  search {"query": "Lund University Global Scholarship"}
    2 model  呼叫 read_page(...)　3 model  呼叫 submit(...)　4 model（結束）
  執行紀錄（結果、步數、費用，出錯記成 error）：tests/test_agent_runner_db.py 2 passed（紅 e8c4336、綠 b042f81）
  ```
- [x] commit 假金鑰會被 gitleaks 擋下 -> verify: `cd "$(mktemp -d)" && git init -q && printf 'GOOGLE_API_KEY=AIzaSyA1234567890abcdefghijklmnopqrstuv\n' > leak.env && git add leak.env && gitleaks git --pre-commit --staged .; echo "exit=$?"`（預期 exit 不是 0）（假金鑰，只用來測試；gitleaks:allow）
  ```
  暫存 repo 裡 commit 假金鑰：leaks found: 1，commit 沒有建立；一般檔案照常 commit
  整個 git 歷史 691 個 commit：唯一的發現是這一行的假金鑰（已加 gitleaks:allow）
  完整檢查：245 passed；ruff、mypy 無問題
  ```

### 段 4（11-08 完成）
- [x] 四條規則全部符合才加入，否則標成已排除並記下原因 -> verify: `cd backend && uv run pytest tests/test_candidates.py tests/test_candidates_db.py -q`
  ```
  規則 紅（c0989c5）：3 failed, 2 passed（通過的兩個是「好的或沒寫的資料不排除」，空骨架本來就符合）　綠（f18009e）：5 passed
  資料庫 紅（8b5b32e）：AssertionError: 提交應該變成一筆候選來源　綠（5e36192）：4 passed
  ```
- [x] 已排除的網址再次提交會直接略過 -> verify: `cd backend && uv run pytest tests/test_candidates_db.py -q`
- [x] 超過每週候選上限的提交留到下週 -> verify: `cd backend && uv run pytest tests/test_candidates_db.py -q`
- [x] 連續 3 次抽不到有效獎學金就自動停用 -> verify: `cd backend && uv run pytest tests/test_candidates_db.py -q`
- [x] 候選排進每天的檢查，抽完後決定；agent 加的來源每次真的重抽都檢查品質 -> verify: `cd backend && uv run pytest tests/test_candidates_db.py -q`
  ```
  紅（22186c3）：assert 4871 in [16, 29, 30, ...]　綠（4bfab4b）：5 passed
  ```
- [x] 每週摘要列出加入、排除、停用 -> verify: `cd backend && uv run pytest tests/test_pipeline_messages.py tests/test_candidates_db.py -q`
  ```
  訊息 紅（0b042d3）：assert '' == '本週新來源：加入 12、排除 3、停用 1'　綠（de16bce）：7 passed
  每週一次 紅（7d821b1）：assert False is True　綠（096ffe1）：6 passed
  真的資料庫上跑收尾新增的兩行：清掉的全文 0、加了每週摘要 False（還沒有 agent 來源）、今天到期的來源 16
  完整檢查：260 passed；ruff、mypy 無問題
  ```

### 段 5（11-09 完成）
- [x] 大學名單從官方出處建立，每個名單記下出處 -> verify: `cd backend && uv run pytest tests/test_universities.py -q`
  ```
  紅（967ea63）：assert 0 == 2　綠（ecc50af）：2 passed
  種子（44457b8）：320 所，英國 187（England 156、Scotland 18、Wales 8、NI 5）、瑞典 42、芬蘭 35、挪威 35、丹麥 16、冰島 5
  載入：種子 320 所，新增 320 所
  ```
- [x] 每批只挑還沒找過、或超過一年沒找的 -> verify: `cd backend && uv run pytest tests/test_universities.py -q`
- [x] 新網頁找得到學程名稱和主辦單位才換網址，並重設抓不到的狀態 -> verify: `cd backend && uv run pytest tests/test_new_url.py -q`
- [x] 對不上就不換，只通知 -> verify: `cd backend && uv run pytest tests/test_new_url.py -q`
  ```
  同一學程 紅（482e161 前）：3 failed　綠（482e161）：4 passed
  換網址 紅：assert False is True（測試欄位名稱經使用者同意修正 d2a2cde）　綠（8070d02）：6 passed
  實跑發現的兩個 bug：長名稱（紅 9aef484、綠 be6e82c）、結尾的 /（紅 19474ac、綠 4bb3a65）
  目錄已有新網址就停用舊來源（ADR-095）：紅 d110934、綠 ac45024；通知 紅 1a2d078、綠 79d0c51
  現在：9 passed
  ```
- [x] 三種任務寫回結果、搜尋每週一次、找新網址每 7 天一次、出錯跳過但到上限就停 -> verify: `cd backend && uv run pytest tests/test_discovery_run_db.py -q`
  ```
  紅（後於 09923a8）：3 failed　綠（3c1a6f9）：3 passed
  discover 紅（e8ca4bf）：assert (0, 0, None) == (2, 2, None)　綠（4b4055b，mypy 修正 25df8a7）
  現在：7 passed
  ```
- [x] 實跑：逐校找 10 所、搜尋補漏 1 次、找新網址 1 次，貼出提交、加入、排除數與費用 -> verify: `cd backend && uv run python -m app.features.discovery.run --universities 10 --search --new-urls 1 --max-cost 2`
  ```
  11-08 搜尋補漏＋找新網址：搜尋新增候選 8（Chevening、瑞典 SI、法國 Eiffel、義大利外交部、荷蘭 NL Scholarship、Stipendium Hungaricum、DAAD、UPF）；找新網址 SERP 判成對不上（bug，已修），之後套用 ADR-095：#16 停用，「已由 #3801 取代」
  11-09 逐校找 10 所（丹麥）：done 10、新增候選 5、出錯 0，合計 NT$4.39（每所 NT$0.05–1.18）
  提示詞 v2（cc518cf）重試 ITU、RMC：各 5 步，各提交 1 頁（v1 只讀丹麥文首頁就放棄）
  加入或排除：候選會在下一次每日檢查抽取後依四條規則決定
  完整檢查：286 passed；ruff、mypy 無問題
  ```

### 段 6
- [ ] 通知門檻只收 0–100、每月上限只收 1–7,000 -> verify: `cd backend && uv run pytest tests/test_settings_api.py -q`
- [ ] agent 加的來源可以停用 -> verify: `cd backend && uv run pytest tests/test_settings_api.py -q`
- [ ] 紀錄 API 回傳本月總額、依功能分、最近的 agent 執行與步驟 -> verify: `cd backend && uv run pytest tests/test_costs_api.py -q`
- [ ] 前端型別檢查與建置通過 -> verify: `cd frontend && npm run gen:api && npm run build`
- [ ] 設定頁與紀錄頁在瀏覽器正常顯示 -> verify: 瀏覽器開 `http://127.0.0.1:8000/settings` 與 `/logs`，用 read_page 檢查標籤（不截評分理由與個資）

### 全部
- [ ] 完整檢查全過 -> verify: `cd backend && uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] 學習卡寫完（每段一張） -> verify: `ls docs/learning/day-10.md`
- [ ] `docs/progress.md`、`docs/spec.md`、#27 筆記更新 -> verify: `grep -n "ADR-078" docs/spec.md && grep -n "第 10 天" docs/progress.md`

## Claude 自行決定（小問題，請事後檢查）

1. 新功能放在 `features/discovery/`（agent、工具、候選、大學名單、找新網址）、`features/costs/`（費用紀錄）、`features/settings/`（設定）
2. 提示詞檔放在 `backend/prompts/<名稱>/<版本號>.md`，名稱用現在版本號的前半，例如 `extract-12` → `prompts/extract/12.md`；變數照舊用 `{name}` 這種寫法；抽取用的共同規則（原本的 `RULES`）直接寫進 `extract/12.md` 和 `section/12.md`，每個檔案都是完整的提示詞，以後改規則就是兩個檔案各出新版本
3. 「本月」以台灣時間的月份計算，和 `runs.local_date` 一致；匯率照現有程式用 1 美元 = 32 新台幣
4. 費用上限每次呼叫前查一次資料庫的總額，不另外快取；一天幾百次呼叫，查一次很快
5. agent 的上限：逐校找每次最多 15 步、搜尋補漏最多 25 步、找新網址最多 15 步；每次執行最多 NT$2
6. Tavily 每月最多用 800 次（免費 1,000 次，留 200 次餘裕），從 `agent_steps` 計算；每次搜尋只用基本搜尋（1 點）
7. `read_page` 給 AI 的文字最多 20,000 字元、連結最多 150 個；超過的截掉並註明「已截斷」
8. 「一句話摘要」取工具結果或 AI 回覆的前 200 字元；它和工具名稱、參數一起永久保留，30 天後只清全文（ADR-089 說的「數字」包含這些小欄位）
9. 30 天清理在每天的收尾工作裡做，不另外排程
10. 逐校找每天最多 30 所；搜尋補漏的國家用規格的範圍（英國、北歐、其他歐洲國家），不用你個人資料裡「想去的國家」，因為 ADR-087 規定 agent 只拿科系與領域
11. 每週候選上限 50 個；自動停用的門檻是連續 3 次；兩個都是門檻數字，之後可以調
12. 同一學程檢查：新網頁的可見文字裡，要找得到學程名稱或縮寫（不分大小寫、忽略標點）以及主辦單位名稱的其中一個主要字
13. 設定存在資料庫的 `app_settings`（和 ADR-026 把來源設定放資料庫一致）；資料庫還沒有值時，用 `.env` 的預設值（例如現在的 `notify_threshold`）
14. gitleaks 用 Homebrew 安裝；hook 檔放進 git，換電腦時再執行一次 `git config core.hooksPath .githooks`
15. （段 2 實作時）提示詞版本不改呼叫的地方：`prompts.identify` 從送出的文字反查是哪個提示詞（比對提示詞裡固定的文字片段），功能名稱就是提示詞名稱（例如 `extract`）；認不出來記成 `unknown`
16. （段 2 實作時）上限只看「本月總額有沒有達到上限」，不預估這次會花多少，所以最多超過一次呼叫的錢（和 ADR-089 一致）；計畫原本寫「加上這次會超過」，已改
17. （段 2 實作時）所有 Gemini 都由 `costs.gemini()` 建立；每個來源的抽取記下 `source_id`，`run_id` 先不填（工作裡拿不到，紀錄頁先用日期分）
18. （段 2 實作時）嵌入（向量）呼叫不記錄：LangChain 的嵌入介面不回傳 tokens，費用也很小；之後要記再加
19. （段 3 實作時）`read_page` 也只能打開這次看過的網址（任務給的網址、搜尋結果、讀過的頁面上的連結），和 `submit` 一樣，避免 AI 編造網址浪費抓取
20. （段 3 實作時）步數＝呼叫 AI 的次數；一步裡 AI 可能同時呼叫好幾個工具
21. （段 3 實作時）工具說明放在 `prompts/tool-*/1.md`，smoke 任務說明在 `prompts/agent-smoke/1.md`；Tavily 用 httpx 直接呼叫，不另外裝 tavily 套件
22. （段 3 實作時）smoke 指令改成 `python -m app.features.discovery.runner --smoke`（計畫原本寫 `agent --smoke`）
23. （段 4 實作時）「歐洲」的國碼清單：歐盟 27 國、冰島、列支敦斯登、挪威、英國、瑞士，加上阿爾巴尼亞、安道爾、波士尼亞、蒙特內哥羅、北馬其頓、塞爾維亞、摩爾多瓦、烏克蘭、摩納哥、聖馬利諾、梵蒂岡、科索沃、土耳其；放在 `candidates.EUROPE`
24. （段 4 實作時）每週摘要最多列 10 個加入的來源，其餘只寫數量；排除的只統計原因，不逐一列名稱
25. （段 4 實作時）最近 7 天沒有加入、排除、停用時，不送每週摘要
26. （段 4 實作時）候選被網站擋（ADR-028）時，和其他來源一樣標成需人工，不自動排除，也不算進每週上限
27. （段 4 實作時）候選的名稱先用網址，抽出獎學金後換成獎學金名稱；之後每次重抽也跟著更新
28. （段 4 實作時）「有效獎學金」和加入的規則相同：四條規則都過才算；已加入的來源之後變成舊資料或不在歐洲，也會被算成一次抽不到
29. （段 5 實作時）逐校找出錯的學校 7 天後再試，不要每天都排第一個佔名額；正常找完的一年後再找
30. （段 5 實作時）每次執行最多提交：逐校找 3 頁、搜尋補漏 10 個、找新網址 1 個；手動指令的 `--max-cost` 是「每次 agent 執行」的上限（預設 NT$2）
31. （段 5 實作時）找新網址時，agent 提議的網址由程式自己再抓一次，用我們抓到的內容做同一學程檢查，不相信 agent 說的
32. （段 5 實作時）同一學程檢查：完整名稱、破折號後的縮寫，或名稱裡至少 3 個特別字全部出現在網頁上；只差結尾 `/` 的網址算同一個
33. （段 5 實作時）逐校找的提示詞第 2 版：首頁是當地語言就先找英文版，至少看 3 頁才放棄（11-09 實跑丹麥學校發現）
34. （段 5 實作時）大學名單由 `backend/scripts/build_universities.py` 從官方出處建立；冰島 7 所裡農業大學網站跳出驗證碼（不繞過）、Hólar 已併入冰島大學，所以只有 5 所；芬蘭國防大學官方資料沒有網址，不收

## 段 5 實作時的發現（之後處理）

1. 抽取時，同一個來源歷來抓過的每個網址的最新快照都會一起給 AI。換網址之後，舊網站最後一次的快照也還會被一起抽，可能把舊資料混進來
2. 搜尋補漏不知道已經有哪些來源，例如提交了 Chevening 的總頁，而種子已經有 Chevening 台灣頁；靠規則去重（ADR-048）處理，之後可以考慮把已知來源告訴 agent
3. 每天的發掘工作在收尾後才跑，所以 agent 找到的候選要到隔天的每日檢查才會評分
