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
3. 新增 `backend/app/core/prompts.py`：`load(name, version) -> str`，讀 `backend/prompts/<name>/<version>.md`；版本不存在就丟錯誤
4. 一個一個搬：`extract-12` → `prompts/extract/12.md`，其他依此類推；程式改成載入。原本的版本號常數保留，因為它是快取鍵
5. 跑完整測試，貼結果（重構後）

### 段 2 費用紀錄與每月上限

1. `llm_calls` 資料表與遷移
2. 用量回呼介面；Gemini 轉接頭在呼叫前後叫它
3. 寫資料庫的實作：
   - 呼叫前：查本月（台灣時間的月份）總額，加上的話超過上限，就打開斷路器、丟錯誤
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
| agent 迴圈的停止條件與錯誤處理 | `tests/test_agent_loop.py` | `features/discovery/agent.py` |
| 三種工具 | `tests/test_agent_tools.py` | `features/discovery/tools.py` |
| 假個資不會送出去 | `tests/test_agent_privacy.py` | `features/discovery/` |
| 全文 30 天清理 | `tests/test_trace_cleanup.py` | `features/discovery/` |
| 候選規則、每週上限、自動停用 | `tests/test_candidates.py` | `features/discovery/candidates.py` |
| 每週摘要訊息 | `tests/test_pipeline_messages.py` | `features/pipeline/report.py` |
| 大學名單與每批挑選 | `tests/test_universities.py` | `features/discovery/universities.py` |
| 同一學程檢查與換網址 | `tests/test_new_url.py` | `features/discovery/new_url.py` |
| 設定 API（門檻、上限範圍、停用來源） | `tests/test_settings_api.py` | `features/settings/api.py` |
| 紀錄 API | `tests/test_costs_api.py` | `features/costs/api.py` |

## 完成標準

### 段 1
- [ ] 重構前完整測試全過 -> verify: `cd backend && uv run pytest -q`
- [ ] 12 個提示詞依名稱與版本載入，文字雜湊和搬之前相同 -> verify: `cd backend && uv run pytest tests/test_prompts.py -q`
- [ ] 版本不存在時丟錯誤 -> verify: `cd backend && uv run pytest tests/test_prompts.py -q`
- [ ] 重構後完整檢查全過 -> verify: `cd backend && uv run pytest && uv run ruff check . && uv run mypy app`

### 段 2
- [ ] 一次呼叫的費用依 tokens 與價格算對 -> verify: `cd backend && uv run pytest tests/test_costs.py -q`
- [ ] 本月總額以台灣時間的月份計算 -> verify: `cd backend && uv run pytest tests/test_costs.py -q`
- [ ] 加上這次會超過上限時，呼叫前就擋下、打開斷路器 -> verify: `cd backend && uv run pytest tests/test_costs.py -q`
- [ ] 成功與失敗的呼叫都寫進 `llm_calls` -> verify: `cd backend && uv run pytest tests/test_costs_db.py -q`
- [ ] `costs` 指令印出本月總額與依功能分 -> verify: `cd backend && uv run python -m app.features.costs`
- [ ] 每日報告多一行今日 AI 費用 -> verify: `cd backend && uv run pytest tests/test_pipeline_messages.py -q`

### 段 3
- [ ] Gemini 3.5 Flash-Lite 的函式呼叫實際可用 -> verify: `cd backend && uv run python -m app.features.discovery.agent --smoke --max-cost 1`
- [ ] AI 說完成時迴圈停止 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
- [ ] 步數到上限時停止並記下結果 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
- [ ] 不存在的工具與工具出錯都變成工具結果，不讓程式當掉 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
- [ ] 費用到上限時停止 -> verify: `cd backend && uv run pytest tests/test_agent_loop.py -q`
- [ ] `submit` 拒收這次沒看過的網址 -> verify: `cd backend && uv run pytest tests/test_agent_tools.py -q`
- [ ] `read_page` 截斷文字並列出連結 -> verify: `cd backend && uv run pytest tests/test_agent_tools.py -q`
- [ ] `search` 超過每月次數上限就回報錯誤 -> verify: `cd backend && uv run pytest tests/test_agent_tools.py -q`
- [ ] 假國籍與假姓名的記號不出現在送給 AI 與 Tavily 的文字裡 -> verify: `cd backend && uv run pytest tests/test_agent_privacy.py -q`
- [ ] 超過 30 天的全文被清掉，數字與摘要保留 -> verify: `cd backend && uv run pytest tests/test_trace_cleanup.py -q`
- [ ] 每一步都寫進 `agent_steps`，trace 指令照順序印出 -> verify: `cd backend && uv run python -m app.features.discovery.trace <smoke 的 agent_run_id>`
- [ ] commit 假金鑰會被 gitleaks 擋下 -> verify: `cd "$(mktemp -d)" && git init -q && printf 'GOOGLE_API_KEY=AIzaSyA1234567890abcdefghijklmnopqrstuv\n' > leak.env && git add leak.env && gitleaks git --pre-commit --staged .; echo "exit=$?"`（預期 exit 不是 0）

### 段 4
- [ ] 四條規則全部符合才加入，否則標成已排除並記下原因 -> verify: `cd backend && uv run pytest tests/test_candidates.py -q`
- [ ] 已排除的網址再次提交會直接略過 -> verify: `cd backend && uv run pytest tests/test_candidates.py -q`
- [ ] 超過每週候選上限的提交留到下週 -> verify: `cd backend && uv run pytest tests/test_candidates.py -q`
- [ ] 連續 3 次抽不到有效獎學金就自動停用 -> verify: `cd backend && uv run pytest tests/test_candidates.py -q`
- [ ] 每週摘要列出加入、排除、停用 -> verify: `cd backend && uv run pytest tests/test_pipeline_messages.py -q`

### 段 5
- [ ] 大學名單從官方出處建立，每個名單記下出處 -> verify: `cd backend && uv run pytest tests/test_universities.py -q`
- [ ] 每批只挑還沒找過、或超過一年沒找的學校 -> verify: `cd backend && uv run pytest tests/test_universities.py -q`
- [ ] 新網頁找得到學程名稱和主辦單位才換網址，並重設抓不到的狀態 -> verify: `cd backend && uv run pytest tests/test_new_url.py -q`
- [ ] 對不上就不換，只通知 -> verify: `cd backend && uv run pytest tests/test_new_url.py -q`
- [ ] 實跑：逐校找 10 所、搜尋補漏 1 次、找新網址 1 次，貼出提交、加入、排除數與費用 -> verify: `cd backend && uv run python -m app.features.discovery.run --universities 10 --search --new-urls 1 --max-cost 20`

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
2. 提示詞檔放在 `backend/prompts/<名稱>/<版本號>.md`，名稱用現在版本號的前半，例如 `extract-12` → `prompts/extract/12.md`；變數照舊用 `{name}` 這種寫法
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
