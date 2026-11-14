# 抽取修正計畫（2026-11-14，ADR-103、104、105）

狀態：**使用者 11-14 核准**，進行中。

使用者 11-14 選 1-B（只重抽指定的來源）、2-B（schema 加欄位），並接受程式規則（ADR-103）。

## 問題

11-14 總檢查（`docs/eval/2026-11-14-audit.md`）：249 筆有 128 筆至少一個欄位有錯，共 206 個錯。

- **118 個（57%）的線索已經存了**：例如同一筆錢列兩次、引用寫每學期卻存成每年。程式規則就能修。
- **約 50 個是 schema 沒有欄位能表達**：非申請期被當成申請期、今年沒開卻照樣存、同一頁別的獎學金的錢。
- **其他是 AI 漏抽或判斷錯**：要改提示詞、重抽。
- **以後改提示詞**：現在會讓約 250 個來源全部重抽（約 NT$65），約 30% 的來源會有欄位隨機變動。

## 設計草圖

### 資料模型（ADR-105）

`schemas.py` 加三個欄位。`WindowDraft`、`AmountDraft` 是一般網頁和長文件（section）共用的，兩條路都會帶到。

| 位置 | 欄位 | 值 | 用途 |
| --- | --- | --- | --- |
| `WindowDraft` | `kind` | `scholarship`（申請這個獎學金，含和入學申請一起申請的）／`admission_only`（只有入學，沒有這個獎學金）／`document`（補件、上傳文件）／`payment`（繳費）／`other` | 只有 `scholarship` 會變成申請期、送截止提醒 |
| `ScholarshipDraft` | `offered`、`offered_evidence` | `yes`／`no`／`unclear`，加逐字引用 | `no` 的不產生申請期 |
| `AmountDraft` | `for_this` | `true`／`false` | `false` 的不列進金額描述與評分，但照樣存下來 |

- **舊資料沒有新欄位時**：當成 `kind=scholarship`、`offered=unclear`、`for_this=true`，也就是行為和現在一樣，等重抽補上。
- **`offered=unclear`** 當成有開，不隱藏。

### 程式規則（ADR-103）

放在既有的 `rules.py`（ADR-045 的程式檢查）。每條是純函式，回傳修正後的資料和 issue 代碼（寫進 `verification.issues`，查得到哪條規則動過）。

1. **同一筆錢列兩次**
   - 種類、數值、幣別、期間、適用對象都一樣 → 只留一筆
   - 同種類、同幣別，「每月 × 2–48 個月 ＝ 總額」 → 去掉總額
2. **期間和引用不合**：引用寫 per semester／每學期，期間卻是 year → 標成待確認（不自己換算，因為不知道一年幾學期）
3. **截止早於開放** → 那個申請期標成待確認
4. **獎學金的國籍範圍和申請期的國籍範圍互相矛盾** → 標成待確認

接進流程的兩個地方：
- `build_extraction` 在申請期去重之後套用規則。
- 新指令 `extract --rules-only`：對已存的資料重新套用規則，重算金額描述、重建申請期，不呼叫 AI。在同一個交易內完成，JSONB 整個重新指定。

### 快取規則（ADR-104）

- `extract_source` 比較「上次抽取的條件」時，不再比提示詞版本，只比原文（ADR-079 的段落指紋）和模型。
- 新參數 `--force`，搭配可重複的 `--source`：指定的來源照樣重抽。
- 每筆資料照樣記下提示詞版本。

### 提示詞

- `extract-13`、`section-13`：加上三個新欄位的說明；國籍「只限非歐盟／EEA」要填 `excluded` 並列出國碼（AI 現在就會展開國碼，所以不用碰 #52）。
- `outline`、`verify` 沒用到新欄位，維持版本不變。

### 網頁

- `npm run gen:api` 更新型別。
- 詳細頁：`offered=no` 顯示「今年沒開」加引用；非申請獎學金的日期另外列成「其他時程」，讓分類錯了也看得到。
- 列表不用改：沒有申請期的，本來就不會出現在「還能申請」。

### 邊界情況

- 分類錯（把真的申請期分成 `document`）：就會漏掉截止提醒。詳細頁的「其他時程」看得到；重抽後的抽查會量這個。
- `offered=no` 但原文其實寫明年會開：申請期是空的，推估的下一屆（`cycles` 的 estimated）也不會產生。
- 1-B 之後資料庫有不同版本的資料：每筆的 `meta.prompts` 查得到。
- EACEA 目錄補的國籍（ADR-053）維持不變。

### 不在範圍內

- #52 國家集合怎麼存。
- 定期自動檢查（沒有選）。
- 研究 agent（另一份計畫 `docs/research-agent-plan.md`）。
- 獎學金說明的設計本身：照 `docs/summary-plan.md`，本計畫只排它的順序（段 5）。
- 漏抽的錯：只靠新提示詞改善，不另外設計。

## 測試對象

| 行為 | 測試檔 |
| --- | --- |
| 規則 1–4 | `tests/test_rules.py` |
| 規則接進抽取流程 | `tests/test_extract_build.py` |
| `--rules-only` 修已存的資料 | 新增 `tests/test_rules_recheck_db.py` |
| 舊資料的預設值、新欄位 | `tests/test_schemas.py` |
| 申請期只收 `kind=scholarship`、`offered=no` 不產生 | `tests/test_cycles.py` 或 `save_cycles` 的 DB 測試 |
| 金額描述只算 `for_this` | `tests/test_amounts.py` |
| API 回傳新欄位 | 既有的 scholarships API 測試 |
| 快取：只有提示詞變了不重抽、模型變了重抽、`--force` 重抽 | `tests/test_extract_build.py` 或新的 DB 測試 |

## 檢查表

在 `backend/` 執行：

### 段 1 程式規則（ADR-103）
- [ ] 完全一樣的金額只留一筆 -> verify: `uv run pytest tests/test_rules.py -k duplicate`
- [ ] 每月 × 月數 ＝ 總額時去掉總額 -> verify: `uv run pytest tests/test_rules.py -k monthly_total`
- [ ] 引用寫每學期、期間是每年 → 標成待確認 -> verify: `uv run pytest tests/test_rules.py -k semester`
- [ ] 截止早於開放 → 標成待確認 -> verify: `uv run pytest tests/test_rules.py -k order`
- [ ] 獎學金和申請期的國籍範圍矛盾 → 標成待確認 -> verify: `uv run pytest tests/test_rules.py -k scope_conflict`
- [ ] `build_extraction` 套用規則並記下 issue -> verify: `uv run pytest tests/test_extract_build.py`
- [ ] `--rules-only` 修已存的資料並重建申請期 -> verify: `uv run pytest tests/test_rules_recheck_db.py`
- [ ] 對本機資料執行一次（先備份） -> verify: `uv run python -m app.features.scholarships.extract --rules-only`（貼出修了幾筆）

### 段 2 schema 加欄位（ADR-105）
- [ ] 舊資料沒有新欄位時用預設值 -> verify: `uv run pytest tests/test_schemas.py -k defaults`
- [ ] 只有 `kind=scholarship` 的會變成申請期 -> verify: `uv run pytest tests/test_cycles.py -k kind`
- [ ] `offered=no` 不產生申請期 -> verify: `uv run pytest tests/test_cycles.py -k offered`
- [ ] 金額描述只算 `for_this` -> verify: `uv run pytest tests/test_amounts.py -k for_this`
- [ ] API 回傳新欄位 -> verify: `uv run pytest tests/test_scholarships_api.py -k offered`
- [ ] 提示詞 extract-13、section-13 -> verify: `uv run pytest tests/test_prompts.py`
- [ ] 詳細頁顯示「今年沒開」和其他時程 -> verify: `cd ../frontend && npm run gen:api && npm run build`，加上瀏覽器確認（不截個資）

### 段 3 快取規則（ADR-104）
- [ ] 只有提示詞版本變了 → 不重抽 -> verify: `uv run pytest -k prompt_change_does_not_reextract`
- [ ] 模型變了 → 重抽 -> verify: `uv run pytest -k model_change_reextracts`
- [ ] `--force --source` 指定的會重抽 -> verify: `uv run pytest -k force_source`

### 段 4 執行與驗證
- [ ] 完整檢查 -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] 新提示詞跑 57 個樣本的評估（約 NT$15），和 11-10 的基準比較 -> verify: `uv run python -m app.features.evaluation.run --models gemini-3.5-flash-lite --rounds 2 --max-cost 20`
- [ ] 備份後全部重抽一次（約 NT$65） -> verify: `uv run python -m app.features.scholarships.extract --force --max-cost 90`（貼出完成／失敗數）
- [ ] 重新檢查：上次有錯的 128 筆加隨機 30 筆對的，用同一份指示比較修好幾個、新錯幾個 -> verify: 報告寫進 `docs/eval/2026-11-xx-audit.md`
- [ ] 學習卡、`docs/progress.md` -> verify: 檔案已更新

### 段 5 獎學金說明（`docs/summary-plan.md`，ADR-100 說明那條；使用者 11-14 選 A）
- [ ] 照 `docs/summary-plan.md` 的檢查清單做；補抽排在段 4 的全部重抽之後（先補的話，全部重抽會換掉整個 `extracted`，說明被洗掉、要重做） -> verify: 該計畫各項的指令

## 費用

- Gemini：評估約 NT$15，加上全部重抽約 NT$65，合計約 NT$80；段 5 的說明補抽另計（每筆約 NT$0.2）。
- 重新檢查用 Claude sub agent，花的是你的 Claude 用量，約 100 萬 tokens（這次 249 筆用了約 166 萬）。

## Claude 自行決定（小問題，請事後檢查）

1. 國籍「只限非歐盟」交給新提示詞處理，不寫成程式規則。程式規則要一份歐盟國家清單，那是 #52 待決定的題目。
2. 每學期的金額不自己換算成每年，只標成待確認。
3. 舊資料沒有新欄位時，預設成和現在一樣的行為。
4. `offered=unclear` 當成有開。
5. 「每月 × 月數 ＝ 總額」的月數範圍定為 2–48。
6. 只升 extract、section 的版本；outline、verify 沒用到新欄位。
7. 重新檢查的樣本：上次有錯的 128 筆，加隨機 30 筆上次全對的（固定亂數種子），才量得到「新錯」。
8. 段的順序：規則 → schema → 快取 → 執行。快取規則在全部重抽之前改好，重抽改用 `--force`。
