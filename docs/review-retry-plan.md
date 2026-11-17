# 核對沒過就拋回 AI 重抽：實作計畫（2026-11-18，ADR-111）

狀態：**完成（11-18）**。結果：`docs/eval/2026-11-18-retry.md`。

- 決定：ADR-111（使用者 11-18 用 `/decision-brief` 從 A–D 選 B）
- 起因：`docs/extraction-standard-report.md` 第 8.3 節。offered 還有 12 個錯，改提示詞擋不下來。

## 問題

抽取後的三關核對只會把沒過的欄位標成「待確認」，錯的值照樣存、照樣顯示。這次要把沒過的原因寫成錯誤訊息拋回 AI，重抽一次。

## 設計草圖

### 流程

```
抽取 → 程式規則 → 核對（三關，offered 也核對）
   └─ 全部通過 → 存檔（和現在一樣）
   └─ 有欄位沒過 → 組錯誤訊息 → 重抽一次（retry-1 提示詞＋原本的抽取提示詞）
                 → 程式規則 → 再核對
                 → 沒過的欄位比第一次少 → 用重抽的結果；否則留第一次的
                 → 存檔，extracted.retry 記下前後
```

### 要改的地方

| 部分 | 做法 | 位置 |
| --- | --- | --- |
| offered 加進核對 | `offered` 是 yes 或 no 時加一項核對：值是「這一屆或下一屆（有／沒有）提供這個獎學金」，引用是 `offered_evidence`；沒過就改成 unclear（和國籍沒過改成 unclear 一樣） | `verify.claims`、`verify.apply_verification` |
| 哪些狀態要重抽 | `not_supported`、`quote_not_found`、`no_evidence`、`year_not_in_quote`、`closes_before_opens`、`degree_not_in_quote`、`number_not_in_quote`、`invalid_currency`、`period_mismatch`。不重抽的：`incomplete`（年份交給程式推算，ADR-110）、`empty`、`conflict`（長文件各節說法不同） | 新模組 `scholarships/retry.py` |
| 錯誤訊息 | 每個沒過的欄位一行：欄位、上次填的值、上次的引用、為什麼沒過（白話）、對應標準的哪一條 | `retry.problems(draft, status)` |
| 重抽 | 提示詞 `retry-1` 放在原本的抽取提示詞前面：「上一次的結果有這些問題…只修正這些欄位，其他照原文」。同一個 schema | `extract.extract_web` 多一個參數 |
| 選結果 | 數兩次各有幾個欄位沒過（國籍、學位、每個申請期、每筆金額、offered），重抽的比較少才用 | `retry.failures`、`build_extraction` |
| 記錄 | `extracted.retry = {"fields": [...], "before": n, "after": m, "kept": "retry" 或 "first"}` | `build_extraction` |
| 範圍 | 整份抽的網頁和同一頁的其他獎學金（focus）。長文件（大綱＋分節、PDF）這一版不重抽 | `build_extraction` |

### 邊界情況

- 重抽的 AI 把原本對的欄位改錯：用「沒過的欄位數」比較，重抽的比較少才採用；但如果它把對的值改成另一個「也通過核對」的值，數字看不出來。這一點靠段 3 的重新檢查量。
- 重抽的呼叫失敗（AI 錯誤）：留第一次的結果，照常存檔，不讓整個來源失敗。
- 費用：
  - 本機資料約 50% 至少有一個欄位沒過
  - 每天約 30 個來源重抽，約 15 個會多一次呼叫，每次約 NT$0.31
  - 每月約 NT$140，比簡報估的 NT$90 高
- 評估（`evaluation.run`）用同一個 `build_extraction`，之後的評估也會包含重抽。

### 不在範圍內

- 漏抽：沒抽出來的值不會進核對（ADR-111 的後果）
- 長文件的重抽
- 標準 v2 的 9 題（`docs/definitions-decisions-v2.md`）
- 全部重抽：只重抽 11-17 重新檢查有錯的 52 個來源來量效果；之後每天的檢查照 ADR-104，原文或模型變了才重抽，自然套用

## 測試對象

| 行為 | 測試檔 |
| --- | --- |
| offered 是 yes／no 時要核對；沒過改成 unclear | `tests/test_verify.py` |
| 錯誤訊息列出沒過的欄位、上次的值、原因 | 新增 `tests/test_retry.py` |
| 全部通過時不重抽（AI 只被呼叫一次抽取） | `tests/test_retry_db.py` |
| 有欄位沒過時重抽，重抽的提示詞帶著錯誤訊息 | `tests/test_retry_db.py` |
| 重抽比較好就用重抽的，否則留第一次的；`extracted.retry` 記錄前後 | `tests/test_retry_db.py` |
| 重抽的呼叫失敗時留第一次的結果 | `tests/test_retry_db.py` |
| 長文件不重抽 | `tests/test_retry_db.py` |

## 檢查表

在 `backend/` 執行。

### 段 1：offered 加進核對
- [x] offered 是 yes／no 時要核對；沒過改成 unclear -> verify: `uv run pytest tests/test_verify.py -k offered`
  ```
  1 passed, 7 deselected in 0.02s
  ```

### 段 2：重抽
- [x] 錯誤訊息 -> verify: `uv run pytest tests/test_retry.py`
  ```
  2 passed in 0.53s
  ```
- [x] 全部通過不重抽、有錯才重抽且帶錯誤訊息 -> verify: `uv run pytest tests/test_retry_db.py -k "no_retry or retries"`
  ```
  2 passed, 3 deselected in 0.47s
  ```
- [x] 比較好才採用、記錄前後 -> verify: `uv run pytest tests/test_retry_db.py -k fewer`（測試名稱和計畫原本寫的不同）
  ```
  1 passed, 4 deselected in 0.48s
  ```
- [x] 重抽失敗留第一次、長文件不重抽 -> verify: `uv run pytest tests/test_retry_db.py -k "failed_retry or long"`（長文件那個第一次就通過，見 commit 7dc27e9；拿掉判斷後確認會失敗）
  ```
  2 passed, 3 deselected in 0.50s
  ```
- [x] 提示詞 retry-1 有版本號 -> verify: `uv run pytest tests/test_prompts.py`
  ```
  15 passed in 0.40s
  ```
- [x] 完整檢查 -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
  ```
  395 passed / All checks passed! / no issues found in 126 source files
  ```

### 段 3：量效果
- [x] 備份後重抽 11-17 有錯的 52 個來源（上限 NT$30） -> verify: `extract --force --source …（52 個） --max-cost 30`，貼上完成／失敗與重抽了幾個
  ```
  完成 49＋3、失敗 0（第一次碰到上限停在 49 個，補跑 3 個）；80 筆裡 36 筆觸發重抽，15 筆採用重抽的
  ```
- [x] 2 個判斷者（effort medium）用同一份指示檢查同樣 51 筆，和 extract-17 那輪比較 -> verify: 數字寫進 `docs/eval/2026-11-18-retry.md`
  ```
  錯誤 50 → 48、offered 判錯 13 → 11
  ```
- [x] 學習卡、`docs/progress.md` -> verify: 檔案已更新
  ```
  `docs/learning/day-11.md` 第 7 張、`docs/progress.md`
  ```

## 費用

- Gemini：段 3 約 NT$20–30；之後每月約 NT$140（見邊界情況）
- Claude：判斷者約 30 萬 tokens

## Claude 自行決定（小問題，請事後檢查）

1. offered 核對沒過就改成 unclear：和國籍沒過改成 unclear（`apply_verification`）一樣；照標準 5.1，不確定時是 unclear。
2. 最多重抽一次（`max_retries=1`）：控制費用；Instructor 的範例是 2 次。
3. 用「沒過的欄位數」決定採用哪一次，重抽的嚴格比較少才用：避免重抽把結果變差。
4. 長文件這一版不重抽：大綱＋分節的流程要每一節各自重抽，工作量大；本機的長文件很少（主要是教育部的簡章）。
5. 先只重抽 52 個來源量效果，不全部重抽：ADR-104 之後每天的檢查會自然套用；要全部重抽約 NT$120–150，量完效果再說。
