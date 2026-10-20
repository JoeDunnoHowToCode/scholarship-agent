# 第 6 天：個人資料與評分

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。依 ADR-039 的方式分階段做。

目標：國家全部換成 ISO 國碼並重抽；EACEA 學程用目錄頁當國籍依據；個人資料（國籍、學位必填，其他選填）有 API 和指令可以填；每個（獎學金 × 類別）算出 0–100 分，附硬性條件結果、分項分數與理由。

## 本計畫記錄的決定

- 國家一律存 ISO 3166-1 兩碼國碼，抽取時由 AI 讀上下文填寫，程式用套件檢查（ADR-054）
- EACEA 學程自己網站沒寫國籍時，用目錄頁的說明當依據（ADR-053）
- 評分保留；個人資料必填國籍、想讀的學位，選填目前科系、想讀的領域、想去的國家；硬性條件只看國籍、學位、時間；門檻只顯示；AI 分項四項；送給 AI 的個資只有科系與領域（ADR-055）
- 學位有附加條件算待確認（ADR-046）；依類別評分（ADR-040）；個人資料的資料表有 user_id，第一版固定為 1（ADR-021）

## Claude 自行決定（小問題，請事後檢查）

1. 國碼套件用 pycountry（ISO 3166 的資料，LGPL-2.1 授權）
2. Kosovo 用 XK；顯示名稱由我們自己決定，台灣顯示 Taiwan（之後網頁顯示「台灣」），不用 ISO 的「Taiwan, Province of China」
3. AI 填了不存在的國碼：丟掉，記在驗證結果的 issues（`invalid_country_code:XX`）
4. 國名是否在原文出現的檢查（ADR-045 第 4 條）改成：國碼對應的任一常見名稱出現在原文就算（例如 KR 對應 Korea、South Korea、Republic of Korea）
5. EACEA 學程套用 ADR-053 後，國籍的驗證結果記成 `catalogue`（依據來自目錄頁），網頁與問答顯示依據來源
6. 時間條件：
   - 只看「適用你的國籍、申請類型是獎學金或不限」的申請期
   - 其中有開放中或即將開放、而且驗證通過的 → 符合
   - 有開放中或即將開放，但驗證沒過 → 待確認
   - 只有預估的下一屆 → 待確認
   - 適用你的都已截止、也沒有預估 → 不符合
   - 有申請期但沒有一個適用你的國籍 → 不符合；完全沒有申請期 → 待確認
7. 學位條件：想讀的學位不在類別清單裡 → 不符合；清單是空的 → 待確認；在清單裡，但學位條件文字提到這個學位（例如條件寫「碩士限藝術學群」、想讀碩士）→ 待確認；其他 → 符合
8. 分項權重：領域契合 40%、補助價值 27%、時程可行 20%、競爭與名額 13%；沒填科系與領域時不評領域契合，其他三項依比例放大到 100%
9. 送給 AI 評分的資料：獎學金的名稱、提供單位、國家、領域、補助內容與金額、這個類別的名額與學位、適用你的申請期日期；你的科系與想讀的領域。不送語言與成績門檻（ADR-055：門檻不拿來評分），不送國籍
10. 硬性條件每次評分都由程式重算（不花錢，申請期狀態每天會變）；AI 分項只有在「個人資料版本、獎學金內容、提示詞版本、模型」任一改變時才重算
11. 所有代表的獎學金（排除 duplicate_of 有值的）都評分，包括封存的；封存的通常因為時間條件是待確認或不符合而分數較低，但仍列出（spec：全部列出、不過濾）
12. 個人資料每次修改，版本號加一
13. API：`GET /api/profile`、`PUT /api/profile`、`GET /api/matches`；資料表類別和 API 用的 Pydantic 模型分開（CLAUDE.md 程式規範）；存取個人資料的函式都要 user_id 參數
14. 指令：`profiles.set` 填個人資料、`matching.score` 評分、`matching.top` 列出前幾名
15. 先用 spec 寫的條件（台灣籍、申請碩士）建一份個人資料來測試；科系與領域請使用者自己用指令填，填完再重新評分
16. 純函式由兩個 sub agent 平行做（國碼；硬性條件與權重），Claude 做抽取改動、資料表、API、指令與實跑

## 待使用者決策

（目前沒有）

## 設計草圖

### 資料表

profiles（新）：id、user_id（唯一）、nationality（char(2)）、target_degree（bachelor／master／phd）、current_major（text，可空）、target_fields（text[]）、target_countries（char(2)[]）、version（int）、updated_at

matches（新）：id、user_id、scholarship_id（外鍵，連動刪除）、category_id（外鍵，連動刪除）、total（numeric）、cap（20、80 或空白）、checks（JSONB：國籍、學位、時間各自的結果與原因）、sub_scores（JSONB：四項分數與理由）、unclear（text[]）、failed（text[]）、model、prompt_version、profile_version、scholarship_hash、computed_at；（user_id, category_id）唯一

### 介面（純函式）

```python
# features/scholarships/countries.py（sub agent A）
def valid_code(code: str) -> str | None             # 不存在就回傳 None；XK 算存在
def clean_codes(codes: list[str]) -> tuple[list[str], list[str]]   # （有效的, 無效的）
def display_name(code: str) -> str                  # TW → Taiwan
def names_for(code: str) -> list[str]               # 用來檢查原文有沒有提到這個國家

# features/matching/checks.py（sub agent B）
def nationality_check(user: str, scope: str, codes: list[str]) -> CheckResult
def applicable(cycles: list[CycleInfo], user: str) -> list[CycleInfo]
def time_check(cycles: list[CycleInfo], user: str) -> CheckResult
def degree_check(target: str, degrees: list[str], conditions: str | None) -> CheckResult
def weighted_total(scores: dict[str, float | None]) -> float
```

### 指令

1. `extract`（重抽 180 筆）→ `extract --cycles-only` 不需要（抽取時就寫申請期）→ `cycles` → `dedup` → `search.index`
2. `uv run python -m app.features.profiles.set --nationality TW --degree master [--major 文字] [--field 文字 …] [--country FR …]`
3. `uv run python -m app.features.matching.score [--max-cost NT$]`
4. `uv run python -m app.features.matching.top [--limit 20]`

### 不在第 6 天範圍

網頁表單（第 9 天）、通知（第 8 天）、排程（第 7 天）

## 測試哪些行為

| 檔案 | 行為 |
| --- | --- |
| test_countries.py | 國碼有效與無效、XK、大小寫、清理清單、顯示名稱、常見別名 |
| test_matching_checks.py | 國籍三種範圍與待確認、適用的申請期、時間條件各情況、學位條件各情況、權重與缺項時依比例調整 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 套件

- [ ] 加入 pycountry -> verify: `uv pip show pycountry | head -2`

### 2. 純函式（紅綠循環）

- [ ] K1 國碼有效與無效（含 XK、大小寫） -> verify: `uv run pytest tests/test_countries.py -k valid`
- [ ] K2 清理國碼清單 -> verify: `uv run pytest tests/test_countries.py -k clean`
- [ ] K3 顯示名稱與常見別名 -> verify: `uv run pytest tests/test_countries.py -k names`
- [ ] M1 國籍條件 -> verify: `uv run pytest tests/test_matching_checks.py -k nationality`
- [ ] M2 適用的申請期與時間條件 -> verify: `uv run pytest tests/test_matching_checks.py -k time`
- [ ] M3 學位條件 -> verify: `uv run pytest tests/test_matching_checks.py -k degree`
- [ ] M4 權重與缺項 -> verify: `uv run pytest tests/test_matching_checks.py -k weighted`

### 3. 國碼與 EACEA 依據（Claude）

- [ ] 抽取表格的國家欄位改成國碼、Erasmus+ 33 國改成國碼、抽完清理無效國碼 -> verify: `uv run pytest && uv run mypy app`
- [ ] EACEA 學程的國籍依據（ADR-053） -> verify: 重抽後 `nationality_scope` 的分布
- [ ] 180 筆重抽、cycles、dedup、index -> verify: 貼出統計與費用

### 4. 個人資料與評分（Claude）

- [ ] 遷移：profiles、matches -> verify: `uv run alembic upgrade head` 與 `\d matches`
- [ ] 個人資料 API 與指令 -> verify: `curl` 讀寫 /api/profile
- [ ] 評分指令 -> verify: 貼出評分筆數、各上限的筆數、費用
- [ ] 再跑一次評分，AI 分項全部沿用 -> verify: 貼出「沿用 N、重算 0」
- [ ] 前 10 名與抽查 -> verify: 貼出前 10 名與 3 筆的理由

### 5. 收尾

- [ ] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

## 執行時發現

（實作與實跑中遇到的事）
