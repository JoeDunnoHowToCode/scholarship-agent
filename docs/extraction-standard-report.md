# 抽取標準 v1：完整報告（2026-11-16 至 11-17）

- **計畫**：`docs/extraction-standard-plan.md`（檢查表都附了指令輸出；「Claude 自行決定」共 20 點）
- **標準**：`docs/extraction-standard.md`
- **決定**：ADR-107（17 題）、ADR-108（一頁拆成多筆）、ADR-109（國家群組）、ADR-110（推算年份）
- **量測**：
  - 評估：`docs/eval/2026-11-16.md`
  - 依標準重新檢查：`docs/eval/2026-11-17-standard.md`
- **最後檢查**：
  - 後端 `387 passed`、ruff `All checks passed!`、mypy `no issues found in 125 source files`
  - 前端 `✓ built`
  - 全部推上 main

## 1. 一開始的目標

- **你的問題**（11-16）：抽下來的資料一定要是對的，為什麼還會錯？
- **我的回答**：很多錯不是 AI 讀錯字，而是「什麼才算對」沒有定義。所以提示詞、程式規則、檢查的判斷者各猜各的，同一筆資料就會被判成錯。
- **你的決定**：
  - 先把標準定好
  - 我列出 17 個定義不清楚的地方，你逐題選了 A1 C … F1 B
  - 審核加重抽的流程等標準做完、量過再決定
- **這次的目標**：
  - 照 17 題的選擇，改提示詞、schema、程式規則與資料模型
  - 量一次效果，並把過程中發現的問題修好

## 2. 整體功能（做完之後系統怎麼運作）

1. 每天抓到網頁後，AI 照新版提示詞（extract-15／16）抽一次主角，同時列出「同一頁還有哪些有自己金額或申請期的獎學金」。列出來的每一個，再用 `focus-1` 各抽一次，存成自己的一筆。
2. 程式規則（不花錢）：
   - 兩群人金額一樣就合併
   - 原價減實付的差額算有依據
   - 百分比要在引用裡
   - 國家群組展開成國碼
   - 沒寫年份的截止日推算下一次，標「年份推估」，照常提醒
3. 核對：「不是獎學金」也要通過核對的 AI。通過了才停用來源、封存獎學金，並列在每日報告；判斷改回來會自動恢復。
4. 網頁的詳細頁：
   - 百分比顯示成「減免 50%」
   - 期間「第一年」
   - 學位「其他」
   - 下一屆說明
   - 不提供時，說明與補助的標題標「過去的資訊」
   - 年份推估的申請期標「年份推估」

## 3. 修改前後（重點程式碼）

### 3.1 段 1：程式規則

**兩群人金額一樣就合併**（`merge.py`，C5 A）

```python
# 修改前
def clean_amounts(amounts):
    return rules.redundant_totals(merge_amounts([amounts]))

# 修改後：多一步 merge_groups；兩筆都寫了適用對象、其他都一樣，就合成一筆，適用對象用「、」接起來
def clean_amounts(amounts):
    return merge_groups(rules.redundant_totals(merge_amounts([amounts])))
```

**差額算有依據**（`amounts.py`，C2 A）

```python
# 修改前：數字一定要出現在引用裡
if not any(math.isclose(number, amount.value) for number in numbers_in(amount.evidence)):
    return "number_not_in_quote"

# 修改後：引用裡兩個數字的差也算（原價 18,000、實付 13,500 → 存 4,500）
numbers = numbers_in(amount.evidence)
differences = {a - b for a in numbers for b in numbers if a > b}
if amount.value is None or not any(math.isclose(n, amount.value) for n in numbers | differences):
    return "number_not_in_quote"
```

**沒寫年份的日期**（`extract.save_cycles`、`cycles.next_year`，B3 B、ADR-110）

```python
# 修改前：年月日不齊全就不建申請期（這類日期永遠沒有申請期、沒有提醒）
if status in ("incomplete", "year_not_in_quote"):
    continue

# 修改後：只有月日、沒有年份 → 取今天以後最近的那一天，verification="year_inferred"，estimated 照舊 False（照常提醒）
inferred = status == "incomplete" and not window.closes_year and bool(window.closes_month and window.closes_day)
if status in ("incomplete", "year_not_in_quote") and not inferred:
    continue
closes_year = window.closes_year or cycles.next_year(window.closes_month, window.closes_day, now.date())
```

- 通知和網頁的申請期文字：「（開放中，年份推估）」。原本會顯示「截止日未核對」（`score.describe_cycle`）。
- `--rules-only`：
  - 改成每筆都重建申請期，規則改了也能套到舊資料
  - 兩群人合併後的那筆金額不能丟。原本用「是不是同一個物件」判斷，合併後的會被丟掉；已先寫重現測試再修。

### 3.2 段 2：schema 加欄位

```python
# 修改前
Degree = Literal["bachelor", "master", "phd"]
AmountPeriod = Literal["month", "year", "total", "once", "unclear"]
value: float

# 修改後（schemas.py）
Degree = Literal["bachelor", "master", "phd", "other"]                       # F1 B
AmountPeriod = Literal["month", "year", "total", "once", "first_year", "unclear"]  # C4 C
value: float | None          # 只寫百分比時留空
percent: float | None = None # C1 B
# ScholarshipDraft、Outline
next_cycle_note / next_cycle_evidence    # B1 B
not_scholarship / not_scholarship_evidence  # A2 C
# ScholarshipDraft、各節、申請期
nationality_groups: list[str] = []       # D1 C、ADR-109
```

所有新欄位都有預設值，舊資料不用重抽也照舊運作。

**國家群組**（新模組 `groups.py`）
- 清單與官方出處（2026-11-16 查證）：
  - 歐盟 27 國
  - EEA 30 國
  - Erasmus+ Programme 33 國
  - 非洲聯盟 55 國
  - 西巴爾幹 4 國
- 存檔時展開成國碼。
- Erasmus+ Partner 換成「排除 Programme countries」。
- 不認識的群組，國籍標待確認。

**不是獎學金**（`extract.py`、`verify.py`、`pipeline/report.py`）

```python
# 修改前：頁面沒有獎學金也照樣存成一筆、每天檢查
# 修改後：AI 判斷不是獎學金 → 和其他欄位一起交給核對的 AI（引用要在原文裡，而且撐得起
# 「完全不提供，不是只有這一屆沒有」）→ 通過才停用來源、封存獎學金、列在每日報告
if status.get("not_scholarship") == "supported":
    disable_not_scholarship(source, row, verified.not_scholarship_evidence or "")
# 判斷改了（之前是程式停用的）→ 自動打開
if (source.review_note or "").startswith(NOT_SCHOLARSHIP_NOTE):
    source.enabled, source.disabled_at, source.review_note = True, None, None
```

**提示詞**：
- extract-14 → 15 → 16、section-14 → 15、outline-9 → 10 → 11
- 新增 `focus-1`
- 標準的每一條都寫進去
- extract-14 那句「申請入學就會一起審核」照你的決定（2A）保留

### 3.3 段 3：一頁拆成多筆（ADR-108）

```python
# 修改前（models.py）：一個來源只能有一筆
source_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sources.id"), unique=True)

# 修改後：唯一的是（source_id, key）；主角固定是 main
__table_args__ = (UniqueConstraint("source_id", "key", name="scholarships_source_id_key_key"),)
source_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sources.id"))
key: Mapped[str] = mapped_column(Text, server_default="main")
```

- **遷移** `0ed701dc7733`：新增 `key`（既有 249 筆都是 main）、拿掉舊的唯一限制、加新的。套用前讀過，沒有誤判成刪除再新增。
- **抽取**：主角照舊；同一頁的其他獎學金最多再抽 5 個。下面兩種不存：
  - 頁面沒有寫它自己的金額或申請期
  - 頁面上不再出現的：封存、拿掉申請期、標 `gone`，不通知，`--rules-only` 跳過
- **假設一個來源一筆的地方**：28 處 `source_id ==` 都看過了，計畫的檢查表有逐處說明。其中要改的地方：
  - 每天的檢查只排一次
  - 候選任一筆通過就加入
  - 每一筆都建向量、都補說明
  - 去重只拿主角比網址
  - 候選的重複比對排除同一來源

## 4. 執行結果

| 項目 | 結果 |
| --- | --- |
| 評估 57 個來源 × 2 次（extract-15） | 國籍有根據 86% → 97%、學位 85% → 86%、截止日 63% → 64%、金額 92% → 91%；沒有觸發停止條件 |
| 全部重抽（extract-15） | 256 個來源完成、0 失敗；第 0 份碰到費用上限，剩下 4 個 |
| 收緊後補抽（extract-16） | 122 個來源（有拆分的 102 個、被停用的 16 個、剩下的 4 個） |
| 不是獎學金而停用 | 16 → 7 → 1（#142，判錯，見 6.2） |
| 拆出來的其他獎學金 | 235 → 150 → 108 筆（程式擋掉沒有金額也沒有申請期的） |
| 申請期「年份推估」 | 32 個 |
| 獎學金說明補抽 | 239 筆、0 失敗，NT$26.7 |
| 依標準重新檢查 200 筆 | 見第 5 節 |
| 用重新檢查的結果再修一輪（extract-17） | 52 個來源、0 失敗，NT$20.1；同樣 51 筆錯誤 89 → 50 |
| #142 | 程式誤停用，已重新打開，並用 extract-17 重抽 |

## 5. 影響（同樣 158 筆，`docs/eval/2026-11-17-standard.md`）

| 欄位 | 11-14 | 11-17 |
| --- | --- | --- |
| 截止日 | 59% | **74%** |
| 國籍 | 76% | 81% |
| 學位 | 97% | 94% |
| 金額 | 69% | **57%** |
| 今年有沒有開 | 沒有判 | 86% |

- **截止日變好**：非申請期被當成申請期 28 → 6 個。
- **金額變差**：
  - 主因是標準比上次嚴，AI 沒照新規則做：參與費用要存成學費補助 10 個；全額免學費要存成 100% 有 8 個。
  - 另外，其他獎學金的錢還混在主角裡，約 7 個。
- **今年有沒有開**：約 10 個是原文明寫「這一屆沒有」，AI 卻填 yes。
- **拆出來的 42 筆**：國籍 76%。其中 6 個錯是程式借用了 Erasmus 目錄頁的國籍，已修，已存的 148 筆也改回「不清楚」。

**再修一輪（extract-17，51 筆）**
- 錯誤 89 → 50：
  - 排除瑞士的國籍名單錯 12 → 0
  - 參與費用與 100% 免學費漏抽 24 → 7
  - offered 17 → 12，還沒解決，見 8.3

**對系統行為的影響**
- 每天的檢查：
  - 有拆分的頁面，每個其他獎學金多一次 AI 呼叫，約 NT$0.15
  - 拆出來的獎學金會各自評分、通知
  - 今天（11-17）收尾時可能會有一批「新獎學金」通知，對象是 108 筆裡分數過門檻的
- 不是獎學金而停用的來源，每天的報告會列出。判斷錯的話，在設定頁重新打開。
- 年份推估的申請期會送截止提醒，提醒裡寫「年份推估」。
- 學位 `other` 在評分裡不符合任何想讀的學位，個人資料與篩選照舊。

## 6. 過程中發現並修正的問題

1. **評估時 4 次 `KeyError: 'other'`**：學位加了 `other`，程式的學位關鍵字表沒有。先寫重現測試再修。
2. **「不是獎學金」判斷太鬆**：16 個被停用，多半是「這一屆沒有」或壞掉的網頁，例如網域過期、維護中、機器人驗證。修了三層：
   - 提示詞寫清楚
   - 核對的 AI 也要判斷
   - 判斷改回來會自動打開
3. **拆分太多**：235 筆，多半是頁面上「其他資助管道」的外部連結。修了兩層：
   - 提示詞寫清楚
   - 程式規則：沒有自己的金額或申請期就不存
4. **每天的 `refresh` 會喚回沒有申請期的已封存獎學金**：和註解寫的不一樣，否則「不是獎學金」封存的隔天就回來。
5. **網址去重會把同一頁拆出來的獎學金全部標成重複**：改成只有主角比網址。
6. **已封存（`gone`）的獎學金照樣會發「新獎學金」通知**：每天的檢查會在收尾時發出 235 則，在它開始之前先修好了。

## 7. 沒照流程做的地方（請事後檢查）

1. **兩次改了測試，沒先問你**：這次是無人值守地跑完整個計畫，所以沒辦法先問。兩次都另開 commit，訊息寫了原因：
   - `test_schemas`：我在紅燈測試裡要求 `Outline` 有國籍群組，但 `Outline` 本來就沒有國籍欄位。
   - `test_multi_scholarship_db`：新規則「沒有金額也沒有申請期就不存」讓舊測試的假資料不成立，加了一筆金額。
2. **有一個 commit 在測試失敗時送出**（`2f83068`）：那次的指令沒有設定 `pipefail`。下一個 commit 修好了，commit 訊息有寫。
3. **兩次紅燈測試第一次就通過**：
   - 一次是資料庫照 `key` 排序，碰巧拿到對的那筆。改了測試用的名稱，重跑確認會失敗後才 commit。
   - 一次是推算年份的日期本來就被擋掉。另外補了正確的測試，並暫時拿掉修正，確認它會失敗；這個是先修再補測試，順序不對。
4. **兩次執行錯誤**：
   - 重抽分片的編號從 0 開始，我用了 1 到 3，第 0 份沒跑到，之後補跑。
   - 一次 `split` 參數在 macOS 不支援，兩個程序在沒有指定來源的情況下啟動，等於全部重抽。2 秒內就停掉了，沒有寫入資料。
5. **想暫停每日檢查的 worker 被權限擋下**：我沒有繞過，改用程式修正，也就是第 6 節第 6 點。
6. **費用超過計畫**：計畫估 Gemini NT$140–170，實際約 NT$243。多出來的是兩次補抽（extract-16、不是獎學金），以及同一頁其他獎學金的抽取（`focus` 約 NT$61）。本月合計約 NT$600，上限 NT$7,000。

## 8. 待你決定

### 8.1 自費輪次要算申請期，還是「只有入學」？（標準 1.3 和 2.4 重疊）

- **背景**：
  - 標準 1.3（你 11-16 選 1A）：自費輪次照樣是申請期（`funding=self_funded`）。
  - 標準 2.4（B4 A）：「原文寫明這段期間拿不到這個獎學金」算只有入學。
  - 自費輪次兩條都符合，所以 AI 有時分成申請期、有時分成只有入學，判斷者兩種都判對。

| 選項 | 做什麼 | 取捨 |
| --- | --- | --- |
| A 以 1.3 為準 | 標準 2.4 加一句「自費輪次除外」，提示詞跟著改 | 詳細頁看得到自費的期限；要重抽有自費輪次的來源才會一致 |
| B 以 2.4 為準 | 標準 1.3 改成自費輪次算只有入學，列在「其他時程」 | 自費的期限沒有截止提醒；程式規則就能套用（`funding=self_funded` 就當成只有入學），不花錢 |

### 8.2 標準沒有涵蓋的情況（標準 v2）

- 9 題已經像 11-16 那樣，一題一題列好選項：`docs/definitions-decisions-v2.md`。
- 8.1 的自費輪次就是其中的 G1。
- 回覆格式和上次一樣，例如「G1A G2C …」。

### 8.3 下一步：審核加重抽的流程（11-16 說好量過再決定）

- **背景**：
  - 這次量到的錯，很多是「AI 沒照規則做」：參與費用、100% 免學費、這一屆沒有卻填 yes。
  - 規則已經寫在提示詞裡了，再改提示詞的效果有限。
  - 11-16 列過三種做法：
    - A：只標出來給你看
    - B：程式檢查出問題就把錯誤拋回給 AI 重抽一次
    - C：另一個 AI 審核後再重抽

這題要決定的東西比較多，而且不好回頭，建議用 `/decision-brief` 做完整比較。

### 8.4 #142 被誤停用（已處理）

- 原文只說「這一屆只收自費生」，照標準是 `offered=no`，不是「不是獎學金」。
- 程式誤判後，我已經重新打開來源，並用 extract-17 重抽；這次沒有再被停用。

## 9. 費用

- **Gemini**（`llm_calls`，11-16 22:30 起）：約 NT$268（extract-17 補修 20.1、補說明 4.5），不含每日檢查自己的呼叫。
  - 抽取 107、其他獎學金 61、分節 26、說明 26、大綱 10、核對 9、其他 4
  - 包含評估 NT$35.8
- **Claude**：
  - 依標準重新檢查：7 個 sub agent 約 113 萬 tokens；extract-17 後再檢查：2 個約 30 萬 tokens
  - 查國家群組清單：約 7 萬 tokens
  - 都是 effort medium

## 附錄：「Claude 自行決定」26 點的驗證證據

在 `backend/` 執行，11-17 跑過的結果附在後面。「—」代表那一點是數字、流程或文件，沒有對應的測試，證據寫在說明欄。

| # | 決定（計畫的編號） | 證據 |
| --- | --- | --- |
| 1 | 推算年份用 `year_inferred`，照常提醒 | `test_save_cycles_db.py`、`test_notification_rules.py -k inferred`：2 passed；本機 32 個申請期 |
| 2 | 學位 other 不符合想讀的學位 | `degree_check` 只認使用者的學位（未改）；`test_rules.py -k other`：1 passed |
| 3 | EACEA 目錄的學程照樣停用 | — 查過 `catalogue.py` 不動 `enabled` |
| 4 | 群組清單放在程式裡 | `test_groups.py`：3 passed；`groups.py` 附官方出處 |
| 5 | 其他獎學金名稱相似度 ≥ 0.9 算同一筆 | `test_multi_scholarship_db.py`（Regional Grant／Grants）：7 passed |
| 6 | 段 3 排最後 | — 執行順序 |
| 7 | 停止條件（低 5 個百分點就停） | — 評估沒有觸發，`docs/eval/2026-11-16.md` |
| 8 | AI 自己補的年份不推算 | `save_cycles` 只推算 `incomplete`（`test_save_cycles_db.py`） |
| 9 | 年份推估在評分裡算未核對 | — `score.py` 的 `verified` 只認 supported（未改） |
| 10 | 兩群合併只在都寫了適用對象時 | `test_merge.py -k same_amount`：1 passed |
| 11 | `--rules-only` 每筆都重建申請期 | `test_rules_recheck_db.py`：5 passed |
| 12 | 不另外呼叫「列出獎學金」 | `test_multi_scholarship_db.py`（假 AI 主抽取順便列出） |
| 13 | 主角 key 固定 main | `test_multi_scholarship_db.py -k main_scholarship`；遷移後 `\d scholarships` |
| 14 | 一頁最多另外抽 5 個、長文件不拆 | — `MAX_OTHERS`、`mode == "whole"` |
| 15 | 不在頁面上的封存、標 gone | `test_multi_scholarship_db.py`、`test_rules_recheck_db.py`（gone 兩個） |
| 16 | 不是獎學金也封存獎學金 | `test_not_scholarship_db.py`：5 passed |
| 17 | refresh 只在有申請期時喚回 | `test_not_scholarship_db.py -k recall` |
| 18 | 只有主角比網址；候選排除同一來源 | `test_dedup.py -k same_page`、`test_candidates_db.py -k own_page`：各 1 passed |
| 19 | 學位 other 只在顯示時叫「其他」 | 瀏覽器確認 #1125「學位：碩士、其他」 |
| 20 | 評估上限 NT$48 | — 兩輪都跑完，NT$35.82 |
| 21 | 不是獎學金也交給核對 AI | `test_verify.py -k not_scholarship`：1 passed；停用 16 → 1 |
| 22 | 沒有自己的金額或申請期不存 | `test_multi_scholarship_db.py -k without_amounts`；拆分 150 → 108 |
| 23 | 程式停用的來源判斷改了自動打開 | `test_not_scholarship_db.py -k reenabled` |
| 24 | gone 不通知 | `test_generate_db.py -k gone`：1 passed |
| 25 | 目錄國籍只給主角 | `test_multi_scholarship_db.py -k catalogue`；已存的 148 筆改回不清楚 |
| 26 | 重新檢查只抽 42 筆拆分資料 | — 固定亂數 20261117，`standard-2026-11-16/ids.json` |
