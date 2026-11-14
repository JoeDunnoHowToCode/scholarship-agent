# 研究 agent 計畫（2026-11-14，ADR-101、102）

狀態：**等使用者核准**。使用者 11-13 選 C（自己規劃的研究 agent），C1 選 B、C1a 選 C、C2 選 C、C3 選 A、C4 選 A、C5 選 A。

## 問題

agent 本來的目的是找到「系統還不知道的」獎學金（ADR-002、083）。現在的搜尋補漏不知道資料庫裡已經有什麼：

- 11-08、11-09 兩次執行搜了 11 次，搜的都是 Chevening、DAAD、Eiffel 這類已知的名字；讀了 1 頁、提交 9 個
- 它每次都從零開始：不記得上週搜過什麼、哪些結果後來被排除

研究 agent 改成：先看資料庫已有什麼、記得以前搜過什麼，再自己決定去找什麼。

## 設計

### 1. 資料庫：唯讀帳號＋專用 schema 的 view（ADR-102）

一個 Alembic 遷移建立以下東西（降版時全部刪掉）：

- **帳號 `agent_reader`**：可以登入，密碼和本機的 `scholar` 一樣寫在預設設定裡（資料庫只綁 127.0.0.1）。帳號層級的設定：
  - `default_transaction_read_only = on`：預設唯讀
  - `statement_timeout = 5s`：查詢最多跑 5 秒
  - `CONNECTION LIMIT 2`
- **schema `agent_read`**：`agent_reader` 只有這個 schema 的 `USAGE` 和裡面 view 的 `SELECT`。`public` 裡的表一張都沒給權限，所以讀不到
- **4 個 view**（只放公開資料，沒有 `user_id`）：

| view | 欄位 | 來自 |
| --- | --- | --- |
| `agent_read.sources` | id、name、url、kind、country、discovery、status、enabled、created_at | `sources` |
| `agent_read.scholarships` | id、name、provider、countries、degrees、fields、amount、nationality_scope、status、source_id、duplicate_of | `scholarships`（不含 `extracted`、向量） |
| `agent_read.searches` | agent_run_id、started_at、query | `agent_steps` 裡 tool = search 的參數（不含 `full_text`，因為任務文字有科系） |
| `agent_read.submissions` | agent_run_id、url、status、review_note | agent 提交後建的 `sources` |

- view 是用 `scholar` 建的，查 view 時用 view 擁有者的權限讀底下的表；所以 `agent_reader` 讀得到 view、讀不到原本的表
- 讀不到的表：`profiles`、`matches`、`events`、`agent_steps`、`llm_calls`、`app_settings` 和其他所有 `public` 的表
- 設定新增 `agent_database_url`，預設 `postgresql+psycopg://agent_reader:agent_reader@localhost:5432/scholar`；CI 用同樣的預設

### 2. 兩個資料庫工具（ADR-102）

放在新檔 `app/features/discovery/db_tools.py`，用 `agent_reader` 的連線，不用主程式的 `SessionLocal`。

**`coverage`（固定查詢，沒有參數）**回傳兩張小表：

- 已加入、啟用中的來源，依國家 × 種類（university、institution、programme…）的數量
- 有效、不重複的獎學金，依國家的數量，和提供者總數

**`query_db(sql)`（自由 SQL）**：

1. 程式先檢查：只能有一句，開頭是 `SELECT` 或 `WITH`。不合格就回一句說明，不送進資料庫（擋掉 `SET statement_timeout = 0` 這類改設定的句子）
2. 在唯讀交易裡執行（`SET TRANSACTION READ ONLY`，和帳號設定重複保護）
3. 最多回 50 筆、4,000 字；超過就截斷並註明
4. 資料庫的錯誤（欄位打錯、權限不足、逾時）變成文字回給模型，和現在的工具錯誤一樣（`_run_tool`），模型自己決定要不要改寫

工具說明照 ADR-088 放在 `prompts/tool-coverage/1.md`、`prompts/tool-query-db/1.md`，`query_db` 的說明列出 4 個 view 的欄位。

### 3. 記憶：放在任務文字（C2 選 C）

執行前由程式讀資料庫，組成任務文字（`tasks.py` 新增 `research_task`）：

- 範圍、學位、年度、科系與領域：和搜尋補漏一樣，個人資料只經過 `applicant_text`（ADR-087）
- **過去的搜尋**：最近 8 週的搜尋補漏與研究執行，每次列出日期、搜尋字、提交的網址和結果（加入／排除＋原因／還是候選）
- **已知的提供者**：不重複的獎學金提供者名稱（11-14 有 191 個）加上 institution 來源的名稱，去重後排序，最多 300 個

### 4. 任務與排程（C3 選 A、C4 選 A）

- 新任務名稱 `research`，系統提示詞 `prompts/agent-research/1.md`：先用 `coverage` 看缺口，需要時用 `query_db`，再搜尋；不要搜已知的提供者；不要重複過去的搜尋字
- 工具：search、read_page、submit、coverage、query_db
- 步數上限 25、每次最多提交 10 個、每次花費上限 NT$2（都和搜尋補漏相同）
- 每週一次：這週（台灣時間 ISO 週）已經有 `research` 執行就略過
- `discover_today` 和指令列的 `--search` 改成跑研究；舊的 `run_search`、`search_task`、`agent-search-1` 程式刪掉，提示詞檔留著（ADR-088：舊版本的檔案留著）
- 網頁的任務名稱加一個 `research: "研究"`；舊的 `search: "搜尋補漏"` 留著，紀錄頁才看得懂舊的執行

### 5. 成效數字（C5 選 A）

新指令 `uv run python -m app.features.discovery.metrics`，每次搜尋補漏與研究執行一行：

| 欄位 | 怎麼算 |
| --- | --- |
| 日期、任務、結果 | `agent_runs` |
| 步數、搜尋次數、SQL 次數 | `agent_steps` 依工具計數 |
| 提交 | 這次執行建的 `sources` 數 |
| 加入、排除、還是候選 | 那些 `sources` 的 status |
| 新網域 | 加入的來源裡，網域在這次執行之前沒出現在任何來源的個數 |
| 費用（NT$） | `agent_runs` 的花費 |

舊的 2 次搜尋補漏也會列出來，當作比較基準。

### 範圍外

- 逐校找、找新網址不改（不給資料庫工具）
- 不判斷找到的獎學金對使用者有沒有用（C5 選 A）
- 不和搜尋補漏並跑（C4 選 A）
- 不改面試文件；計畫完成後再另外改「為什麼用 agent」那段

### 邊界情況

- 資料庫連不上（`agent_reader` 不存在、密碼錯）：工具回錯誤文字，agent 照樣能搜尋；不讓整次執行失敗
- 模型一直寫錯 SQL：每次錯誤都算一步，25 步上限擋住
- 查詢逾時：5 秒後資料庫取消，回「查詢逾時」
- 沒有過去的搜尋：記憶那段寫「還沒有」
- 沒有個人資料：和現在一樣寫「沒有填」

## 費用

- 搜尋補漏 11-08、11-09 兩次：US$0.027、US$0.006（約 NT$0.9、NT$0.2）
- 記憶約多 3,000 tokens，每一步重送；25 步約多 75,000 輸入 tokens，粗估每次多 NT$0.3
- 每週一次，每月約多 NT$1–2；每次上限仍是 NT$2

## 測試

| 行為 | 測試檔 |
| --- | --- |
| `agent_reader` 讀不到個資表、寫不進去 | `tests/test_agent_db_tools_db.py` |
| `coverage` 的數量 | `tests/test_agent_db_tools_db.py` |
| `query_db` 的程式檢查、上限、錯誤變文字 | `tests/test_agent_db_tools.py`（不連資料庫）、`_db.py`（逾時） |
| 記憶的組法 | `tests/test_research_task_db.py` |
| 假個資不出現在研究任務文字 | `tests/test_agent_privacy.py` |
| 研究 agent 的提交要先讀過 | `tests/test_agent_tools.py` |
| 每週一次、`discover` 跑研究 | `tests/test_discovery_run_db.py` |
| 成效數字 | `tests/test_discovery_metrics_db.py` |

## 檢查清單

- [ ] 遷移建立 `agent_reader`、`agent_read` schema 和 4 個 view（讀過自動產生的內容再套用） -> verify: `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
- [ ] `agent_reader` 查 `profiles`、`matches`、`events`、`agent_steps`、`llm_calls` 都是權限不足 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools_db.py -k personal`
- [ ] `agent_reader` 不能寫入 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools_db.py -k read_only`
- [ ] view 裡沒有 `user_id` 和 `full_text` 欄位 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools_db.py -k columns`
- [ ] `query_db` 只收一句 SELECT／WITH，其他回說明、不送資料庫 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools.py -k one_select`
- [ ] `query_db` 最多 50 筆、4,000 字，超過註明截斷 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools.py -k limits`
- [ ] `query_db` 的資料庫錯誤變成文字 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools.py -k error`
- [ ] `query_db` 逾時回「查詢逾時」 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools_db.py -k timeout`
- [ ] `coverage` 依國家 × 種類計數，只算已加入、啟用中的 -> verify: `cd backend && uv run pytest tests/test_agent_db_tools_db.py -k coverage`
- [ ] 任務文字列出最近 8 週的搜尋字與結果 -> verify: `cd backend && uv run pytest tests/test_research_task_db.py -k searches`
- [ ] 任務文字列出已知提供者，去重、最多 300 個 -> verify: `cd backend && uv run pytest tests/test_research_task_db.py -k providers`
- [ ] 假個資（國籍等）不出現在研究任務文字 -> verify: `cd backend && uv run pytest tests/test_agent_privacy.py -k research`
- [ ] 研究 agent 提交沒讀過的頁面會被拒絕；逐校找不受影響 -> verify: `cd backend && uv run pytest tests/test_agent_tools.py -k read_first`
- [ ] 這週已有研究執行就略過 -> verify: `cd backend && uv run pytest tests/test_discovery_run_db.py -k research_weekly`
- [ ] `discover` 跑研究、不再跑搜尋補漏 -> verify: `cd backend && uv run pytest tests/test_discovery_run_db.py -k discover`
- [ ] 成效指令每次執行一行，數字對 -> verify: `cd backend && uv run pytest tests/test_discovery_metrics_db.py`
- [ ] 網頁的任務名稱 -> verify: `cd frontend && npm run build`
- [ ] 完整檢查 -> verify: `cd backend && uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] 實跑一次研究 agent -> verify: `cd backend && uv run python -m app.features.discovery.run --search --max-cost 2`
- [ ] 看成效數字（和舊的 2 次搜尋補漏比） -> verify: `cd backend && uv run python -m app.features.discovery.metrics`
- [ ] 學習卡 `docs/learning/day-12.md`、更新 `docs/progress.md` -> verify: `ls docs/learning/day-12.md && grep -n "研究 agent" docs/progress.md`

## Claude 自行決定

1. 任務改名 `research`，不沿用 `search`：成效數字才分得出新舊。每週檢查只看 `research`，所以這週（已跑過搜尋補漏）核准後就能實跑
2. 研究 agent 的提交要先用 read_page 讀過那一頁：搜尋補漏讀 1 頁就提交 9 個，等於只看搜尋摘要就提交。只套用在研究任務，逐校找不變
3. `agent_reader` 的密碼寫在預設設定，和 `scholar:scholar` 一樣：要防的是模型讀到個資，不是本機的人；模型看不到連線字串
4. 自由 SQL 的程式檢查只收一句 SELECT／WITH：真正的保護是帳號權限，程式檢查是為了擋掉改連線設定的句子（例如把逾時關掉），並給模型看得懂的錯誤
5. 上限數字：查詢 5 秒、50 筆、4,000 字；記憶 8 週、提供者 300 個；每次花費上限維持 NT$2
6. 成效先只做指令，不放進每週摘要或網頁：C5 選 A 只要數字，指令最少程式
