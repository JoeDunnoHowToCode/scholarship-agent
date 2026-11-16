# 抽取標準實作計畫（2026-11-16，ADR-107–110）

狀態：**等使用者核准**。

- 標準：`docs/extraction-standard.md`
- 題目與選項：`docs/definitions-decisions.md`

## 問題

兩次檢查有 362 個錯，很多出在「什麼才算對」沒有定義。使用者 11-16 定了 17 題的標準，這份計畫把它做進提示詞、schema 與程式。

## 設計草圖

### 段 1：不用改 schema 的程式規則（不花錢，`--rules-only` 就能套用）

| 標準 | 做法 | 位置 |
| --- | --- | --- |
| C5 A 兩群人金額一樣就合併 | `merge.clean_amounts` 再加一步：用途、數值、幣別、期間都一樣，就合併成一筆，適用對象用「、」接起來 | `merge.py` |
| C2 A 原價與實付的差額 | `amount_status` 的數字檢查：值等於引用裡兩個數字的差，也算有依據 | `amounts.py` |
| B3 B 沒寫年份的日期（ADR-110） | `save_cycles` 遇到只有月日的申請期，取今天以後最近的那一天建成申請期，`verification="year_inferred"`。它不是預估（`estimated` 照舊是 False），所以照常送提醒 | `extract.py`、`cycles.py` |
| B3 B 提醒標推估 | 截止提醒的文字在 `year_inferred` 時加「（年份推估）」；網頁的核對狀態顯示「年份推估」 | `notifications/`、`labels.ts` |
| E2 B 不提供時標「過去的資訊」 | 詳細頁在 `offered=no` 時，金額與說明的標題旁加「過去的資訊」 | `ScholarshipDetail.tsx` |

### 段 2：schema 加欄位與新提示詞

| 標準 | schema | 程式 |
| --- | --- | --- |
| C1 B 百分比 | `AmountDraft.value` 改成可以空白；加 `percent: float \| None` | 核對：有百分比時檢查引用裡有這個百分比；金額描述寫「學費減免 50%」；列表的大概金額只看有數值的 |
| C4 C 第一年 | `AmountPeriod` 加 `first_year` | 期間名稱「第一年」 |
| F1 B 學位 other | `Degree` 加 `other` | 評分不用改：`degree_check` 只認使用者想讀的學位，`other` 自然不符合；網頁的學位名稱加「其他」 |
| B1 B 只存最新一屆 | `ScholarshipDraft` 加 `next_cycle_note`（原文怎麼說下一屆何時公布）與引用 | 詳細頁的申請期沒有下一屆時，顯示這句 |
| A2 C 不是獎學金 | `ScholarshipDraft` 加 `not_scholarship: bool` 與引用 | 抽到 `true` 就停用來源，`review_note` 寫原因；每天的報告列出「判斷不是獎學金而停用的來源」 |
| D1 C 國家群組（ADR-109） | 國籍與申請期的國籍各加 `nationality_groups: list[str]`（群組代號） | 新模組 `scholarships/groups.py`：群組代號 → 國碼清單，附出處；存檔時展開成國碼；不認識的群組存原文名稱，國籍標待確認 |

- 新提示詞 extract-15、section-15、outline-10 照標準全部重寫規則，包括 B2 A、B4 A、B5 B、C2 A、C3 A、D2 B、E1 B 這些只需要改提示詞的。
- 群組清單第一版：歐盟 27 國、EEA（歐盟＋冰島、列支敦斯登、挪威）、瑞士、Erasmus+ Programme／Partner（沿用 ADR-054 的清單）、African Union 會員國。每份清單附官方出處與查證日期。

### 段 3：一頁多個獎學金（ADR-108）

- **資料表**：
  - `scholarships` 去掉 `source_id` 的唯一限制，加 `key`（獎學金名稱正規化後的字串）
  - 唯一限制改成（`source_id`, `key`）
  - Alembic 遷移，既有資料的 `key` 用現在的名稱算
- **抽取**：
  1. 新的一步：先請 AI 列出頁面上有哪些獎學金（名稱、是不是這個來源的主角），提示詞 `listing-1`
  2. 一個 → 照現在的流程抽
  3. 多個 → 每個各抽一次，提示詞加「只抽『某某』這一個」
- **存檔**：
  - 用（來源, `key`）找同一筆
  - 頁面上不再出現的，那一筆照封存規則處理（不刪）
- **14 處假設一個來源一筆的程式**改成「這個來源的所有獎學金」，包括：
  - 每天的檢查
  - 候選的四條規則：任一筆通過就加入
  - 找新網址、搜尋索引、評估、PDF 補抓、設定頁
- **去重（ADR-097）**：同一來源的多筆不互相比對。

### 段 4：執行與驗證

1. 評估 57 個樣本（費用上限 NT$40，這次不讓第 2 次跑一半）
2. 備份後全部重抽
3. 補抽新獎學金的說明
4. 判斷者用 `docs/extraction-standard.md` 重新檢查同樣的 158 筆，加上段 3 拆出來的新獎學金

### 邊界情況

- 推估年份的日期，原文其實是舊資訊：會推出錯的日期；網頁與提醒都標「年份推估」。
- 停用來源判斷錯：每天的報告列出來，設定頁可以重新打開。
- 一頁拆成多筆時，名稱每天被 AI 寫得不一樣：會被當成新的一筆。`key` 用正規化的名稱（去掉標點、大小寫），並在同一來源內用名稱相似度對回舊的。
- 百分比和金額同時存在（例如減 50%，約 4,500 歐元）：兩個都存。

### 不在範圍內

- 審核重抽的流程（上次的 A／B／C）：等這份標準做完、量過之後再決定。
- 研究 agent（`docs/research-agent-plan.md`）。

## 測試對象

| 行為 | 測試檔 |
| --- | --- |
| 兩群人金額一樣就合併 | `tests/test_merge.py` |
| 差額算有依據 | `tests/test_amounts.py` |
| 沒寫年份的日期推算下一次、標 `year_inferred`、照常提醒 | `tests/test_save_cycles_db.py`、`tests/test_notification_rules.py` |
| 百分比、第一年、學位 other 的 schema 與預設值 | `tests/test_schemas.py` |
| 百分比的核對與描述 | `tests/test_amounts.py` |
| `not_scholarship` 停用來源、出現在報告 | 新增 `tests/test_not_scholarship_db.py` |
| 群組展開成國碼、不認識的群組標待確認 | 新增 `tests/test_groups.py` |
| 下一屆公布說明出現在 API | `tests/test_detail_kinds_db.py` |
| 列出頁面上的獎學金、多個時各抽一次 | 新增 `tests/test_listing.py`（假的 AI） |
| 同一來源多筆的存檔、找同一筆、消失的封存 | 新增 `tests/test_multi_scholarship_db.py` |
| 候選規則以獎學金為單位 | `tests/test_candidates_db.py`（新增測試，不改舊的） |

## 檢查表

在 `backend/` 執行。

### 段 1
- [ ] 兩群人金額一樣就合併成一筆 -> verify: `uv run pytest tests/test_merge.py -k same_amount`
- [ ] 值等於引用裡兩個數字的差也算有依據 -> verify: `uv run pytest tests/test_amounts.py -k difference`
- [ ] 只有月日的申請期推算下一次、標 `year_inferred` -> verify: `uv run pytest tests/test_save_cycles_db.py -k year_inferred`
- [ ] `year_inferred` 的申請期照常提醒，文字標推估 -> verify: `uv run pytest tests/test_notification_rules.py -k inferred`
- [ ] 網頁顯示「年份推估」與「過去的資訊」 -> verify: `cd ../frontend && npm run build`，加上瀏覽器確認（不截個資、不按存檔）
- [ ] 對本機資料套用（先備份） -> verify: `uv run python -m app.features.scholarships.extract --rules-only` 與 `cycles`

### 段 2
- [ ] 新欄位與預設值（百分比、第一年、other、下一屆說明、不是獎學金、群組） -> verify: `uv run pytest tests/test_schemas.py`
- [ ] 百分比的核對與描述 -> verify: `uv run pytest tests/test_amounts.py -k percent`
- [ ] 群組展開成國碼；不認識的群組標待確認 -> verify: `uv run pytest tests/test_groups.py`
- [ ] 不是獎學金就停用來源並出現在報告 -> verify: `uv run pytest tests/test_not_scholarship_db.py`
- [ ] 詳細頁回傳下一屆公布說明 -> verify: `uv run pytest tests/test_detail_kinds_db.py`
- [ ] 提示詞 extract-15、section-15、outline-10 -> verify: `uv run pytest tests/test_prompts.py`
- [ ] 前端型別與顯示 -> verify: `cd ../frontend && npm run gen:api && npm run build`

### 段 3
- [ ] 遷移：`source_id` 不再唯一，（`source_id`, `key`）唯一，既有資料補 `key` -> verify: `uv run alembic upgrade head` 後查 `\d scholarships`
- [ ] 列出頁面上的獎學金；多個時各抽一次 -> verify: `uv run pytest tests/test_listing.py`
- [ ] 同一來源多筆的存檔、找同一筆、消失的封存 -> verify: `uv run pytest tests/test_multi_scholarship_db.py`
- [ ] 候選規則以獎學金為單位 -> verify: `uv run pytest tests/test_candidates_db.py`
- [ ] 其他假設一來源一筆的地方都改完 -> verify: `grep -rn "Scholarship.source_id ==" app`（每一處都看過，貼出結果）

### 段 4
- [ ] 完整檢查 -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] 評估 57 個樣本 -> verify: `uv run python -m app.features.evaluation.run --models gemini-3.5-flash-lite --rounds 2 --max-cost 40`
- [ ] 備份後全部重抽 -> verify: `uv run python -m app.features.scholarships.extract --force --max-cost 120`
- [ ] 補抽說明 -> verify: `uv run python -m app.features.scholarships.extract --backfill-summary --max-cost 30`
- [ ] 依標準重新檢查 158 筆＋新拆出的 -> verify: 報告寫進 `docs/eval/2026-11-xx-standard.md`
- [ ] 學習卡、`docs/progress.md` -> verify: 檔案已更新

## 費用

- Gemini：
  - 評估約 NT$40
  - 全部重抽約 NT$90–120（多了「列出獎學金」的呼叫，多個獎學金的頁面各抽一次）
  - 說明約 NT$10
  - 合計約 NT$140–170
- 重新檢查：你的 Claude 用量，約 120 萬 tokens。

## Claude 自行決定（小問題，請事後檢查）

1. 推算年份的申請期用 `verification="year_inferred"`，不用 `estimated`：預估的申請期不送提醒（`notifications/generate.py`），而 ADR-110 要送提醒。
2. 學位 `other` 在評分裡不符合任何想讀的學位，評分程式不用改。
3. 「不是獎學金」停用來源時，EACEA 目錄的學程也一樣停用；目錄匯入不會動 `enabled`（查過 `catalogue.py`），所以不會被自動打開。
4. 群組的國碼清單放在程式裡（像 ADR-054 的 Erasmus+ 清單），不建資料表。
5. 一頁多個獎學金的 `key` 用正規化的名稱；同一來源內名稱相似度 ≥ 0.9 就當成同一筆，避免 AI 寫法不同就變成新的一筆。
6. 段 3 排最後：它的工作量最大，前兩段做完就能先量到效果。
