# 第 9 天：網頁介面與結構化金額

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 直接推 main）。依 ADR-039 的方式分階段做。

目標：在本機瀏覽器打開網頁，就能：

- 看依時間狀態與適配度排序的獎學金列表，用篩選和搜尋框找
- 看詳細頁：截止日、資格、文件、每個金額都附原文引用與核對結果
- 修改個人資料，評分在背景自動更新
- 在問答頁問問題，答案附出處
- 看通知歷史

## 本計畫記錄的決定

- 前端用 React＋TypeScript＋Vite 做單頁應用，建置後由 FastAPI 的 `app.frontend()` 提供（ADR-066）
- 型別由 `/openapi.json` 產生（openapi-typescript），呼叫用 openapi-fetch（ADR-067）
- 元件用 shadcn/ui（複製進專案）＋Tailwind 4（ADR-068）
- 資料抓取用 TanStack Query（ADR-071）
- 搜尋：篩選＋混合搜尋（關鍵字＋語意，用 RRF 合併名次）（ADR-069）
- 金額：每個金額一筆，附用途與原文引用，程式核對（ADR-070）
- 第一版不加 Host 檢查、CORS、登入（ADR-072）
- 網頁伺服器手動啟動，launchd 照舊只管 worker 與排程器（ADR-073）

## 分三段做（會超過一天）

| 段 | 內容 | 做完就有 | 估計 |
| --- | --- | --- | --- |
| 1 能用的網頁 | 後端 API、前端骨架、列表、詳細頁、個人資料、問答、通知歷史、FastAPI 提供建好的網頁 | 能用的版本 | 約 1 天 |
| 2 混合搜尋 | RRF 合併名次、列表 API 的搜尋參數、搜尋框 | 打字搜尋 | 約半天 |
| 3 結構化金額 | 抽取表格、數字核對、合併、重抽、顯示 | 列表上的大概金額、詳細頁的金額與出處 | 約半天＋背景重抽（約 NT$34） |

## Claude 自行決定（小問題，請事後檢查）

1. 前端放在 repo 根目錄的 `frontend/`，和 `backend/` 並列
2. 套件用 npm（電腦已有 Node 22.22.3、npm 10.9.8）。版本寫死（不用 `^`），`package-lock.json` 進 git，安裝一律用 `npm ci`（照 lockfile 裝，不會自己升級）。這是為了 npm 供應鏈攻擊（CISA 2025-09-23）
3. 路由用 React Router 8 的 declarative mode（`BrowserRouter`＋`Routes`）。資料已經交給 TanStack Query（ADR-071），路由只負責「網址對到哪一頁」，要學的觀念最少
4. shadcn/ui 用 CLI 的預設底層（2026-07 起是 Base UI），少記一個設定
5. 不用 openapi-react-query：直接寫 `useQuery({ queryKey, queryFn: () => client.GET(...) })`，每一步看得到
6. 產生型別不用啟動伺服器：後端多一個小指令，把 `app.openapi()` 印出來，接給 openapi-typescript，產生 `frontend/src/api/schema.d.ts`；這個檔案進 git、不手改。`npm run gen:api` 一次做完
7. 開發時 Vite 把 `/api` 轉發到 `http://127.0.0.1:8000`，瀏覽器看起來是同一個網址，所以不需要 CORS（ADR-072）；`.claude/launch.json` 多一個 `web` 設定（Vite 5173）
8. 做好後 `npm run build` 產生 `frontend/dist`，FastAPI 用 `app.frontend("/", directory=...)` 提供；還沒建置過時，FastAPI 照常啟動（只有 API）
9. 頁面與網址：`/` 列表、`/scholarships/:id` 詳細頁、`/profile` 個人資料、`/ask` 問答、`/notifications` 通知歷史
10. API 照 CLAUDE.md 的資料夾規範放在各功能裡：
    - `scholarships/api.py`：列表、詳細
    - `search/api.py`：問答
    - `notifications/api.py`：通知歷史
    - `profiles/api.py`：存檔後放評分工作
11. 列表一筆獎學金一列，顯示分數最高的類別（和第 8 天通知的 `best_scores` 一致）。沒有搜尋字時，依時間狀態分組（還能申請、時間待確認、已截止或不適用，ADR-059），同組依分數；有搜尋字時，依搜尋的相關程度排，分組改成每列的標記
12. 列表的篩選：留學國家、學位、只看還能申請的、截止日範圍，沿用第 5 天的篩選表（`search/filters.py`）。國籍不給篩選，因為評分已經依你的國籍判斷
13. 詳細頁的變更紀錄只列會通知的欄位（截止日、國籍、學位），其他欄位的紀錄雜訊多（第 8 天執行時發現第 6 點）
14. 個人資料存檔後，API 放一件 RQ 評分工作（`score_today`，worker 由 launchd 跑）。評分紀錄的個人資料版本比目前舊時，列表 API 回傳 `scores_outdated: true`，畫面顯示「評分更新中」，每 5 秒重抓，直到更新完。一次全部重評約 NT$4 以內（第 6 天全部重評約 NT$3.8–4.2）
15. 問答用 `POST /api/ask`，問題放在 JSON 內容裡（問題可能很長，放網址不合適；也剛好受到 FastAPI 只解析 JSON 的保護）。畫面上註明每題約 NT$0–0.3（第 5 天實測）
16. `ask()` 改成回傳結構化結果（路線、答案、出處、篩選到的獎學金、提示），終端機指令照樣印出同樣的內容；先改 `answer_with` 回傳答案與出處，用假的 LLM 寫測試
17. 通知歷史：`GET /api/events` 列最近 50 則（類型、標題、內容、狀態、時間），只讀
18. 混合搜尋：
    - 關鍵字用 `ILIKE` 比對名稱、中文名稱、提供單位、領域；資料只有 188 筆，不需要全文索引
    - 語意用第 5 天的 `find`
    - 合併用 RRF：每份名單裡的名次 r 給 1/(60 + r) 分，加總後排序（k＝60，Cormack 等人 2009 年的論文所用的值）
19. 語意搜尋不能用時（沒網路、斷路器打開、呼叫失敗），只用關鍵字，回應帶 `semantic: false`，畫面註明「這次只用關鍵字搜尋」
20. 金額的抽取表格（取代原本的 `amount` 文字）：

    ```python
    class AmountDraft(BaseModel):
        value: float          # 照原文換成阿拉伯數字，例如「1 萬 6 千」填 16000
        currency: str         # ISO 4217 三碼，例如 EUR、USD、TWD（用 pycountry 檢查）
        period: Literal["month", "year", "once", "unclear"]
        kind: Literal["living_allowance", "tuition_coverage", "travel", "other"]
        applies_to: str | None  # 適用對象，例如「一般生」；全部適用留空
        evidence: str | None    # 寫著這個金額的原文句子，逐字引用
    ```

    只列「獎學金給你的錢」（生活津貼、學費補助或減免、旅費、其他）；學費、申請費這類要你付的錢不列（PIONEER 的 5,613.10 EUR 學費就是這種）
21. 金額的核對只用程式，不另外問 AI：引用要在原文裡（和驗證者同一套找法），而且引用裡真的有這個數字。數字的寫法要認得千分位（1,400、1.400）、小數（5,613.10）、中文單位「萬」「千」（1 萬 6 千＝16000）。狀態：`supported`、`no_evidence`、`quote_not_found`、`number_not_in_quote`、`invalid_currency`
22. 長文件各節的金額取聯集，相同的（數字、幣別、期間、用途、適用對象一樣）只留第一筆與它的引用
23. 列表上的「大概的金額」：
    - 從核對通過的金額裡，先找生活津貼；沒有的話，依學費補助、旅費、其他的順序找
    - 同用途、同期間、同幣別但適用對象不同的，顯示範圍（例如教育部「每年 16,000–30,000 USD」）
    - 都沒有就顯示「—」
24. `scholarships.amount` 文字改由金額清單產生，搜尋索引、問答、變更紀錄照舊用它；類別的 `amount` 文字不改
25. 金額存在抽取結果（`extracted` JSONB）裡，第 9 天不排序、不篩選金額，所以不需要新欄位，也不需要遷移
26. 抽取提示詞改版號：`extract-11`、`section-11`。全部重抽用 `extract --max-cost 60`，等當天的每日檢查跑完再跑（兩邊同時抽同一個來源會互相覆蓋）；只因改版重抽的不寫變更紀錄（第 4 天的規則）
27. 前端不寫單元測試：邏輯放在後端並有測試，前端只負責顯示；每一頁用瀏覽器預覽驗證，貼截圖或頁面文字

## 待使用者決策

1. ~~網頁伺服器（FastAPI）要不要也由 launchd 登入後自動啟動~~：選 A 手動啟動（ADR-073）

## 設計草圖

### 資料

- 第 1、2 段：不新增資料表
- 第 3 段：抽取結果多 `amounts` 清單與 `verification.amounts`（每筆的核對狀態）；`scholarships.amount` 改由清單產生；不需要遷移

### API

```python
# scholarships/api.py
GET /api/scholarships?q=&country=&degree=&open_only=&deadline_after=&deadline_before=
  -> ScholarshipList { rows: list[ScholarshipRow], semantic: bool, scores_outdated: bool }
ScholarshipRow { id, name, name_zh, provider, countries, degrees,
                 score, category, group: "pass"|"unclear"|"fail", time_reason,
                 unclear, failed, next_deadline, stale, amount_headline, official_url }
GET /api/scholarships/{id}
  -> ScholarshipDetail { 基本欄位, categories, cycles, requirements, amounts（含核對狀態與引用）,
                         nationality（範圍、國家、引用、核對）, degrees（引用、核對）,
                         match（分數、分項、理由、待確認）, changes（只有會通知的欄位） }

# search/api.py
POST /api/ask  { question } -> AskOut { route, answer, citations: [{id, where}], listed, notes }

# notifications/api.py
GET /api/events?limit=50 -> list[EventOut { kind, title, lines, url, status, created_at, sent_at }]

# profiles/api.py（改）
PUT /api/profile -> 存檔，再放一件 score_today 工作
```

### 前端

```text
frontend/
  package.json、package-lock.json、vite.config.ts（/api 轉發到 127.0.0.1:8000）
  components.json（shadcn 設定）
  src/main.tsx                 QueryClientProvider＋BrowserRouter
  src/api/schema.d.ts          openapi-typescript 產生（不手改）
  src/api/client.ts            openapi-fetch
  src/components/ui/           shadcn 複製進來的元件
  src/pages/ScholarshipList.tsx、ScholarshipDetail.tsx、Profile.tsx、Ask.tsx、Notifications.tsx
```

### 流程

```text
開發：  npm run dev（Vite 5173）＋ uv run uvicorn app.main:app --reload（8000）
型別：  npm run gen:api（後端印出 openapi → openapi-typescript → src/api/schema.d.ts）
做好後：npm run build → frontend/dist；只開 FastAPI，瀏覽器打開 http://127.0.0.1:8000/
```

### 介面（純函式，有測試）

```python
# search/fusion.py（新）
def rrf(rankings: list[list[int]], k: int = 60) -> list[int]         # 合併名次，回傳獎學金 id 的順序

# search/ask.py（改）
def answer_with(llm, question, evidence) -> Answered                 # 回傳答案與有效出處，不再直接印出

# scholarships/amounts.py（新）
def numbers_in(text: str) -> set[float]                             # 認得千分位、小數、萬、千
def amount_status(amount: AmountDraft, source: str) -> str           # supported、quote_not_found…
def headline(amounts: list[dict[str, Any]]) -> str | None            # 列表上的大概金額
def describe(amounts: list[dict[str, Any]]) -> str | None            # 給 scholarships.amount 的文字

# scholarships/merge.py（改）
def merge_amounts(sections: list[list[AmountDraft]]) -> list[AmountDraft]

# 列表排序
def list_order(group: str, score: float | None) -> tuple[int, float]
```

### 不在第 9 天範圍

- 依金額排序或篩選、幣別換算（ADR-070 做得到，需要時再做）
- 登入、Host 檢查、CORS（ADR-072，公開版前重新決定）
- 設定頁、成本統計、發掘 agent（第 10 天）
- 前端單元測試（「Claude 自行決定」第 27 點）
- 類別的金額文字

## 測試哪些行為

| 檔案 | 行為 |
| --- | --- |
| test_search_fusion.py（新） | RRF：兩份名單合併；只出現在一份的也排得進來；越前面分數越高 |
| test_ask_answer.py（新） | `answer_with` 回傳答案與出處；不存在的出處編號被剔除並記下 |
| test_web_order.py（新） | 列表排序：先依時間狀態分組，同組依分數；沒有分數的排在同組最後 |
| test_amounts.py（新） | 數字寫法（千分位、小數、萬、千）；金額核對的各種狀態；列表的大概金額（生活津貼優先、範圍、沒有）；金額文字 |
| test_merge.py | 長文件各節的金額合併去重 |

## 檢查清單

在 `backend/` 執行，前端的在 `frontend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 第 1 段：能用的網頁

純函式（紅綠循環）：

- [ ] W1 列表排序：時間狀態分組，同組依分數 -> verify: `uv run pytest tests/test_web_order.py`
- [ ] Q1 `answer_with` 回傳答案與有效出處 -> verify: `uv run pytest tests/test_ask_answer.py`

後端 API（Claude）：

- [ ] A1 `GET /api/scholarships`（篩選、分組、分數、時間說明） -> verify: `curl -s 'http://127.0.0.1:8000/api/scholarships?open_only=true' | python3 -m json.tool | head -40`
- [ ] A2 `GET /api/scholarships/{id}`（教育部、ReSound 各一次） -> verify: `curl -s http://127.0.0.1:8000/api/scholarships/3 | python3 -m json.tool | head -60`
- [ ] A3 存個人資料後放評分工作，列表回報評分更新中，更新完變回 false -> verify: `curl -X PUT` 後 `uv run rq info` 看到工作；再查 `scores_outdated`
- [ ] A4 `POST /api/ask`（lookup、filter、semantic 各一題），終端機指令輸出不變 -> verify: `curl -s -X POST http://127.0.0.1:8000/api/ask -H 'Content-Type: application/json' -d '{"question":"教育部北歐國家有幾個名額？"}'`
- [ ] A5 `GET /api/events` -> verify: `curl -s 'http://127.0.0.1:8000/api/events?limit=5' | python3 -m json.tool`

前端（Claude）：

- [ ] F1 前端骨架（Vite＋React＋TypeScript＋Tailwind 4＋shadcn＋TanStack Query＋React Router 8），版本寫死、有 lockfile -> verify: `npm ci && npm run build`
- [ ] F2 產生型別 -> verify: `npm run gen:api && npx tsc --noEmit`
- [ ] F3 列表頁（分組、分數、時間說明、篩選、資料過舊標記） -> verify: 瀏覽器預覽，貼截圖
- [ ] F4 詳細頁（截止日、資格與引用、文件、評分與理由、變更紀錄） -> verify: 瀏覽器預覽教育部與 ReSound，貼截圖
- [ ] F5 個人資料頁（存檔後列表顯示評分更新中，更新完自動刷新） -> verify: 瀏覽器預覽，貼存檔前後的畫面
- [ ] F6 問答頁（等待中、答案、出處、費用提醒） -> verify: 瀏覽器預覽問一題，貼截圖
- [ ] F7 通知歷史頁 -> verify: 瀏覽器預覽，貼截圖
- [ ] F8 FastAPI 提供建好的網頁（只開 FastAPI） -> verify: `npm run build` 後只啟動 uvicorn，打開 `http://127.0.0.1:8000/` 與 `/scholarships/3`（重新整理也要能開），貼截圖

### 第 2 段：混合搜尋

- [ ] S1 RRF 合併名次（紅綠循環） -> verify: `uv run pytest tests/test_search_fusion.py`
- [ ] S2 列表 API 的 `q`：關鍵字＋語意＋RRF；語意不能用時只用關鍵字 -> verify: `curl` 搜「數據科學」「DEAI」；手動打開斷路器再搜一次，看到 `semantic: false`，之後恢復
- [ ] S3 搜尋框與「只用關鍵字」的提示 -> verify: 瀏覽器預覽，貼截圖

### 第 3 段：結構化金額

純函式（紅綠循環）：

- [ ] M1 數字寫法：千分位、小數、萬、千 -> verify: `uv run pytest tests/test_amounts.py -k numbers`
- [ ] M2 金額核對的各種狀態 -> verify: `uv run pytest tests/test_amounts.py -k status`
- [ ] M3 長文件各節的金額合併去重 -> verify: `uv run pytest tests/test_merge.py -k amounts`
- [ ] M4 列表上的大概金額 -> verify: `uv run pytest tests/test_amounts.py -k headline`
- [ ] M5 由金額清單產生的文字 -> verify: `uv run pytest tests/test_amounts.py -k describe`

串起來（Claude）：

- [ ] M6 抽取表格、提示詞改版（extract-11、section-11）、存檔時核對並產生文字 -> verify: `uv run python -m app.features.scholarships.extract --source 3`，再抽 ReSound 與 PIONEER，貼出金額清單與核對狀態
- [ ] M7 全部重抽 -> verify: `uv run python -m app.features.scholarships.extract --max-cost 60`，貼出筆數與費用；抽查 5 筆的金額與引用
- [ ] M8 列表與詳細頁顯示金額（核對狀態、引用） -> verify: 瀏覽器預覽，貼截圖

### 收尾

- [ ] 完整檢查、更新 CLAUDE.md 的常用指令（前端）、progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`，以及 `frontend/` 的 `npm run build && npx tsc --noEmit`

## 執行時發現
