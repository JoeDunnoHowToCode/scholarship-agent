# 抽取修正：完整報告（2026-11-14）

- **計畫**：`docs/extraction-fix-plan.md`
- **決定**：ADR-103（程式規則）、ADR-104（只重抽指定的來源）、ADR-105（schema 加欄位）、`docs/summary-plan.md`（獎學金說明，排在重抽之後，你選 A）
- **最後檢查**：`348 passed`、ruff `All checks passed!`、mypy `no issues found in 124 source files`、前端 `✓ built`，全部推上 main

## 1. 為什麼要做

11-14 用 Claude sub agent 對照原文檢查全部 249 筆：
- 128 筆至少一個欄位有錯，共 206 個錯（`docs/eval/2026-11-14-audit.md`）
- 57% 的錯，線索已經存在資料庫裡
- 約 50 個錯是現在的表格裝不下的資訊：補件期間、今年沒開、同一頁別的獎學金的錢

另一個問題：提示詞一改版，約 250 個來源就會全部重抽，約 NT$65，而且沒問題的欄位也會跟著變。

## 2. 修改前後（重點程式碼）

### 2.1 程式規則（ADR-103）

**同一筆錢列兩次**（`rules.py`、`merge.py`、`extract.py`）

```python
# 修改前：只有長文件合併時去掉「完全一樣」的金額；一般網頁整份抽，不處理
draft = draft.model_copy(update={"windows": merge.dedupe_windows(draft.windows)})

# 修改後：所有抽取都去重；總額＝每月×2–48 個月（或每年×2–6 年）時拿掉總額
draft = draft.model_copy(update={"windows": merge.dedupe_windows(draft.windows)})
draft = draft.model_copy(update={"amounts": merge.clean_amounts(draft.amounts)})
```

**每學期被存成每年**（`amounts.py`）

```python
# 修改後：在 amount_status 的最後加一關，不換算，只標成待確認
if amount.period == "year" and SEMESTER.search(amount.evidence):
    return "period_mismatch"
```

**截止早於開放**（`verify.py`）：抽取和 `--rules-only` 共用同一個函式。

```python
# 修改前：rule_status 裡只檢查年份在不在引用裡
# 修改後：
def window_rule(window: WindowDraft) -> Status | None:
    if window.closes_year and not rules.deadline_year_in_quote(window.closes_year, window.evidence):
        return "year_not_in_quote"
    if all(opens) and all(closes) and closes < opens:
        return "closes_before_opens"
    return None
```

**新指令 `--rules-only`**（`extract.recheck_rules`）：對已存的資料重新套用規則，不呼叫 AI；有變的就重建申請期。

### 2.2 schema 加欄位（ADR-105）

```python
# 修改前：WindowDraft 只有 funding（獎學金生／自費／不限）
# 修改後（schemas.py）：
kind: WindowKind = Field(default="scholarship", ...)      # scholarship / admission_only / document / payment / other
# AmountDraft
for_this: bool = Field(default=True, ...)                  # 是不是這個獎學金的錢
# ScholarshipDraft、Outline
offered: Offered = Field(default="unclear", ...)           # yes / no / unclear
offered_evidence: str | None = Field(default=None, ...)
```

**申請期只建「申請獎學金」的日期**（`extract.save_cycles`）

```python
# 修改後：加在「年月日不齊全就跳過」之後
if window.kind != "scholarship" or offered == "no":
    continue
```

另外：
- 最早截止日（`earliest_deadline`）只算 `kind=scholarship`。否則補件日期會被當成截止日，系統就不會去補抓 PDF。
- 金額描述、列表的金額、詳細頁的金額，都只算 `for_this` 不是 false 的（`amounts.own`、`api.amount_items`）。
- 詳細頁 API 多三個欄位：`offered`、`offered_evidence`、`other_dates`。
- 網頁的詳細頁：`offered=no` 時顯示紅色標籤「這次不提供」加引用；非申請獎學金的日期另外列成「其他時程」。

**提示詞**
- extract-12 → 13 → 14、section-12 → 13 → 14、outline-8 → 9
- 加上三個新欄位的說明
- 「只限非歐盟／EEA」要填 excluded 並列出國碼
- 同一筆錢不要用每月和總額各寫一次
- extract-14 再補一句：申請入學就會一起審核的獎學金，入學期間也算申請期

**評估抓到的誤報**（`rules.excluded_as_group`）
- 問題：「排除歐盟各國」會列出約 30 個國碼，原本的國名檢查要求每個國名都在原文裡，結果一筆多出 29 個假問題。
- 修法：原文用歐盟／EEA 一次排除時，不逐一檢查國名。

### 2.3 快取規則（ADR-104）

```python
# 修改前（extract_source）：快照、4 個提示詞版本、模型，任一個變了就整份重抽
if existing and existing.extracted.get("meta") == meta:
    return "unchanged"

# 修改後：不看提示詞版本；原文和模型都沒變就跳過；要用新版重抽就指定 force
same_model = bool(existing) and not force and old_meta.get("model") == meta["model"]
if existing and same_model and old_meta.get("snapshots") == hashes:
    return "unchanged"
```

指令列加上 `--force`，`--source` 可以重複寫，例如 `extract --force --source 3 --source 14`。

### 2.4 獎學金說明（段 5）

- **新模組** `summary.py`：
  - 寫 2–3 句中文，每句附原文引用
  - 核對三關：數字在引用裡 → 引用在原文裡 → AI 判斷
  - 只顯示通過的句子
- **每天的檢查**（`pipeline/jobs.py`）：抽完就補說明；已經是最新版本的不呼叫 AI。
- **補抽**：`extract --backfill-summary`，跳過已封存和重複的。`run_backfill` 改成金額和說明共用。
- **詳細頁**：頁首摘要下面多一塊「說明」。

## 3. 執行結果

| 項目 | 結果 | 費用 |
| --- | --- | --- |
| `--rules-only` 修已存的資料 | 和備份比對 23 筆有變；金額 497 → 472 筆 | 0 |
| 新提示詞評估（57 個來源） | 國籍有根據 82% → 86%、學位 82% → 85%、金額 90% → 92%、截止日 69% → 63%（分母變大） | NT$20.1 |
| 全部重抽 | 249/249 筆，0 失敗 | NT$73.7 |
| extract-14 補救（10 筆） | 芬蘭 3 筆的申請期回來 | NT$3.4 |
| 說明補抽 | 205 筆、384 句，288 句通過（75%） | NT$23.1 |
| 總檢查＋重新檢查 | sub agent 讀原文判斷 | 你的 Claude 用量，約 275 萬 tokens |

Gemini 總共約 NT$120，在每月 NT$7,000 的上限內。

## 4. 影響（同樣 158 筆，重抽前後；`docs/eval/2026-11-14-recheck.md`）

| 欄位 | 重抽前 | 重抽後 |
| --- | --- | --- |
| 截止日 | 57% | 58% |
| 國籍 | 69% | 69% |
| 學位 | 94% | 96% |
| 金額 | 42% | **69%** |

- 錯誤 206 → 156；有錯的筆數 128 → 104。
- 同一筆錢列兩次 40 → 12、漏抽申請期 17 → 8、國籍名單錯 12 → 3。
- 教育部的補件期間現在是「其他時程」，申請期只剩 2/13。
- 26 筆標成「這次不提供」，網頁不再顯示它們的申請期。

**沒變好的**
- 截止日：「非申請期被當成申請期」11 → 28 個。
  - 15 個是自費生的輪次被分類成申請獎學金。
  - 13 個是入學期間，其中 3 筆可能是 extract-14 改錯的。
  - 這次的判斷標準比上次嚴：判斷的是網頁會顯示什麼。
- 上次全對的 30 筆裡，12 筆現在有錯：AI 每次結果不完全一樣，加上新的分類錯。

**對系統行為的影響**
- 以後改提示詞不會自動全部重抽，要自己指定來源。資料庫會有不同版本的資料，每筆的 `meta.prompts` 查得到是哪一版。
- 每天的檢查會多一次說明的 AI 呼叫，只有新來源或原文變了重抽時才會發生，每筆約 NT$0.1。
- `--backfill-amounts`（ADR-074）照舊留著。提示詞版本變了之後，它會把所有資料都當成要補；它不在每天的流程裡，只有手動執行時才會發生。

## 5. 過程中修正的問題

1. `--rules-only` 第一次跑時，在每筆金額多存了 status，179 筆看起來有變，其實 156 筆只是格式不同。已先寫重現的測試再修好。
2. 評估的國名檢查誤報（見 2.2）。
3. 芬蘭、丹麥的入學期間被分類成「只有入學」，7 筆的申請期不見。用 extract-14 補救，但重新檢查顯示其中 3 筆可能本來就是對的（見待決定 2）。
4. `--force` 的測試第一次跑就通過，因為前一步的實作已經處理了 force。照實記在 commit 和計畫裡。

## 6. 待你決定（兩題）

### 6.1 自費生的輪次要不要建成申請期？

- **背景**：
  - 申請期有兩個欄位：`funding`（獎學金生、自費、不限）和這次新加的 `kind`。
  - 自費輪次（例如「第二輪只收自費生」）現在被 AI 分類成 `kind=scholarship`、`funding=self_funded`，全部資料共 36 個。
  - 它們會建成申請期，列表的「還能申請」本來就不算自費的，但詳細頁會列出來。
  - 重新檢查把這 15 個算成錯。
- **現在**：建成申請期，標「自費」（ADR-047 以來的做法）。

| 選項 | 做什麼 | 取捨 |
| --- | --- | --- |
| A 維持 | 自費輪次照樣建成申請期、標「自費」 | 不用改；詳細頁看得到自費的期限；重新檢查會算錯 |
| B 不建申請期 | 程式規則：`funding=self_funded` 就當成 `admission_only`，列在「其他時程」 | 一條規則加測試，`--rules-only` 就能套用、不花錢；自費的期限不會有截止提醒 |

### 6.2 extract-14 那句「申請入學就會一起審核，入學期間也算申請期」要不要保留？

- **背景**：
  - 第一次重抽後，7 筆的入學期間被分類成「只有入學」，申請期不見了。
  - 我加了這句再重抽 10 筆，芬蘭 3 筆（LAB、Metropolia、Savonia）回到申請期。
  - 但重新檢查判定這幾筆的獎學金是入學後才申請（例如修滿 60 學分），第一次總檢查對 Metropolia 也這樣判。
- **現在**：保留 extract-14，那 3 筆有申請期。

| 選項 | 做什麼 | 取捨 |
| --- | --- | --- |
| A 保留 | 不動 | 那 3 筆的入學截止日會出現在列表、會送提醒；如果判斷者對，這些是錯的申請期 |
| B 改回 | 拿掉那句變成 extract-15，只重抽那 3 筆（約 NT$1） | 那 3 筆沒有申請期，只列在「其他時程」；如果入學時其實就會評選，會漏掉提醒 |

兩題都不難回頭：
- 6.1 是一條程式規則。
- 6.2 只牽涉 3 筆資料。
