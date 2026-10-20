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
17. 評分表的唯一鍵是（user_id, scholarship_id, category_name）：類別存在獎學金的 extracted 欄位裡，沒有自己的資料表，所以草圖原本寫的 category_id 外鍵做不到；重抽後類別改名或刪掉，評分指令會刪掉對不上的舊評分
18. AI 分項沿用與否看「送出內容」的雜湊（模型、提示詞版本、獎學金資料、科系與領域），不含今天的日期（spec 評分第 4 點：只有個人資料或獎學金內容變動才重算）；改想去的國家這類不送給 AI 的欄位不會重算 AI。這一點取代第 10 點的「個人資料版本」
19. 硬性條件的原因用中文寫（開放中、碩士、不限國籍……）；時間條件的原因分成五種：原文沒有截止日／有截止日但年份或日期不完整（第 4 天不建申請期的窗口）／有截止日但都不適用你／適用你的都已截止／適用你的截止日（先列驗證通過的那個）
20. 送給 AI 的截止日只列適用你、還沒截止的前 4 個；一個都沒有時改送時間條件的原因，讓 AI 分得出「沒有截止日」和「都截止了」
21. 評分指令的 Session 設 `expire_on_commit=False`：每筆獎學金 commit 後不把讀進來的資料標成過期，下一筆才不會重新查資料庫（避免 N+1）
22. FastAPI 的資料庫依賴寫成 `Annotated[Session, Depends(get_session)]`（ruff 的 B008 規則不允許在參數預設值呼叫函式）
23. 子 agent B 用突變測試（故意把規則改錯 11 種方式）找到 4 種測試抓不到的改法，補成保護測試；程式本來就對，所以測試直接通過，commit 訊息有註明
24. EL→GR、UK→GB 的國碼對應做了又撤回：唯一的 EL 來自一個原文完全沒提到希臘的學程，是 AI 填錯；保留對應會把「有紀錄的丟棄」變成「無聲的錯誤國家」。之後真的有來源用 EL 寫希臘再加
25. 新增 `.claude/launch.json`，讓 Claude 桌面版的預覽可以啟動 API（`uv run --directory backend uvicorn app.main:app`）
26. 國籍有限制（只限列出的國家、或列出的國家以外）卻沒有國家清單時，算待確認，不算不符合：例如「for non-European applicants」「African Union 會員國」，AI 沒列出國家。國家集合怎麼存另外決定（#52）
27. 時間條件改看「還有機會申請」的申請期：給申請獎學金的人、國籍符合或待確認、還沒截止（含預估）；其中有確定適用你、開放中或即將開放、截止日核對過的才算符合（取代第 6 點的「有申請期但沒有一個適用你的國籍 → 不符合」只看確定適用的寫法）
28. 申請期的說明寫了 Erasmus+ 的 Partner／Programme countries，一律用程式的 33 國清單（第 4 天原本只在 AI 沒給清單時才補）；目前的資料只改到學程 65
29. 只有自費生的申請期 → 時間不符合，原因寫「只找到自費生的申請期，沒有獎學金的截止日」（Global-MINDS 原文確認 2027 年起只收自費生）
30. 評分提示詞 score-2：寫明「分數越高代表對申請人越有利」「名額越多、競爭越小，分數越高」；score-1 沒寫方向，同樣名額 4 名的競爭分數從 3 到 8 都有
31. AI 的分項分數一定要是數字（score-3）：資料沒寫或無法判斷時給 5 分並說明；只有沒填科系與領域時，由程式把領域契合設成不評、其他依比例放大（spec 評分第 3 點）。空白分數會被加權總分跳過、其他項放大，等於把「不知道」當成「和其他項一樣好」

## 待使用者決策

第 6 天的功能都不受影響，以下是實跑時新發現的題目，已加進 `docs/adr.md` 的待決定清單：

- #51 預估的下一屆落在過去：怎麼處理資料過舊的來源（第 7 天前）
- #52 國家集合（EU、EEA、African Union）怎麼存（公開版前）
- #53 時程與名額分數由 AI 評還是程式算：時程理由會過時、名額分數不一致（第 7 天前）

## 設計草圖

### 資料表

profiles（新）：id、user_id（唯一）、nationality（char(2)）、target_degree（bachelor／master／phd）、current_major（text，可空）、target_fields（text[]）、target_countries（char(2)[]）、version（int）、updated_at

matches（新）：id、user_id、scholarship_id（外鍵，連動刪除）、category_name（類別名稱，見「Claude 自行決定」第 17 點）、total、cap（20、80 或空白）、checks（JSONB：國籍、學位、時間各自的結果與原因）、sub_scores（JSONB：四項分數與理由）、unclear（text[]）、failed（text[]）、model、prompt_version、profile_version、input_hash（送給 AI 的內容的雜湊，第 18 點）、computed_at；（user_id, scholarship_id, category_name）唯一

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
| test_matching_checks.py | 國籍三種範圍與待確認、適用的申請期、時間條件各情況、學位條件各情況、權重與缺項時依比例調整；實跑後補：沒有國家清單、國籍不明的申請期、突變測試的保護 |
| test_rules.py | 實跑後補：Partner／Programme countries 一律用固定清單 |
| test_matching_score.py | 填了科系後補：AI 的分項分數一定要是數字 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 套件

- [x] 加入 pycountry -> verify: `uv pip show pycountry | head -2`

  ```
  Name: pycountry
  Version: 26.2.16
  ```

### 2. 純函式（紅綠循環）

- [x] K1 國碼有效與無效（含 XK、大小寫） -> verify: `uv run pytest tests/test_countries.py -k valid`

  ```
  1 passed, 2 deselected in 0.02s
  ```
- [x] K2 清理國碼清單 -> verify: `uv run pytest tests/test_countries.py -k clean`

  ```
  1 passed, 2 deselected in 0.02s
  ```
- [x] K3 顯示名稱與常見別名 -> verify: `uv run pytest tests/test_countries.py -k names`

  ```
  1 passed, 2 deselected in 0.02s
  ```
- [x] M1 國籍條件 -> verify: `uv run pytest tests/test_matching_checks.py -k nationality`

  ```
  1 passed, 4 deselected in 0.03s（實跑後補了 M5，現在是 2 passed）
  ```
- [x] M2 適用的申請期與時間條件 -> verify: `uv run pytest tests/test_matching_checks.py -k time`

  ```
  1 passed, 4 deselected in 0.03s（實跑後補了 M6，現在是 2 passed）
  ```
- [x] M3 學位條件 -> verify: `uv run pytest tests/test_matching_checks.py -k degree`

  ```
  1 passed, 4 deselected in 0.03s
  ```
- [x] M4 權重與缺項 -> verify: `uv run pytest tests/test_matching_checks.py -k weighted`

  ```
  1 passed, 4 deselected in 0.03s
  ```

實跑後發現的規則漏洞（「執行時發現」第 8、9 點），同樣紅綠循環：

- [x] G1 突變測試找到的 4 個漏洞（保護測試，直接通過） -> verify: `uv run pytest tests/test_matching_checks.py -k mutation`

  ```
  1 passed, 6 deselected in 0.03s
  ```
- [x] M5 國籍有限制但沒有國家清單 → 待確認 -> verify: `uv run pytest tests/test_matching_checks.py -k without_a_country_list`

  ```
  1 passed, 6 deselected in 0.03s
  ```
- [x] M6 國籍不明、還沒截止的申請期 → 時間待確認 -> verify: `uv run pytest tests/test_matching_checks.py -k unknown_nationality`

  ```
  1 passed, 6 deselected in 0.03s
  ```
- [x] R1 Partner／Programme countries 一律用固定的 33 國清單 -> verify: `uv run pytest tests/test_rules.py -k window_nationality`

  ```
  1 passed, 7 deselected in 0.03s
  ```
- [x] S1 AI 的分項分數一定要是數字（「執行時發現」第 12 點） -> verify: `uv run pytest tests/test_matching_score.py`

  ```
  1 passed in 0.66s
  ```

### 3. 國碼與 EACEA 依據（Claude）

- [x] 抽取表格的國家欄位改成國碼、Erasmus+ 33 國改成國碼、抽完清理無效國碼 -> verify: `uv run pytest && uv run mypy app`

  ```
  107 passed in 1.27s
  All checks passed!
  Success: no issues found in 62 source files
  ```
- [x] EACEA 學程的國籍依據（ADR-053） -> verify: 重抽後 `nationality_scope` 的分布

  ```
   nationality_scope |   basis   | count
  -------------------+-----------+-------
   all               | supported |    88
   all               | catalogue |    88
   listed            | supported |     3
   excluded          | supported |     1
   unclear           |           |     1   ← 第 1 天的測試資料（沒有來源，不評分）
  ```
- [x] 180 筆重抽、cycles、dedup、index -> verify: 貼出統計與費用

  ```
  完成 33、沒變 0、失敗 0｜約 US$0.186（NT$5.9）
  完成 50、沒變 2、失敗 0｜約 US$0.308（NT$9.8）
  完成 47、沒變 1、失敗 0｜約 US$0.285（NT$9.1）
  完成 47、沒變 0、失敗 0｜約 US$0.286（NT$9.2）
  申請期：開放中 57、即將開放 33、已截止 88、預估 0
  這次封存 4 筆、喚回 1 筆、新增預估申請期 79 筆
  180 筆獎學金，其中 0 筆是重複：無
  向量相似度 ≥ 0.95 的可能重複：0 對
  段落：沿用 6135、重算 0；表格 347；獎學金向量重算 178；失敗 0
  ```

### 4. 個人資料與評分（Claude）

- [x] 遷移：profiles、matches -> verify: `uv run alembic upgrade head` 與 `\d matches`

  ```
  $ uv run alembic current
  f64bbe6d16f0 (head)
  \d matches
   id | user_id | scholarship_id | category_name | total | cap | checks (jsonb) | sub_scores (jsonb)
   unclear text[] | failed text[] | model | prompt_version | profile_version | input_hash | computed_at
  "matches_user_id_scholarship_id_category_name_key" UNIQUE CONSTRAINT, btree (user_id, scholarship_id, category_name)
  "matches_scholarship_id_fkey" FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE
  ```
- [x] 個人資料 API 與指令 -> verify: `curl` 讀寫 /api/profile

  ```
  $ uv run python -m app.features.profiles.set --nationality TW --degree master
  {"nationality": "TW", "target_degree": "master", "current_major": null, "target_fields": [], "target_countries": [], "version": 1, ...}
  1) GET                                → version 1
  2) PUT 同樣內容（國碼寫小寫 tw）       → "nationality":"TW", version 1（沒變就不加版本）
  3) PUT target_countries ["fr"]         → "target_countries":["FR"], version 2
  4) PUT 改回去                          → "target_countries":[], version 3
  5) PUT nationality XX                  → 422：XX 不是 ISO 3166-1 兩碼國碼（例如台灣是 TW）
  6) PUT target_degree diploma           → 422：Input should be 'bachelor', 'master' or 'phd'
  ```
- [x] 評分指令 -> verify: 貼出評分筆數、各上限的筆數、費用

  ```
  score-1（第一次）：評分 221 筆（AI 分項沿用 0、重算 221、失敗 0）；上限 20：20、上限 80：140、沒有上限：61｜約 US$0.119（NT$3.8）
  規則修正後：      評分 221 筆（AI 分項沿用 206、重算 15、失敗 0）；上限 20：17、上限 80：142、沒有上限：62｜約 US$0.008（NT$0.3）
  score-2（最終）：  評分 221 筆（AI 分項沿用 0、重算 221、失敗 0）；上限 20：17、上限 80：142、沒有上限：62｜約 US$0.117（NT$3.8）
  ```
- [x] 再跑一次評分，AI 分項全部沿用 -> verify: 貼出「沿用 N、重算 0」

  ```
  評分 221 筆（AI 分項沿用 221、重算 0、失敗 0）；上限 20：17、上限 80：142、沒有上限：62
  tokens：輸入 0、輸出 0，約 US$0.000（NT$0.0）
  ```
- [x] 前 10 名與抽查 -> verify: 貼出前 10 名與 3 筆的理由

  ```
  $ uv run python -m app.features.matching.top --limit 10
   1.  95.7  Erasmus Mundus Scholarship – CLIDE (Intercultural Leadership)｜Erasmus Mundus Scholarship｜條件都符合
         適用你的截止日：2027-03-07（即將開放）｜https://clide.umk.pl/
   2.  91.3  Erasmus Mundus Scholarship – European Master on Control of Renewable Energy Systems (EU-CORE)｜條件都符合
         適用你的截止日：2027-01-31（即將開放）Partner and Programme country students applying for Erasmus+ EMJM and Consortium scholarships｜https://master-eu-core.ec-nantes.fr
   3.  90.2  Erasmus Mundus Scholarship – REPLAY Game Design Masters｜條件都符合
         適用你的截止日：2027-01-08（開放中）4th intake｜https://www.replaymasters.eu/
   4.  89.2  Erasmus Mundus Joint Master European Master in Animal Biodiversity and Genomics (EMABG)｜EMJM Scholarship｜條件都符合
         適用你的截止日：2027-01-15（開放中）｜https://www.emabg.eu/
   5.  89.2  Erasmus Mundus Scholarship – EMIMEP｜條件都符合
         適用你的截止日：2027-03-12（即將開放）｜https://www.erasmus-mundus.emimep.eu/
   6.  88.0  Erasmus Mundus Scholarship – Children's Literature, Media & Cultural Entrepreneurship｜條件都符合
         適用你的截止日：2027-01-22（開放中）Erasmus Mundus scholarship｜https://www.clmce-erasmusmundus.eu/
   7.  88.0  Erasmus Mundus Scholarship – ILSPSD｜EU Member States and Third Countries associated to the Erasmus Mundus programme｜條件都符合
         適用你的截止日：2027-01-04（開放中）Scholarship applications｜https://master-international-law-erasmusmundus.eu/
   8.  85.8  Erasmus Mundus Joint Master: Social Psychology of Transformation – Understanding and Mastering Social Change｜Erasmus Mundus Joint Master (EMJM) Scholarships｜條件都符合
         適用你的截止日：2027-01-31（開放中）Scholarship Call｜https://spot-psychology.eu/
   9.  84.7  Erasmus+ MSc in Geo-Information Science and Earth Observation for Environmental Modelling and Management (GEM)｜Erasmus Mundus Joint Master Scholarships｜條件都符合
         適用你的截止日：2027-01-15（開放中）｜https://www.gem-msc.eu/
  10.  84.7  Erasmus Mundus Master: Applied & Community Theatre (Theatre SPACEs)｜條件都符合
         適用你的截止日：2026-12-01（開放中）｜https://www.theatre-spaces.eu/
  ```

  抽查 3 筆（還沒填科系與領域，所以領域契合都是「不評」，其他三項依比例放大）：

  ```
  95.7（沒有上限）CLIDE｜國籍 pass 不限國籍｜學位 pass 碩士｜時間 pass 2027-03-07（即將開放）
    補助 10：全額學費、綜合保險、24 個月每月 1,400 歐元｜時程 10：距離 2027-03-07 還有充裕時間｜名額 8：名額 12 名
    回原文核對：「open from 22 February 2027 to 7 March 2027」「12 scholarship places」「€1,400 for 24 months」都對
  70.2（上限 80）NeuroData｜國籍 pass 不限國籍（依據：EACEA 目錄頁）｜學位 pass｜時間 unclear 原文沒有截止日
    補助 9：學費、保險、每月 1,400 歐元｜時程 5：原文沒有截止日｜名額 6：名額 15 名
  82.5（沒有上限）GroundwatCh（學程 65，修正前因誤判是 20 分）｜時間 pass 2027-01-03（開放中）partner countries
    補助 10｜時程 8：還有約兩個半月｜名額 5：名額 15 名，未提及競爭程度
  ```

  API：`curl "localhost:8000/api/matches?limit=1"` 回傳同一筆（total 95.7、cap null、checks 三項 pass、sub_scores 四項含理由）

### 5. 收尾

- [x] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

  ```
  107 passed in 1.27s
  All checks passed!
  Success: no issues found in 62 source files
  ```

## 執行時發現

1. 重抽 180 筆（4 個程序平行）：完成 177、沒變 3（煙霧測試時已經用新提示詞抽過的 221、20、3）、失敗 0，AI 費用約 NT$34.0。獎學金向量重算 178 筆，因為國家換成國名後組出來的文字變了
2. EACEA 目錄頁當國籍依據（ADR-053）用在 88 筆學程；另外 88 筆學程自己的網站就寫了開放所有國籍
3. 無效國碼 3 個，都被丟掉並記在 issues：EL（PIONEER，原文完全沒提到希臘，是 AI 填錯）、EU 和 EEA（MERGED，原文「outside the EU, EEA or Switzerland」）。EL→GR 的對應做了又撤回（「Claude 自行決定」第 24 點）
4. 國家集合：有國籍限制的 4 筆裡有 3 筆用集合定義（EU／EEA、African Union）。AI 有時展開成各國國碼（SINReM、PIONEER 的 30 國），有時沒有（MASTET 是空清單；MERGED 只剩 CH）。台灣籍的判斷都正確，其他國籍會判錯 → 待決定 #52
5. 17 個預估申請期（13 筆獎學金）的截止日在過去：來源的最新資料是 2022–2025 年，預估只加一年（例如 2022-05-14 → 2023-05-14）→ 待決定 #51
6. 第 4 天不建申請期的窗口（年份是 AI 補的），評分原因原本寫「原文沒有截止日」，不準確；改成「原文有截止日，但年份或日期不完整，無法確認」（第 19 點）
7. 寫評分指令時抓到的錯：對應申請期時建了兩次 CycleInfo，用「是不是同一個物件」對不回去，等於沒有申請期適用；改成只建一次
8. 第一次評分（score-1）：221 個類別、AI 重算 221、失敗 0、約 NT$3.8；上限 20：20、上限 80：140、沒有上限：61。上限 80 的 140 筆裡，135 筆只有時間待確認。時間待確認共 142 筆：開放中但截止日沒核對過 4、只有預估 70、原文沒有截止日 35、年份不完整 33
9. 抽查「申請期都不適用你」的 14 個類別，回原文確認後找到 2 個誤判、確認 1 個是對的：
   - 學程 78 原文「3 January 2027 (for non-European applicants)」被抽成只限列出的國家、但清單是空的 → 台灣籍被判不符合（第 26、27 點）
   - 學程 65 原文「Partner countries: All other countries」，AI 自己列了 159 國、漏掉台灣（第 28 點）
   - 只有自費生申請期的 9 筆：Global-MINDS 原文寫「From 2027 on, Global-MINDS is a self-funded programme」，判不符合是對的（第 29 點）
   - 修正後重建申請期（不花 AI 費用），重新評分只重算內容變了的 15 筆、約 NT$0.3：上限 20：17、上限 80：142、沒有上限：62
   - 代價：學程 15 MASTET 原文是「African Union 會員國」，以前判不符合是碰巧對的，現在變成國籍待確認，等 #52
10. 「競爭與名額」的分數方向不一致：score-1 沒寫分數高代表什麼，同樣名額 4 名的競爭分數從 3 到 8 都有，名額 12 名從 4 到 8 → score-2 寫明方向（第 30 點），重評 221 筆、約 NT$3.8。有寫名額數字的 131 個類別裡，名額和分數的等級相關係數（Spearman）從 0.09 升到 0.42：方向對了，但同樣 15 名仍有 5 到 8 分 → 併進待決定 #53
11. AI 的「時程可行」理由會寫出評分當天的日期（例如「今天是 2026-10-20，還有兩個月」），內容沒變就一直沿用 → 待決定 #53
12. 使用者填了科系與領域（個人資料版本 5）後重新評分（score-2）：重算 221、約 NT$4.1；領域契合 0–3 分 143 筆、4–6 分 15、7–10 分 40、空白 23。空白的 23 筆裡有 13 筆兩邊都有資料（學程的領域是地理空間、氣候變遷、土木工程等），AI 似乎用空白表示「不相關」；加權總分跳過空白項，這些學程反而排進前 10（Geospatial 第 4 名）。補助價值也有 25 筆空白、時程 13 筆 → 第 31 點（score-3）。score-3 重評 221 筆、約 NT$4.2，再跑一次全部沿用、NT$0；空白分數 0 筆；領域契合 0–3 分 142、4–6 分 49、7–10 分 30；前 10 名的領域契合都是 8–10 分，Geospatial 從第 4 名降到第 31 名（領域 5 分）
