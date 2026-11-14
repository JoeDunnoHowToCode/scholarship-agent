# 獎學金說明計畫（2026-11-10，ADR-100）

狀態：**併入 `docs/extraction-fix-plan.md` 的段 5**（使用者 11-14 選 A：維持獨立的一步，排在全部重抽之後）。使用者 11-10 選戊：中文說明，每句附原文引用並核對。

## 問題

詳細頁沒有任何一段告訴你「這是什麼獎學金」。抽取表單從來沒有這個欄位（查過 `schemas.py`、`models.py`、`api.py` 和 git 紀錄），所以重抽也不會出現。

## 設計

### 資料

- 存在 `scholarships.extracted` 這個 JSONB 裡，不加資料表欄位，所以不用遷移：
  - `extracted["summary"]`：最多 3 筆 `{text, evidence, status}`。`text` 是中文的一句，`evidence` 是逐字的原文引用，`status` 是核對結果
  - `extracted["summary_from"]`：產生說明用的提示詞版本，例如 `summary-1`
- 寫入時整個 `extracted` 重新指定，不原地改字典（CLAUDE.md 規定）

### 產生：獨立的一步，不改抽取的提示詞

- 新提示詞 `prompts/summary/1.md`：讀這筆抽取用的快照原文（和核對用的同一份，`snapshot_text`），寫 2–3 句中文：誰提供、給誰、補助什麼。每句的 `evidence` 逐字複製原文，不改寫、不翻譯
- 新 schema `SummaryDraft`：`sentences: list[SummarySentence]`，每句 `text`、`evidence`。超過 3 句只留前 3 句
- 為什麼獨立一步，不加進抽取表單：
  - 加進抽取表單要改 `extract-12`、`outline-8`、`section-12` 三個提示詞。版本號一改，168 筆全部整份重抽，已經核對過的國籍、學位會重新抽而變動（ADR-074 發生過）
  - 獨立一步有自己的版本號（`summary_from`），之後改說明的提示詞，只會重做說明
  - 第 11 天的評估用的 `build_extraction` 不受影響，評估不會多花錢

### 核對：三關（照 `verify.py`）

1. **程式檢查**：句子裡的每個阿拉伯數字都要出現在引用裡（用 `rules.number_in_source`），沒有就是 `number_not_in_quote`
2. **引用存在**：`quote_in_source` 或 `quote_in_table_text`，沒有就是 `quote_not_found`
3. **AI 判斷**：新提示詞 `prompts/summary-check/1.md`，一次問完所有句子，沿用 `verify.py` 的 `Verdicts` 格式；規則是「引用必須寫到這句中文的每一個事實」。沒過就是 `not_supported`，AI 漏答也算沒過

另外：沒附引用是 `no_evidence`。通過的是 `supported`。

不改 `verify-5`：它是 `current_prompts()` 的一部分，改了會讓 168 筆全部整份重抽。

### 什麼時候產生

- `ensure_summary(session, llm, row)`：`summary_from` 不是最新版本就產生並核對，是最新就跳過
- 每天的檢查（`pipeline/jobs.py`）：`extract_source` 之後呼叫一次。整份重抽會換掉整個 `extracted`，說明跟著消失，所以下一行就重做；原文沒變的不會重做
- 既有資料：新指令 `uv run python -m app.features.scholarships.extract --backfill-summary [--limit N] [--max-cost NT$]`，每筆各自一個交易、鎖住那一列（照 `--backfill-amounts`）。跳過已封存和重複的（`duplicate_of` 有值）

### API 與網頁

- `ScholarshipDetail` 加 `summary: list[SummaryOut]`（`text`、`evidence`），**只回傳通過核對的句子**
- 詳細頁：頁首摘要列下面、頁籤上面，加一塊「說明」：每句中文一行，下面用小字灰色放「原文引用」。沒有通過的句子就整塊不顯示

### 範圍外

- 列表卡片不顯示說明（卡片已經很滿）
- 說明不進變更紀錄、不發通知、不進搜尋向量
- 不改評估（ADR-098）

### 邊界情況

| 情況 | 結果 |
| --- | --- |
| 原文太短、AI 回空清單 | `summary` 是空清單，`summary_from` 照記，不會每天重試 |
| AI 呼叫失敗（`LLMError`） | 這筆不寫入，下次再試；不影響抽取本身 |
| 引用用刪節號省略 | 照 `quote_in_source` 的規則，每一截都要依序出現 |
| 中文寫「每月 1,400 歐元」、引用寫「EUR 1400」 | 數字比對把 1,400 和 1400 視為相同 |
| 已封存或重複的獎學金 | 補抽指令跳過；每天的檢查本來就不抽它們 |

## 費用

- 每筆兩次 AI 呼叫：說明約 US$0.006（和 `extract-12` 每次呼叫差不多，讀同一份原文），核對約 US$0.0004（`verify-5` 的平均）
- 補上既有的 168 筆：約 US$1.1（約 NT$36）。先跑 `--limit 5` 看品質，再跑其餘的

## 測試

| 行為 | 測試檔 |
| --- | --- |
| 核對三關的每種結果 | `tests/test_summary.py`（假的 AI，不碰資料庫） |
| 超過 3 句只留 3 句 | `tests/test_summary.py` |
| `ensure_summary` 寫入、版本是最新就跳過 | `tests/test_summary_db.py`（真的資料庫，交易裡跑完復原） |
| 補抽指令跳過封存與重複的 | `tests/test_summary_db.py` |
| 詳細頁 API 只回傳通過的句子 | `tests/test_summary_db.py` |

每天檢查的那一行呼叫（`jobs.py`）沒有現成的測試可以掛，用讀程式碼確認，並在補抽後看一筆的 `summary_from`。網頁沒有單元測試（第 9 天決定 27），用瀏覽器看，不按任何存檔按鈕。

## 檢查清單

- [ ] 核對：沒附引用 → `no_evidence` -> verify: `cd backend && uv run pytest tests/test_summary.py -k no_evidence`
- [ ] 核對：數字不在引用裡 → `number_not_in_quote` -> verify: `cd backend && uv run pytest tests/test_summary.py -k number`
- [ ] 核對：引用不在原文 → `quote_not_found` -> verify: `cd backend && uv run pytest tests/test_summary.py -k quote_not_found`
- [ ] 核對：AI 說不支持或漏答 → `not_supported`，支持 → `supported` -> verify: `cd backend && uv run pytest tests/test_summary.py -k verdict`
- [ ] 產生：超過 3 句只留 3 句 -> verify: `cd backend && uv run pytest tests/test_summary.py -k three`
- [ ] `ensure_summary` 寫入 `summary` 和 `summary_from`；已是最新就不呼叫 AI -> verify: `cd backend && uv run pytest tests/test_summary_db.py -k ensure`
- [ ] 補抽指令跳過封存與重複的 -> verify: `cd backend && uv run pytest tests/test_summary_db.py -k backfill`
- [ ] 詳細頁 API 只回傳通過核對的句子 -> verify: `cd backend && uv run pytest tests/test_summary_db.py -k detail`
- [ ] 每天的檢查在抽取後呼叫 `ensure_summary` -> verify: `grep -n "ensure_summary" app/features/pipeline/jobs.py`
- [ ] 前端型別與建置 -> verify: `cd frontend && npm run gen:api && npm run build`
- [ ] 補抽 5 筆看品質 -> verify: `cd backend && uv run python -m app.features.scholarships.extract --backfill-summary --limit 5 --max-cost 10`
- [ ] 補抽其餘的 -> verify: `cd backend && uv run python -m app.features.scholarships.extract --backfill-summary --max-cost 60`
- [ ] 詳細頁顯示說明與引用（瀏覽器，不按存檔） -> verify: 瀏覽器打開一筆有說明的詳細頁，`find "說明"`
- [ ] 完整檢查 -> verify: `cd backend && uv run pytest && uv run ruff check . && uv run mypy app`

## Claude 自行決定

1. 沒通過核對的句子不顯示，而不是標「待確認」：頁首那一塊是你最先讀的，錯的句子放在那裡會誤導人
2. 存在 `extracted` 裡，不加資料表欄位：只有詳細頁會讀它，不用拿它查詢或排序
3. 補抽跳過已封存的：它們已經不能申請，省下約 50 筆的費用
4. 核對用新的提示詞 `summary-check-1`，不改 `verify-5`：理由在「核對」一節
5. `run_backfill` 改成接收「要不要補」和「怎麼補」兩個函式，金額和說明共用同一個迴圈，不複製一份
