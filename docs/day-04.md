# 第 4 天：申請期、去重、變更紀錄、封存與預估下一輪

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。依 ADR-039 的方式分階段做，需要使用者決策的部分先暫緩、統整到最後報告。

目標：每筆獎學金的截止日變成「申請期」清單（一屆可以有多個截止日，各附適用對象）；規則去重；資料變更寫進變更紀錄；截止後自動封存並產生下一屆的預估申請期，新的一屆出現時自動喚回。

## 本計畫記錄的決定

- 申請期一屆可以有多筆，各附結構化的適用對象：國籍範圍（ADR-043 格式）＋申請類型（獎學金／自費／不限）＋說明文字（ADR-047）
- 去重第 4 天用規則：官方網址正規化後相同，或提供單位＋名稱正規化後相同；第 5 天加向量（ADR-048）
- 覆寫目前資料，變更紀錄在同一個交易裡寫入（ADR-020）；只記重要欄位：截止日、金額、資格、文件要求（spec）
- 截止後改「已截止」；沒有其他開放中或即將開放的申請期就封存，並依去年日期產生「預估」申請期，預估開放前一個月起每週檢查官網（spec）
- 本月 AI 上限：使用者已在 AI Studio 調高，金額待使用者告知後記成 ADR-049；確認前不跑重抽

## Claude 自行決定（小問題，請事後檢查）

1. 抽取表格的截止日改成「申請窗口」清單（windows），每個窗口有：說明、入學年度、開放日（年月日）、截止日（年月日＋時間＋時區）、適用國籍範圍與國家、申請類型、原文引用；整個獎學金層級的 intake 與截止日欄位移除
2. 時區請 AI 填 IANA 名稱（例如 Europe/Paris、Asia/Taipei）；名稱無效或原文沒寫，就用全世界最早的時區（UTC+14）換算，並標「時區是假設的」：提醒寧可早一點，不要晚
3. 截止時間原文沒寫，就當作當地 23:59
4. 只有截止日年月日齊全的窗口才建成申請期；缺年份的（例如「Mid-February」「1st of March」）留在抽取結果，標待確認，不建申請期
5. 申請期的狀態由程式依日期計算：預估（estimated）、即將開放（upcoming：開放日在未來）、開放中（open）、已截止（closed：截止日已過）；沒有開放日的，截止日還沒到就算開放中
6. 預估下一屆：取最近一屆已截止的申請期，日期全部加一年（2/29 改 2/28），入學年度加一（2026/27 → 2027/28）；「開始重新檢查官網」的日期＝預估開放日前一個月（沒有開放日就用預估截止日前三個月）。排程在第 7 天才接，這裡只算出日期
7. 封存：沒有任何「即將開放」或「開放中」的申請期就封存（預估的不算）；之後重抽出現新的即將開放或開放中的申請期，就喚回（改回使用中）並刪掉那一屆的預估申請期
8. 去重的結果用 scholarships 新欄位 `duplicate_of` 記：重複的那筆保留自己的資料，但指向代表的那筆；代表的那筆取 id 最小的（最早建立的）。之後網頁與評分只看代表的那筆（第 6、9 天）
9. 網址正規化：主機名小寫、去掉開頭的 www.、去掉結尾的 /、去掉錨點、http 視同 https；查詢字串保留
10. 名稱正規化：全形轉半形、不分大小寫、去掉空白與標點
11. 提示詞要求獎學金名稱帶上學程名稱（例如「Erasmus Mundus Scholarship – SuCat」），避免五個學程都叫「Erasmus Mundus Scholarships」
12. 變更紀錄只在「來源內容變了」的重抽才寫：只因為提示詞或模型改版而重抽，原文沒變，就不寫（否則每次改提示詞都會產生一堆假的變更）
13. 文字欄位比對前先正規化（全形半形、空白、大小寫），只差這些的不算變更；清單欄位（學位、國家、文件、申請期）用集合比對，順序不同不算變更
14. 變更紀錄的「對應快照」記這次抽取用到的最新一份快照
15. 申請期的「其他里程碑」（面試、放榜）這次不做，等需要時再加
16. 純函式由兩個 sub agent 平行做（申請期的日期邏輯；去重與變更比對），Claude 做資料表、抽取、驗證、合併與指令

## 待使用者決策

- 本月 AI 上限的新金額，以及是否每個月都用（ADR-049）

## 設計草圖

### 資料表

cycles（新）：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | bigint identity，主鍵 | |
| scholarship_id | bigint，外鍵，必填，連動刪除 | |
| intake | text | 入學年度，例如 2027/28 |
| label | text | 原文的說明，例如「Partner countries」「第一輪」 |
| opens_at | timestamptz | 開放時間（UTC），可空 |
| closes_at | timestamptz，必填 | 截止時間（UTC） |
| timezone | text | 原文的時區（IANA 名稱），可空 |
| timezone_assumed | boolean，必填 | 時區是不是假設的（UTC+14） |
| nationality_scope | varchar(16)，必填 | all／listed／excluded |
| nationalities | text[]，必填 | 國家清單 |
| funding | varchar(16)，必填 | scholarship／self_funded／any |
| status | varchar(16)，必填 | estimated／upcoming／open／closed |
| estimated | boolean，必填 | 是不是程式預估的 |
| recheck_from | date | 預估的申請期從哪天開始每週檢查官網 |
| evidence | text | 原文引用 |

changes（新）：id、scholarship_id（外鍵，連動刪除）、field、old_value（JSONB）、new_value（JSONB）、changed_at、snapshot_id（外鍵，可空）

scholarships 新增：`duplicate_of`（外鍵 scholarships.id，可空）

### 介面（純函式）

```python
# features/scholarships/cycles.py（sub agent A）
def to_utc(year: int, month: int, day: int, time: str | None, timezone: str | None) -> tuple[datetime, bool]
    # 回傳（UTC 時間, 時區是不是假設的）
def cycle_status(opens_at: datetime | None, closes_at: datetime, now: datetime, *, estimated: bool) -> Status
def next_intake(intake: str | None) -> str | None          # 2026/27 → 2027/28
def estimate_next(opens_at, closes_at, intake) -> Estimate  # 日期加一年、recheck_from
def should_archive(statuses: list[Status]) -> bool

# features/scholarships/dedup.py（sub agent B）
def normalize_url(url: str) -> str
def normalize_name(text: str) -> str
def find_duplicates(items: list[Candidate]) -> dict[int, int]   # 重複的 id → 代表的 id

# features/scholarships/changes.py（sub agent B）
def diff_important(old: dict, new: dict) -> list[Change]       # 欄位、舊值、新值
```

### 指令

1. `extract`：存檔時一併重寫抽出來的申請期、寫變更紀錄（原文變了才寫）、喚回
2. `uv run python -m app.features.scholarships.cycles`：更新所有申請期的狀態、封存、產生預估申請期（不呼叫 AI）
3. `uv run python -m app.features.scholarships.dedup`：依規則標記重複（不呼叫 AI）

### 邊界情況

- 窗口缺年份：不建申請期，抽取結果標待確認
- 同一屆完全相同的兩個窗口（日期、對象、類型都一樣）：合併成一個
- 預估的那一屆已經有真的申請期：不再產生預估
- 重複判斷時，代表的那筆後來被刪除：重複的那筆的 duplicate_of 設為空白（外鍵 ON DELETE SET NULL）

### 不在第 4 天範圍

向量去重（第 5 天）、排程與每週檢查（第 7 天）、通知（第 8 天）、網頁（第 9 天）、申請期的其他里程碑

## 測試哪些行為

| 檔案 | 行為 |
| --- | --- |
| test_cycles.py | 時區換算（IANA、沒寫時間當 23:59、時區無效或沒寫用 UTC+14 並標假設）、四種狀態、入學年度加一、預估日期加一年（含 2/29）、recheck_from、封存判斷 |
| test_dedup.py | 網址正規化、名稱正規化、網址相同算重複、提供單位＋名稱相同算重複、不同學程的通用名稱不誤判、代表取 id 最小 |
| test_changes.py | 文字只差空白大小寫不算變更、清單順序不同不算變更、金額變了算變更、申請期日期變了算變更、文件清單少一份算變更 |
| test_merge.py | 長文件的多個窗口合併、完全相同的窗口去重 |
| test_rules.py／test_verify.py | 每個窗口各自檢查年份與引用 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 純函式（sub agent A：申請期）

- [ ] C1 to_utc：IANA 時區換算 -> verify: `uv run pytest tests/test_cycles.py -k iana`
- [ ] C2 to_utc：沒寫時間當 23:59 -> verify: `uv run pytest tests/test_cycles.py -k default_time`
- [ ] C3 to_utc：時區沒寫或無效用 UTC+14 並標假設 -> verify: `uv run pytest tests/test_cycles.py -k assumed`
- [ ] C4 cycle_status 四種狀態 -> verify: `uv run pytest tests/test_cycles.py -k status`
- [ ] C5 next_intake -> verify: `uv run pytest tests/test_cycles.py -k intake`
- [ ] C6 estimate_next：加一年、2/29、recheck_from -> verify: `uv run pytest tests/test_cycles.py -k estimate`
- [ ] C7 should_archive -> verify: `uv run pytest tests/test_cycles.py -k archive`

### 2. 純函式（sub agent B：去重與變更）

- [ ] D1 normalize_url -> verify: `uv run pytest tests/test_dedup.py -k url`
- [ ] D2 normalize_name -> verify: `uv run pytest tests/test_dedup.py -k name`
- [ ] D3 find_duplicates：網址或提供單位＋名稱相同、代表取 id 最小 -> verify: `uv run pytest tests/test_dedup.py -k duplicates`
- [ ] D4 diff_important：只差格式不算、順序不同不算 -> verify: `uv run pytest tests/test_changes.py -k ignores`
- [ ] D5 diff_important：金額、申請期、文件清單的變更 -> verify: `uv run pytest tests/test_changes.py -k detects`

### 3. 抽取格式、合併、驗證（Claude）

- [ ] 既有測試改成新格式（窗口清單；使用者已同意 ADR-047），單獨一個 commit -> verify: `uv run pytest`
- [ ] M1 合併：多個窗口取聯集、完全相同的去重 -> verify: `uv run pytest tests/test_merge.py -k windows`
- [ ] V1 驗證：每個窗口各自檢查年份 -> verify: `uv run pytest tests/test_verify.py -k window_year`

### 4. 資料表與指令

- [ ] 遷移：cycles、changes、duplicate_of -> verify: `uv run alembic upgrade head` 與 `\d cycles`
- [ ] extract 寫申請期、變更紀錄、喚回 -> verify: 重抽教育部與學程 20，貼出申請期
- [ ] cycles 指令 -> verify: `uv run python -m app.features.scholarships.cycles`，貼出各狀態筆數與封存筆數
- [ ] dedup 指令 -> verify: `uv run python -m app.features.scholarships.dedup`，貼出重複筆數

### 5. 實跑（等 ADR-049 的金額）

- [ ] 180 筆重抽 -> verify: extract 輸出統計，`--max-cost` 用使用者給的金額
- [ ] 抽查 10 筆申請期和原網頁比對 -> verify: 貼出比對表（引用看完整，不截斷）

### 6. 收尾

- [ ] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

## 執行時發現

（實作與實跑中遇到的事）
