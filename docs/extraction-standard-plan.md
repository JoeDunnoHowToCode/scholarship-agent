# 抽取標準實作計畫（2026-11-16，ADR-107–110）

狀態：**完成（11-17）**。完整報告：`docs/extraction-standard-report.md`。

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
- **假設一個來源一筆的程式**改成「這個來源的所有獎學金」（原本寫 14 處；11-16 實查 `source_id ==` 有 12 個檔案 28 處，不是每處都和獎學金有關，要逐一看），包括：
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
- [x] 兩群人金額一樣就合併成一筆 -> verify: `uv run pytest tests/test_merge.py -k same_amount`
  ```
  1 passed, 19 deselected in 0.02s
  ```
- [x] 值等於引用裡兩個數字的差也算有依據 -> verify: `uv run pytest tests/test_amounts.py -k difference`
  ```
  1 passed, 9 deselected in 0.02s
  ```
- [x] 只有月日的申請期推算下一次、標 `year_inferred` -> verify: `uv run pytest tests/test_save_cycles_db.py -k year_inferred`
  ```
  1 passed, 1 deselected in 0.42s
  ```
- [x] `year_inferred` 的申請期照常提醒，文字標推估 -> verify: `uv run pytest tests/test_notification_rules.py -k inferred`
  ```
  1 passed, 9 deselected in 0.35s
  ```
- [x] 網頁顯示「年份推估」與「過去的資訊」 -> verify: `cd ../frontend && npm run build`，加上瀏覽器確認（不截個資、不按存檔）
  ```
  ✓ built in 268ms
  #557：頁首摘要、申請期那一行、核對狀態都有「年份推估」
  #63（offered=no）：「說明（過去的資訊）」「補助（過去的資訊）」；console 沒有錯誤
  ```
- [x] `--rules-only` 合併後的金額不能丟、資料沒變也要重建申請期（實作時發現的缺口，先寫重現測試）-> verify: `uv run pytest tests/test_rules_recheck_db.py`
- [x] 對本機資料套用（先備份 `before-standard-rules-20261116-2303.dump`） -> verify: `uv run python -m app.features.scholarships.extract --rules-only` 與 `cycles`
  ```
  重新套用規則：看了 259 筆，24 筆有變
  申請期：開放中 136、即將開放 41、已截止 65、預估 0
  這次封存 3 筆、喚回 1 筆、新增預估申請期 49 筆；資料過舊 5 筆
  申請期核對狀態：year_inferred 36 個；兩群人合併的金額 34 筆
  ```

### 段 2
- [x] 新欄位與預設值（百分比、第一年、other、下一屆說明、不是獎學金、群組） -> verify: `uv run pytest tests/test_schemas.py`
  ```
  3 passed in 0.03s
  ```
- [x] 百分比的核對與描述 -> verify: `uv run pytest tests/test_amounts.py -k percent`
  ```
  1 passed, 10 deselected in 0.05s
  ```
- [x] 群組展開成國碼；不認識的群組標待確認 -> verify: `uv run pytest tests/test_groups.py`（存檔時展開另見 `tests/test_extract_build.py -k groups`）
  ```
  3 passed in 0.02s
  ```
- [x] 不是獎學金就停用來源並出現在報告 -> verify: `uv run pytest tests/test_not_scholarship_db.py`（報告文字另見 `tests/test_pipeline_messages.py -k not_scholarship`）
  ```
  4 passed in 0.98s
  ```
- [x] 詳細頁回傳下一屆公布說明 -> verify: `uv run pytest tests/test_detail_kinds_db.py`
  ```
  2 passed in 1.09s
  ```
- [x] 提示詞 extract-15、section-15、outline-10 -> verify: `uv run pytest tests/test_prompts.py`
  ```
  15 passed in 0.72s
  ```
- [x] 前端型別與顯示 -> verify: `cd ../frontend && npm run gen:api && npm run build`
  ```
  🚀 openapi.json → src/api/schema.d.ts
  ✓ built in 235ms
  ```

### 段 3
- [x] 遷移：`source_id` 不再唯一，（`source_id`, `key`）唯一，既有資料補 `key` -> verify: `uv run alembic upgrade head` 後查 `\d scholarships`（先備份 `before-multi-key-20261116-2317.dump`）
  ```
  Running upgrade cc936d925bfc -> 0ed701dc7733, scholarships key per source
  key | text | not null | 'main'::text
  "scholarships_source_id_key_key" UNIQUE CONSTRAINT, btree (source_id, key)
  ```
- [x] 列出頁面上的獎學金；多個時各抽一次（改成主抽取順便列出，見「Claude 自行決定」第 12 點，測試併入下一行） -> verify: `uv run pytest tests/test_multi_scholarship_db.py`
- [x] 同一來源多筆的存檔、找同一筆、消失的封存 -> verify: `uv run pytest tests/test_multi_scholarship_db.py`
  ```
  5 passed in 1.07s
  ```
- [x] 候選規則以獎學金為單位 -> verify: `uv run pytest tests/test_candidates_db.py`
  ```
  10 passed in 1.41s
  ```
- [x] 其他假設一來源一筆的地方都改完 -> verify: `grep -rn "Scholarship.source_id ==" app`（每一處都看過）
  ```
  pipeline/jobs.py:142      due_source_ids：只 join 主角（測試：每天只排一次）
  settings/api.py:114       計數，多筆照算，不用改
  discovery/intake.py:173   _scholarships：全部，主角排第一（候選規則任一筆通過）
  search/index.py:159       每一筆都建向量（測試）
  search/index.py:202       EXISTS，來源只排一次
  evaluation/run.py:180     只 join 主角（樣本以來源為單位）
  scholarships/summary.py:80  每一筆都補說明（測試）
  scholarships/models.py:95   main_of
  scholarships/pdfs.py:105    加 key == main（PDF 補抓以來源為單位）
  scholarships/extract.py:550、561  find_other、archive_gone
  scholarships/extract.py:636 recheck_rules 指定來源：全部
  另外：dedup 只拿主角比對網址（測試）；候選的重複比對排除同一來源（測試）
  ```

### 段 4
- [x] 完整檢查 -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
  ```
  387 passed, 1 warning
  All checks passed!
  Success: no issues found in 125 source files
  ```
- [x] 評估 57 個樣本（上限改成 NT$48，見第 20 點） -> verify: `uv run python -m app.features.evaluation.run --models gemini-3.5-flash-lite --rounds 2 --max-cost 48`
  ```
  樣本 57 個，花了約 NT$35.82；報告 docs/eval/2026-11-16.md
  國籍 97%、學位 86%、截止日 64%、金額 91%；失敗 4（KeyError: 'other'，已修）；沒有觸發停止條件
  ```
- [x] 備份後全部重抽（`before-reextract-standard-20261116-2344.dump`；分 3 份，每份上限 NT$40） -> verify: `uv run python -m app.features.scholarships.extract --force --shard K/3 --max-cost 40`
  ```
  完成 74＋83＋99、失敗 0；第 0 份碰到上限，剩 4 個
  ```
- [x] 收緊「不是獎學金」與「其他獎學金」後補抽 122 個來源（extract-16，實作時發現的問題，報告第 6 節） -> verify: `extract --force --source …（122 個） --max-cost 30`
  ```
  完成 61＋61、失敗 0（NT$27.3＋26.1）；不是獎學金 16 → 7，再加核對 AI 後 → 1
  ```
- [x] 補抽說明 -> verify: `uv run python -m app.features.scholarships.extract --backfill-summary --max-cost 30`（結果見報告第 4 節）
- [x] 依標準重新檢查 158 筆＋新拆出的 42 筆 -> verify: 報告寫進 `docs/eval/2026-11-17-standard.md`
  ```
  截止日 59% → 74%、國籍 76% → 81%、學位 97% → 94%、金額 69% → 57%、今年有沒有開 86%
  ```
- [x] 學習卡、`docs/progress.md` -> verify: 檔案已更新（`docs/learning/day-11.md` 第 6 張）

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
7. **停止條件**（11-16 補）：段 4 的評估若有任何欄位的「有根據」比 11-14（`docs/eval/2026-11-14.md`）低 5 個百分點以上，就停下來報告，不做全部重抽。
8. 年份推算只用在 AI 沒填年份（`incomplete`）的日期；AI 自己填了、引用裡卻沒有的年份（`year_not_in_quote`）照舊不建申請期：那是 AI 違反 ADR-045，要讓它看得到。
9. 年份推估的申請期在評分裡算「未核對」（`verified` 只認 `supported`），時間條件是待確認，不是通過；提醒照送。
10. 兩群人合併只在兩筆都寫了適用對象時：沒寫的代表所有人，和某一群一樣時不合併。
11. `--rules-only` 改成每筆都重建申請期（原本只重建有變的）：建申請期的規則改了也要套到舊資料；之後照舊執行 `cycles` 指令重新產生預估。
12. **不另外呼叫「列出獎學金」**（計畫原本寫 `listing-1`）：主抽取多一個欄位 `other_scholarships`，有列出來的才各抽一次（提示詞 `focus-1` 放在抽取提示詞前面）。只有一個獎學金的頁面（大多數）不多花錢；`listing.py` 這個名稱也已經被列表用掉。
13. **主角的 `key` 固定是 `main`**（計畫原本寫正規化的名稱）：既有資料遷移後全部是 main，主角永遠更新同一筆，不會因為 AI 寫的名稱不同變成新的一筆；相似度 ≥ 0.9 只用在其他獎學金。
14. 一頁最多另外抽 5 個（`MAX_OTHERS`）；長文件（大綱＋分節）照舊只抽一個。
15. 頁面上不再出現的其他獎學金：封存、刪掉它的申請期（申請期可以從抽取結果重建，不是資料遺失），抽取結果標 `gone`，`--rules-only` 跳過它；再出現時重新存檔會蓋掉標記。
16. 「不是獎學金」除了停用來源，也封存那筆獎學金（預設的列表看不到）；引用一定要在原文裡才停用。
17. 每天的 `refresh` 只在有申請期時喚回已封存的（原本一個申請期都沒有也會喚回，和註解寫的不一樣）：否則「不是獎學金」封存的隔天就回來。
18. 去重：同一頁拆出來的多筆網址一樣，只有主角拿網址比對；候選的重複比對排除同一來源。
19. 學位 `other` 只在顯示時叫「其他」（`DEGREE_LABELS`）；個人資料與篩選照舊只有學士、碩士、博士。
20. 段 4 評估的費用上限從 NT$40 改成 NT$48：上次每個來源每輪約 NT$0.31，57 × 2 輪約 NT$35，新提示詞比較長，40 可能又讓第 2 輪跑一半。
21. 「不是獎學金」也交給核對的 AI（和其他欄位同一次呼叫）：只靠「引用在原文裡」擋不住「這一屆沒有」與壞掉的網頁。
22. 其他獎學金沒有自己的金額（`for_this`）也沒有申請獎學金的日期，就不存：頁面只是列出外部資助管道。
23. 程式停用的來源（`review_note` 以「判斷不是獎學金」開頭）在判斷改回來時自動打開；使用者在設定頁停用的不動。
24. `gone` 的獎學金不產生通知：封存擋不住 `generate`，每日檢查會替 235 筆發通知。
25. 目錄頁的國籍依據（ADR-053）只給主角；同一頁拆出來的獎學金沒寫國籍就是不清楚。
26. 依標準重新檢查只從 108 筆拆分資料裡抽 42 筆（固定亂數），把 Claude 用量壓在約 120 萬 tokens。
