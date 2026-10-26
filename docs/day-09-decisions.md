# 第 9 天前要決定的 6 題

第 9 天要做：前端列表、詳細頁、個人資料頁，以及搜尋與問答的網頁介面。依 ADR-014（最後負責時刻），開工前先決定排在第 9 天之前的題目。格式依 `docs/decision-format.md`：不給推薦、不給參考組合；用題號和 A、B、C 回答，也可以寫自己的理由。

資料與實測都是 2026-10-25 查的。

## 你的選擇（2026-10-26）

| 題 | 選擇 | 記錄 |
| --- | --- | --- |
| #35 前端框架 | A React＋Vite | ADR-066 |
| #36 型別契約 | B 產生型別（openapi-typescript＋openapi-fetch） | ADR-067 |
| #37a 資料抓取 | B TanStack Query | ADR-071 |
| #37b 元件庫 | A shadcn/ui 複製進專案 | ADR-068 |
| #43 存取安全 | 登入（用 Google 登入）等公開版再做；第一版的防護程度待選 | — |
| #35b 搜尋方式 | D 篩選＋混合搜尋 | ADR-069 |
| #55 金額 | C 每個金額一筆附引用 | ADR-070 |

## 題目之間的關係

- #36（型別契約）、#37（資料抓取與元件庫）的選項會依 #35（前端框架）不同，表格裡分開寫
- #43（存取安全）要做的事，會依 #35 是「前端、後端分開跑」還是「FastAPI 直接產生網頁」而不同
- #35b（搜尋方式）如果之後想「依金額篩選或排序」，要 #55 選 C 才做得到
- 閱讀順序照依賴關係排：#35 → #36 → #37 → #43 → #35b → #55

## #35 前端框架

### 1. 這題在決定什麼

網頁用什麼技術寫。這決定前端程式怎麼組織、你要學哪一套，以及之後（第 10 天的設定頁與成本統計、公開版）好不好擴充。換框架等於所有頁面重寫，是難回頭的決定。

### 2. 先懂的概念

- **要做的頁面**：第 9 天有列表（排序、篩選、搜尋）、詳細頁、個人資料表單、問答頁；第 10 天再加設定頁、成本統計、候選來源核准
- **兩大做法**：
  - **單頁應用（SPA）**：瀏覽器下載一個 JavaScript 程式，畫面在瀏覽器裡畫，資料用 JSON 向 FastAPI 拿。開發時跑兩個伺服器（Vite 開發伺服器＋FastAPI）；做好後 `vite build` 產生靜態檔，交給 FastAPI 的 `app.frontend()` 提供（FastAPI 0.138 起有，已確認我們的 0.143.0 有），又變回一個程式、同一個網址。React、Vue、Svelte 都能這樣
  - **伺服器產生網頁**：FastAPI 用 Jinja2 模板直接回傳 HTML。HTMX 讓按鈕、表單用屬性（例如 `hx-get`）只換掉頁面的一部分，幾乎不用寫 JavaScript；只有一個伺服器、一種語言（Python）
- **全端框架（Next.js）**：React 的框架，頁面預設在伺服器上執行（React Server Components），需要一個 Node.js 伺服器；我們的後端是 Python，所以會有兩個後端。也可以輸出成靜態檔，但 Server Actions、轉發請求等伺服器端功能就不能用
- **名詞**：元件（component）＝畫面上可重複使用的一塊（例如一張獎學金卡片）；狀態（state）＝畫面上會變的資料（例如篩選條件）；TypeScript＝加上型別的 JavaScript（#36）
- **你的電腦**：已經有 Node 22.22.3，SPA 和 Next.js 需要的版本都夠
- **參考**：FastAPI 官方的全端範本（full-stack-fastapi-template，2026-10-15 更新）用 React 19.3＋TypeScript＋Vite 8＋TanStack Router／Query＋Tailwind 4＋shadcn/ui，用 Hey API 產生呼叫程式，建置後由 `app.frontend()` 提供
- **版本**（2026-10-25）：React 19.3.1、Vite 8.3.5、Next.js 16.4.3、Vue 3.5.44（3.6 還在 RC）、Svelte 5.57.2／SvelteKit 3.1.0、htmx 2.0.11（htmx 4.0 已在 2026-08-28 發表，npm 預設 2027 年才換成 4；2 版會一直支援）
- **使用度與滿意度**（自願填寫的問卷，只當參考）：

  | 框架 | State of JS 2025：用過／滿意 | Stack Overflow 2026：用過／想繼續用 |
  | --- | --- | --- |
  | React | 85% / 72% | 41.5% / 46.7% |
  | Vue | 52% / 84% | 17.2% / 47.2% |
  | Svelte | 27% / 86% | 7.8% / 59.4% |
  | Next.js | 59% / 55% | 20.6% / 39.3% |
  | HTMX | 9% / 69% | 5.4% / 55.9% |

  State of JS 2025 有 13,002 人填；Stack Overflow 2026 有 10,281 人回答這一題。State of JS 網站沒有定義「滿意」這個數字

- Svelte（SvelteKit 3，滿意度最高、使用度較低）也做得到，沒有列成選項；想一起比較的話跟我說

來源：npm registry；react.dev、vite.dev、nextjs.org（Next 16、16.4、static exports、Server and Client Components）、vuejs.org 與 vuejs/core releases、svelte.dev、htmx.org 與 htmx 4 公告；fastapi/full-stack-fastapi-template 的 frontend/package.json；FastAPI 文件 frontend；State of JS 2025；Stack Overflow Developer Survey 2026（都在 2026-10-25 查證）

### 3. 選項

**A React＋Vite（單頁應用）**

- 怎麼運作：用 TypeScript＋React 寫元件，Vite 開發與建置；路由用 React Router 8 或 TanStack Router；建置後由 FastAPI 的 `app.frontend()` 提供
- 好處：用的人最多（兩份問卷都是第一）；FastAPI 官方範本就是這套；#37 的元件庫選擇最多
- 代價：要學的東西多（JSX、hooks、狀態、路由、建置工具）；開發時兩個伺服器；選擇多，要做的小決定也多
- 在這個專案：多一個 `frontend/` 資料夾；開發時 Vite 把 `/api` 轉發到 FastAPI；做好後一個 FastAPI 程序同時提供網頁和 API

**B Next.js**

- 怎麼運作：React 的全端框架，頁面預設在 Node.js 伺服器上執行，可以在伺服器端向 FastAPI 拿資料
- 好處：用的人多（Stack Overflow 2026 在這幾個裡排第二）；伺服器端渲染、串流等功能齊全
- 代價：兩個後端（Node＋Python），兩個程序要啟動與保護；要多學伺服器元件與瀏覽器元件的分界；2025-12 有 React Server Components 的嚴重漏洞（CVE-2025-66478），之後官方固定發安全更新，要跟著升級；滿意度在這幾個裡最低
- 在這個專案：`frontend/` 是 Next.js 專案，launchd 要多管一個 Node 伺服器；輸出成靜態檔的話，伺服器端功能都不能用

**C Vue＋Vite（單頁應用）**

- 怎麼運作：架構和 A 一樣，元件寫成 Vue 的單檔元件（`.vue`，模板接近 HTML）
- 好處：模板寫法接近 HTML；滿意度高（State of JS 84%）；官方自己提供路由（Vue Router）與狀態管理（Pinia），要選的東西少
- 代價：用的人比 React 少（State of JS 52% 對 85%）；元件庫要注意授權（PrimeVue 5 改成商業授權，個人與學生免費）
- 在這個專案：架構和 A 相同，只差元件寫法

**D HTMX＋Jinja2（FastAPI 直接產生網頁）**

- 怎麼運作：FastAPI 的路由回傳 Jinja2 模板產生的 HTML；HTMX 是一個 script 標籤（不用建置），讓表單、按鈕只更新頁面的一部分
- 好處：一個伺服器、一種語言；不用 Node、不用建置、不用型別契約（#36 自動是 D）；同一個網址，不需要 CORS（#43）；最快做出能用的版本
- 代價：練不到現代前端框架，作品集上前端分量少；互動越複雜越難寫（例如第 10 天的成本圖表要另外加一個 JavaScript 圖表庫）；用的人最少；htmx 4 已發表，之後升級要改一些寫法
- 在這個專案：多一個 `backend/app/web/`（路由、模板、靜態檔）；頁面直接呼叫現有的 Python 函式（篩選、`find`、`ask`）

### 4. 選了會怎樣

| 情境 | A React | B Next.js | C Vue | D HTMX |
| --- | --- | --- | --- | --- |
| 開工前要先懂的 | JSX、hooks、路由、建置 | A 的全部＋伺服器元件 | 模板語法、組合式 API、路由、建置 | Jinja 模板＋HTMX 屬性 |
| 做好後要跑的程式 | 1 個（FastAPI 提供建好的網頁） | 2 個（Node＋FastAPI） | 1 個 | 1 個 |
| 開發時的伺服器 | 2 個 | 2 個 | 2 個 | 1 個 |
| 型別契約（#36） | 要選 | 要選 | 要選 | 不需要 |
| 第 10 天的成本圖表 | 用 React 的圖表套件 | 同 A | 用 Vue 的圖表套件 | 另外加一個 JavaScript 圖表庫 |
| 作品集上的前端分量 | 高 | 高 | 高 | 低 |
| 第 9 天要花的時間（相對） | 中 | 最長 | 中 | 最短 |

### 5. 對照品質屬性

- 盡快做出能用的版本：D 最快；A、C 差不多；B 最慢
- 學習價值與作品集：A、B、C 都是完整的前端框架，A、B 屬於用的人最多的 React；D 學到伺服器產生網頁，前端少
- 結果準確可信：框架本身影響不大；A、B、C 搭配 #36 可以在編譯時抓到欄位錯誤；D 的契約留在 Python

### 6. 可逆性

難回頭：換框架要重寫所有頁面（後端 API 不受影響）。拿不定時，可以想「第 10 天和公開版還要做哪些畫面」，以及「前端是不是你想練的技能」。這題又大又難回頭，需要的話可以用 `/decision-brief` 做完整的中立比較。

### 7. 原本的狀態與改完後

- 現在：沒有前端；FastAPI 只有 `/health`、`/api/profile`、`/api/matches`
- A、C：repo 多 `frontend/`（`package.json`、`src/`）；FastAPI 多一行 `app.frontend("/", directory=...)` 提供建置結果；`.claude/launch.json` 多一個 Vite 的設定
- B：`frontend/` 是 Next.js 專案；多一個 Node 伺服器，launchd 多一個項目
- D：`backend/app/web/`（路由、`templates/`、`static/htmx.min.js`）；不用 Node

## #36 前後端型別契約

### 1. 這題在決定什麼

前端怎麼知道 API 回傳的資料長什麼樣（欄位名稱、型別、哪些可能是空的），以及後端改了欄位時，前端怎麼發現。選了 #35 D（HTMX）的話，這題自動是 D。

### 2. 先懂的概念

- **契約（contract）**：前後端事先約定好的資料形狀。後端已經用 Pydantic 定義了：

  ```python
  class ProfileIn(BaseModel):
      nationality: str                      # 國碼，例如 TW
      target_degree: Degree                 # "bachelor" | "master" | "phd"
      current_major: str | None = None
      target_fields: list[str] = []
      target_countries: list[str] = []

  class ProfileOut(ProfileIn):
      version: int
      updated_at: datetime
  ```

- **OpenAPI**：FastAPI 依這些 Pydantic 模型，自動產生一份描述所有 API 的文件 `/openapi.json`（OpenAPI 3.1 格式）。我們的 `ProfileOut` 已經在裡面
- **TypeScript 型別**：前端用 TypeScript 寫的話，可以宣告資料的形狀，**編譯時**就檢查用錯欄位。但型別在執行時不存在（TypeScript 官方文件：型別註記不會改變程式執行的行為），伺服器真的回傳了不一樣的東西，型別擋不住
- **程式碼產生（codegen）**：用工具讀 `/openapi.json`，自動產生 TypeScript 型別，甚至產生呼叫 API 的函式。`ProfileOut` 會變成：

  ```ts
  type ProfileOut = {
    nationality: string;
    target_degree: "bachelor" | "master" | "phd";
    current_major?: string | null;   // 有預設值的欄位會變成「可能沒有」
    target_fields?: string[];
    target_countries?: string[];
    version: number;
    updated_at: string;              // 日期時間是字串，不是 Date
  };
  ```

  這裡看得到兩個常見的小坑（已用我們的 `/openapi.json` 確認）：有預設值的欄位不在「必填」清單，所以產生 `?`（API 其實每次都會回傳）；日期時間是字串
- **執行期驗證**：有些工具可以另外產生 Zod 檢查規則，在瀏覽器收到資料時真的檢查一遍（預設關閉，因為有效能成本）
- **工具現況（2026-10-25 查證）**：

  | 工具 | 版本 | 產生什麼 | 維護狀況 |
  | --- | --- | --- | --- |
  | openapi-typescript＋openapi-fetch | 7.13.0、0.17.0（2026-02-11） | 只有型別＋約 6 kB 的呼叫函式庫 | 2026-02 之後只有更新依賴的 commit |
  | Hey API（`@hey-api/openapi-ts`） | 0.99.0（2026-06-22） | 型別＋每個 API 一個呼叫函式；外掛可產生 TanStack Query、Zod | FastAPI 文件推薦的工具；還在 1.0 前、要求鎖定版本，幾乎每個小版本都有不相容的改動；10 月 0 個 commit |
  | Orval | 8.44.0（2026-10-21） | 型別＋呼叫函式＋React/Vue/Svelte Query hooks、SWR、Zod、假資料 | 很活躍，4–7 天發一版；沒找到「支援 OpenAPI 3.1」的明確說明 |
  | Kubb | 5.14.0（2026-10-25） | 和 Orval 類似，支援 OpenAPI 3.1 | 很活躍，一天發好幾版；Svelte、Solid 的外掛還停在 v4 |

來源：FastAPI 文件 Generating SDKs、Separate OpenAPI Schemas；npm registry；各工具官方文件與 GitHub releases；TypeScript Handbook；htmx 文件；Jinja 文件（都在 2026-10-25 查證）

### 3. 選項

**A 手寫 TypeScript 型別**

- 怎麼運作：照著 Pydantic 模型，在前端手寫一份 TypeScript 型別
- 好處：不用任何工具；型別寫成自己想要的樣子（例如沒有多餘的 `?`）
- 代價：契約在兩個地方（Python 和 TypeScript），要靠人同步；改了後端忘了改前端，沒有工具會發現
- 在這個專案：每個 API 手寫一份型別

**B 產生型別＋小型呼叫函式庫（openapi-typescript＋openapi-fetch）**

- 怎麼運作：一個指令讀 `/openapi.json` 產生 `api.d.ts`；呼叫 API 用 openapi-fetch，網址、參數、回傳都有型別
- 好處：後端改了欄位，重新產生後前端編譯就報錯，指出每個要改的地方；執行時幾乎沒有額外程式
- 代價：多一個產生步驟；資料抓取（loading、快取）要自己搭（#37）；工具 2026-02 後沒有新功能
- 在這個專案：`frontend/src/api.d.ts` 由指令產生，不手改

**C 產生完整的呼叫程式（Orval、Kubb 或 Hey API）**

- 怎麼運作：一個指令產生型別、每個 API 一個呼叫函式，還可以直接產生 TanStack Query 的 hooks（#37 選快取函式庫時用得上）和 Zod 執行期檢查
- 好處：新增 API 時，前端幾乎不用手寫呼叫程式；可以開執行期檢查
- 代價：產生的程式很多，要學工具的設定檔；工具更新快、可能有不相容的改動（Hey API 尤其明顯）；產生的 hooks 會散在整個前端，之後換工具要改很多地方
- 在這個專案：選 C 的話，工具可以一起選（C1 Orval、C2 Kubb、C3 Hey API）；不選就由我依維護狀況決定，記在「Claude 自行決定」

**D 不需要前端型別（純 JavaScript，或 #35 選 HTMX）**

- 怎麼運作：純 JavaScript 沒有型別，契約只在伺服器（Pydantic、`/openapi.json`）；HTMX 的話，契約一直留在 Python 裡（Pydantic 模型 → 模板的資料 → Jinja 模板）
- 好處：沒有產生步驟；HTMX 時前後端是同一份 Python
- 代價：純 JavaScript 的欄位錯誤要到執行時才發現；HTMX 的模板預設把不存在的欄位印成空字串（可設定成 `StrictUndefined` 改為報錯）
- 在這個專案：選 HTMX 時自動是這個

### 4. 選了會怎樣

| 情境 | A 手寫 | B 產生型別 | C 產生完整程式 | D 不需要 |
| --- | --- | --- | --- | --- |
| 後端把 `current_major` 改名 | 前端忘了改就到執行時才發現（畫面空白） | 重新產生後，編譯報錯指出每個地方 | 和 B 一樣 | 純 JS 執行時才發現；HTMX 在模板裡（開 StrictUndefined 會報錯） |
| 新增一個 API | 手寫型別＋呼叫 | 重新產生型別，手寫一行呼叫 | 重新產生，呼叫函式和 hooks 都有了 | 寫模板 |
| 伺服器回傳和型別不符 | 發現不了 | 發現不了 | 開 Zod 就會在瀏覽器報錯 | — |
| 多的設定 | 無 | 一個產生指令 | 產生指令＋工具設定檔 | 無 |
| 依賴的工具 | 無 | 只剩維護更新 | Orval、Kubb 活躍；Hey API 放緩 | 無 |

### 5. 對照品質屬性

- 盡快做出能用的版本：API 少的時候 A 最快；B 的設定約 30 分鐘；C 的設定比較久，但每多一個 API 省一點時間
- 學習價值與作品集：B、C 是業界常見的「契約優先」做法（OpenAPI＋codegen）；A、D 少
- 結果準確可信：B、C 在編譯時抓到欄位不一致；C 開 Zod 連執行時也抓得到；A 最容易不同步

### 6. 可逆性

中等：A → B 大多是把手寫型別換成產生的；C 產生的呼叫函式和 hooks 會用在每一頁，之後換工具或換回 B 要改每個呼叫的地方。

### 7. 原本的狀態與改完後

- 現在：沒有前端；`/openapi.json` 已經自動產生（有 `ProfileIn`、`ProfileOut`、`MatchOut`）
- A：`frontend/src/types.ts` 手寫
- B：`frontend/src/api.d.ts`（產生的，不手改）＋ openapi-fetch
- C：`frontend/src/api/`（產生的型別、呼叫函式、hooks，不手改）＋工具設定檔
- D：沒有前端型別檔

## #37 前端資料抓取與 UI 元件庫

### 1. 這題在決定什麼

兩件事，分成 37a、37b 回答：

- 37a 資料抓取：前端怎麼向 API 拿資料，並處理「載入中」「錯誤」「改完要重新整理」
- 37b UI 元件庫：按鈕、表格、表單、對話框這些畫面元件，用現成的還是自己做

#35 選 D（HTMX）的話，37a 不需要（伺服器直接產生 HTML），37b 只剩 C。

### 2. 先懂的概念

- **資料抓取的三種狀態**：每次向 API 拿資料，畫面都要處理「載入中」「成功」「錯誤」。問答頁要等 AI 回答好幾秒，載入中特別重要
- **快取與失效**：同一份資料好幾頁都用到時，要不要重抓（快取）；你改了個人資料之後，評分列表就過時了，要讓它重抓（失效）
- **TanStack Query** 5.104.5（2026-10-19）：專門處理上面這些（快取、背景重抓、修改後失效、分頁）；有 React、Vue、Svelte、Solid、Angular 版；FastAPI 官方範本用它；#36 選 C 時可以直接產生它的 hooks
- **SWR** 2.5.1：Vercel 做的，只有 React 版，概念類似
- **元件庫的兩種取得方式**：
  - **複製進專案**：用指令把元件的原始碼複製到你的專案，之後就是你的程式，想改就改（例如 shadcn/ui）
  - **安裝套件**：用 npm 安裝，照文件組合，升級跟著套件走（例如 MUI）
- **Tailwind CSS** 4.3.3：在 HTML 上直接寫一堆小 class（例如 `p-4 text-sm`）決定樣式；很多現代元件庫都建立在它上面
- **版本與授權**（2026-10-25）：

  | 名稱 | 版本 | 取得方式 | 備註 |
  | --- | --- | --- | --- |
  | shadcn/ui（React） | CLI 4.22.1 | 複製進專案 | Tailwind 4；2026-07 起預設用 Base UI 當底層，也可以選 Radix；FastAPI 官方範本用它 |
  | shadcn-vue | 2.8.2 | 複製進專案 | Vue 版，底層是 Reka UI |
  | MUI（React） | 9.5.0 | 安裝套件 | Material Design 風格；從 v7 直接跳到 v9 |
  | Mantine（React） | 9.7.3 | 安裝套件 | 要 React 19.2 以上 |
  | Chakra UI（React） | 3.37.0 | 安裝套件 | |
  | Vuetify（Vue） | 4.3.0 | 安裝套件 | Material Design，MIT 授權 |
  | Nuxt UI（Vue） | 4.12.0 | 安裝套件 | MIT；一般的 Vue＋Vite 也能用 |
  | PrimeVue（Vue） | 5.0.4 | 安裝套件 | 5 版改成商業授權，要授權碼；個人、學生、非商業開源免費；MIT 的 4.5.5 還在 |
  | daisyUI | 5.7.50 | 安裝套件 | Tailwind 外掛，提供 `btn`、`card` 這類 class，任何框架或 HTMX 都能用 |
  | Pico CSS | 2.1.1 | 安裝或 CDN | 2026-10-04 宣布停止維護、repo 已封存 |

來源：npm registry；TanStack Query、SWR 的 GitHub README；ui.shadcn.com changelog；mui.com、mantine.dev、chakra-ui.com、vuetify、ui.nuxt.com、primevue 套件內的 LICENSE.md、daisyui.com、tailwindcss.com、picocss 的 GitHub README（都在 2026-10-25 查證）

### 3. 選項

**37a 資料抓取**

**A 直接用 fetch**

- 怎麼運作：用瀏覽器內建的 `fetch`，搭配 React 的 `useEffect`（或 Vue 的 `onMounted`），自己記錄載入中與錯誤
- 好處：沒有新東西要學，每一步都看得到
- 代價：每頁重複寫載入中與錯誤處理；快取、「改完重新整理」都要自己做
- 在這個專案：每個頁面各自寫

**B TanStack Query**

- 怎麼運作：用 `useQuery` 拿資料、`useMutation` 改資料；改完個人資料時，宣告「評分列表失效」，它就自動重抓
- 好處：業界常見的做法；載入中、錯誤、快取、失效都內建；搭配 #36 的 C 可以自動產生
- 代價：多一套觀念（查詢鍵 query key、失效 invalidation）要學
- 在這個專案：每個 API 對應一個查詢

**C 框架內建（只適用 #35 選 B 或 D）**

- 怎麼運作：Next.js 在伺服器元件裡直接抓資料；HTMX 由伺服器產生好 HTML
- 好處：不用另外的函式庫
- 代價：綁定那個框架的做法
- 在這個專案：#35 選 B 或 D 時才有這個選項

**37b UI 元件庫**

**A 複製進專案（shadcn/ui 系列）**

- 怎麼運作：用 CLI 把需要的元件（按鈕、表格、對話框）複製進 `src/components/ui/`；React 用 shadcn/ui，Vue 用 shadcn-vue
- 好處：原始碼在專案裡，想改就改，不怕套件大改版；FastAPI 官方範本用這個；學得到 Tailwind 和元件的組成
- 代價：要懂 Tailwind；元件之後有更新，要自己決定要不要合併
- 在這個專案：需要什麼元件才複製什麼

**B 安裝現成的完整元件庫**

- 怎麼運作：React 用 MUI、Mantine 或 Chakra；Vue 用 Vuetify、Nuxt UI 或 PrimeVue（注意授權）
- 好處：現成的元件最多，照文件組合就能用
- 代價：外觀被套件的風格綁住，改不到的地方要繞路；大改版時要跟著升級（MUI 從 v7 跳到 v9）
- 在這個專案：選 B 的話，套件可以一起選；不選就由我依框架決定，記在「Claude 自行決定」

**C 只用 CSS，元件自己組**

- 怎麼運作：Tailwind＋daisyUI 的 class（`btn`、`card`、`table`），互動元件自己寫；#35 選 D（HTMX）時用這個
- 好處：最輕，不綁框架
- 代價：互動元件（對話框、下拉選單、可排序的表格）要自己寫
- 在這個專案：HTMX 時就是這個

### 4. 選了會怎樣

37a：

| 情境 | A fetch | B TanStack Query | C 框架內建 |
| --- | --- | --- | --- |
| 改完個人資料、回到評分列表 | 要自己記得重抓 | 設定「個人資料改了 → 評分失效」，自動重抓 | 重新產生頁面 |
| 問答頁等 AI 回答 | 自己寫載入中 | 內建載入中狀態 | Next.js：串流或載入中元件；HTMX：`hx-indicator` |
| 每頁重複的程式 | 多 | 少 | 少 |

37b：

| 情境 | A 複製進專案 | B 完整元件庫 | C 只用 CSS |
| --- | --- | --- | --- |
| 想改按鈕的樣子 | 直接改原始碼 | 用主題設定，改不到要繞路 | 改 class |
| 套件大改版 | 不受影響（原始碼在專案裡） | 要跟著升級 | 影響小 |
| 對話框、下拉選單 | 複製現成的 | 現成的 | 自己寫 |
| 學到的東西 | Tailwind、元件的組成 | 一個元件庫的用法 | CSS |

### 5. 對照品質屬性

- 盡快做出能用的版本：37a：C（如果框架有）最快，B 設定好後最省事，A 一開始最快、頁面多了就慢；37b：B 現成元件最多，A 次之，C 最慢
- 學習價值與作品集：37a B 是常見做法；37b A 學到的最多（Tailwind、元件組成），也是 FastAPI 官方範本的選擇
- 結果準確可信：37a 的 B、C 比較不會出現「畫面顯示舊資料」（例如改了個人資料，評分還是舊的）

### 6. 可逆性

中等：資料抓取的寫法會散在每一頁，之後換要改每一頁；元件庫換掉要重新做所有畫面的樣式，複製進專案的元件因為原始碼在手上，綁得最少。

### 7. 原本的狀態與改完後

- 現在：沒有前端
- 37a A：沒有新套件；B：`package.json` 多 `@tanstack/react-query`（或 Vue 版）；C：沒有新套件
- 37b A：`components.json`＋`src/components/ui/`（複製進來的元件）＋Tailwind；B：`package.json` 多一個元件庫；C：Tailwind＋daisyUI，或只有自己的 CSS

### 追問：#35 選 A 之後，37a 的選項

37a 的 C「框架內建」原本只寫了 Next.js 和 HTMX；#35 選了 A（React＋Vite）之後，對應的「內建」是**路由內建的資料載入**（2026-10-25 查證）：

- **React Router 8 的 Data mode**：每個頁面可以有 `loader`（進頁面前先抓資料）、`action`（處理表單送出），也有等待中的狀態；用 `createBrowserRouter`，不需要額外的 Vite 外掛（只有 Framework mode 才要）
- **TanStack Router**：路由的 loader 內建快取（先顯示舊資料、背景重抓）；官方文件寫明它沒有「不同頁面之間共用快取與去除重複請求」，需要的話建議搭配 TanStack Query（FastAPI 官方範本就是兩個一起用）

選 A 之後的 37a：

| | A fetch | B TanStack Query | C 路由內建的 loader |
| --- | --- | --- | --- |
| 怎麼運作 | 每頁自己抓、自己記載入中與錯誤 | 用 `useQuery`、`useMutation`，快取與失效內建 | 進頁面前由路由的 loader 抓好資料 |
| 改完個人資料，回到評分列表 | 要自己記得重抓 | 宣告「評分失效」就自動重抓 | React Router：送出表單（action）後，頁面上的 loader 自動重跑（官方文件）；TanStack Router 這次沒查證 |
| 不同頁面共用同一份資料 | 自己處理 | 共用快取 | TanStack Router 不共用（官方文件寫的） |
| 多學的觀念 | 少 | 查詢鍵、失效 | 路由的 loader、action |

來源：React Router「Picking a Mode」（8.5.0）與「Actions」、TanStack Router「Data Loading」（2026-10-25、26 查證）

## #43 本機網頁的存取安全

### 1. 這題在決定什麼

網頁和 API 要防到什麼程度，讓你的個人資料和會花錢的問答只有你自己用得到。

### 2. 先懂的概念

- **要保護的東西**：個人資料（`GET/PUT /api/profile`：國籍、學位、科系）、評分與理由（`GET /api/matches`，理由會提到科系）、第 9 天的問答（每題約 NT$0–0.3，第 5 天實測）、第 10 天的設定（費用上限）
- **綁定位址**：伺服器「聽」哪個網路位址。uvicorn 預設只聽 `127.0.0.1`（這台電腦自己），同一個 Wi-Fi 的其他裝置連不到；改成 `0.0.0.0` 才會開放給區網。Vite 開發伺服器預設是 `localhost`。我們的 PostgreSQL、Redis 已經只綁 `127.0.0.1`（`docker-compose.yml`）
- **你逛的其他網站也在同一個瀏覽器裡**：惡意網頁可以叫你的瀏覽器對 `127.0.0.1:8000` 送請求
  - **CORS（跨來源資源共用）只管「別的網站能不能讀到回應」，不管「請求會不會送出」**。「簡單請求」（GET、HEAD、POST，內容是表單或純文字）不會先問就直接送出，這就是 **CSRF（跨站請求偽造）**
  - **FastAPI 已有的防護**（已確認我們的版本 0.143.0）：只把 `Content-Type: application/json` 的內容當 JSON 解析（0.65.2 起，修 CVE-2021-32677）；沒有 Content-Type 的也不解析（0.132.0 起預設 `strict_content_type=True`）。所以「收 JSON 的 API」擋得住表單式的 CSRF；只靠網址參數的 API（例如 `GET /api/ask?q=...`）擋不住
  - **DNS rebinding（DNS 重新綁定）**：惡意網域先指到攻擊者的伺服器，網頁載入後再改指到 `127.0.0.1`。瀏覽器把它當成「同一個網站」，就能讀回應（讀到個人資料）、呼叫問答。但請求的 Host 標頭仍然是攻擊者的網域，所以**檢查 Host 標頭**就擋得掉（Starlette 的 `TrustedHostMiddleware`，不符合就回 400）。Chrome 94 起已經不讓不安全（http）的公開網站連到本機，所以用 Chrome 時這招會被擋（Vite 的資安公告也這樣寫）；Safari 沒有這層保護
- **瀏覽器自己的保護（2026-10）**：Chrome 142（2025-10-28）起，公開網站要連 localhost 或區網，要你先按「允許」（Local Network Access）；但最上層的表單送出（整頁跳轉）不在管制內。Firefox 151（2026-05）開始逐步推出；Safari 還沒有
- **Cookie 的 SameSite**：瀏覽器自動附上 cookie；`localhost:5173` 和 `localhost:8000` 算「同一個 site」（不看連接埠），所以 SameSite 分不開本機的不同程式
- **這台電腦上的其他程式**：用同一個帳號執行的程式，通常也讀得到 `backend/.env`；權杖或密碼如果放在那裡，擋不住已經在電腦裡的惡意程式
- 限制條件「個資不外流」（ADR-001）和這題有關

來源：uvicorn 設定文件；Vite server options；MDN 的 CORS、Same-origin policy、Site；FastAPI 的 GHSA-8h2j-cgx8-6xv7 與 Strict Content-Type 文件；Vite GHSA-vg6x-rcgg-rjx6；Chrome 142 release notes 與 Local Network Access 部落格；Firefox 151 release notes；WebKit bug 250607；OWASP CSRF Prevention Cheat Sheet（都在 2026-10-25 查證）

### 3. 選項

**A 維持現況：只靠綁 127.0.0.1**

- 怎麼運作：不加任何檢查；FastAPI 預設的 JSON 檢查照舊
- 好處：0 工作量
- 代價：用 Safari（或 Firefox 還沒推到你的時候）逛到惡意網站，DNS rebinding 讀得到個人資料、呼叫得了問答；用網址參數的 API 擋不住 CSRF（Chrome 142 起會先問你，Safari 不會）
- 在這個專案：用 Safari 時，和限制條件「個資不外流」有一條沒擋的路

**B 檢查 Host 標頭＋CORS 只允許自己的前端＋會寫入或花錢的 API 一律收 JSON（不登入）**

- 怎麼運作：加 `TrustedHostMiddleware`（只允許 `localhost`、`127.0.0.1`）；前後端分開跑時，CORS 只允許前端的網址；寫一條程式規範：「寫入資料或會花錢的 API 用 POST/PUT 收 JSON」
- 好處：擋得住區網、DNS rebinding、別的網站讀資料、表單式的 CSRF；約 1 小時
- 代價：擋不住這台電腦上的其他程式；每個新 API 都要遵守那條規範（漏了就有洞）
- 在這個專案：`app/main.py` 多 1–2 行，CLAUDE.md 的程式規範多一條

**C B＋存取權杖（token）**

- 怎麼運作：每個請求都要帶一個自訂標頭（例如 `X-API-Token`），值存在 `backend/.env`。自訂標頭會讓瀏覽器先發預檢（preflight），惡意網站過不了
- 好處：不必完全靠「每個 API 都收 JSON」的紀律；沒有權杖的本機程式也進不來
- 代價：前端要拿到並保存權杖；讀得到 `.env` 的程式一樣拿得到；約半天
- 在這個專案：每個 API 多一個檢查（FastAPI 的 `APIKeyHeader`），前端每個請求附上標頭

**D B＋登入（密碼＋HttpOnly 的 session cookie）**

- 怎麼運作：登入頁輸入密碼（雜湊存在 `.env`），登入後拿到一個簽章過的 cookie（Starlette `SessionMiddleware`，預設 SameSite=Lax、兩週到期）
- 好處：最接近公開版會用的做法（#44 上雲前要有）；作品集看得到登入流程
- 代價：登入頁、登出、過期處理、密碼雜湊；cookie 會自動附上，所以仍然需要 B 的 CSRF 防護；約 1 天
- 在這個專案：多一個登入頁和 session 設定，每兩週登入一次

### 4. 選了會怎樣

| 情境 | A 現況 | B Host＋CORS＋JSON | C B＋權杖 | D B＋登入 |
| --- | --- | --- | --- | --- |
| 同一個 Wi-Fi 的其他裝置 | 連不到 | 連不到 | 連不到 | 連不到 |
| 惡意網站用 DNS rebinding 讀個人資料 | Chrome 擋下；Safari 讀得到 | 擋下（400） | 擋下 | 擋下 |
| 惡意網站送表單到收 JSON 的 API | 擋下（FastAPI 不解析） | 擋下 | 擋下 | 擋下 |
| 惡意網站用網址參數觸發問答（花錢） | 送得出去（Chrome 會先問你，Safari 不會） | 依規範不會有這種 API | 擋下（沒有權杖） | 依規範不會有這種 API |
| 這台電腦上的其他程式 | 連得進來 | 連得進來 | 沒權杖就擋（讀得到 `.env` 的除外） | 沒密碼就擋（讀得到 `.env` 的除外） |
| 每天使用 | 直接開 | 直接開 | 直接開 | 每兩週登入一次 |
| 工作量 | 0 | 約 1 小時 | 約半天 | 約 1 天 |

### 5. 對照品質屬性

- 盡快做出能用的版本：A 最快；B 只多約 1 小時；C、D 更慢
- 學習價值與作品集：D 最多（登入、session）；B、C 練威脅建模（CSRF、DNS rebinding、CORS 的真正用途）；A 沒有
- 結果準確可信：和這題關係不大
- 限制條件「個資不外流」：A 在 Safari 上有一條讓惡意網站讀到個人資料的路（DNS rebinding），B、C、D 不管哪個瀏覽器都擋住了

### 6. 可逆性

可回頭：B、C 都是加減幾行設定；D 多了登入頁，拿掉要刪頁面和 session 設定。之後上雲（#44）時，D 的做法要重新評估（例如改用雲端的身分驗證）。

### 7. 原本的狀態與改完後

- 現在：uvicorn 只聽 `127.0.0.1`；PostgreSQL、Redis 只綁 `127.0.0.1`；FastAPI 只把 JSON 當 JSON 解析；沒有 CORS、沒有 Host 檢查、沒有登入；macOS 防火牆是關的（只有綁 `0.0.0.0` 時才有差）
- A：不變
- B：`app/main.py` 從

  ```python
  app = FastAPI(title="留學獎學金 Agent")
  ```

  變成

  ```python
  app = FastAPI(title="留學獎學金 Agent")
  # 只接受 Host 是本機的請求：擋 DNS rebinding
  app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
  ```

  （前後端分開跑時再加 `CORSMiddleware`，只允許前端的網址）
- C：B＋`.env` 多一個 `API_TOKEN`，每個 API 檢查 `X-API-Token` 標頭
- D：B＋`/login` 頁、session cookie、`.env` 多密碼雜湊與簽章金鑰

### 追問：用 Google 登入

你問：能不能直接綁 Google 帳號？搜尋不用登入，個人推薦、通知、agent、申請追蹤才要登入；Google 是怎麼做到防護的，還是這是不一樣的東西？

**可以，做法叫「用 Google 登入」**。技術上是 OpenID Connect（建立在 OAuth 2.0 上的身分驗證標準），Google 的實作通過 OpenID 認證。流程：

1. 你按「用 Google 登入」，瀏覽器跳到 Google 的登入頁；密碼只輸入在 Google
2. 登入後，Google 帶著一次性的代碼跳回我們事先登記的網址（redirect URI）。Google 規定這個網址要用 HTTPS，但 localhost 例外
3. FastAPI 用這個代碼加上 client secret（放 `backend/.env`），向 Google 換一張 ID token：Google 簽章過的身分證明，寫著你是誰、你的 email
4. FastAPI 檢查 ID token：簽章是 Google 的、發行者 `iss` 是 Google、對象 `aud` 是我們的 client ID、還沒過期 `exp`。通過後，發一個**我們自己的** session cookie
5. 之後每個請求，都靠這個 session cookie 認出你；這一段是我們程式的事，和 Google 無關

FastAPI 可以用 Authlib 這個函式庫做（有 Starlette／FastAPI 的官方範例；它用 SessionMiddleware 暫存登入流程的 `state`）。

**是兩層不一樣的東西**：

- **Google 負責「你是誰」（身分驗證）**：保管密碼、兩步驟驗證、可疑登入偵測。登入流程本身也有防護：代碼只送回事先登記的網址；`state` 防止登入流程被偽造；`nonce` 防止同一張 token 被重複使用；ID token 有 Google 的簽章
- **#43 的威脅是「這個請求是不是你從自己的網頁送出的」**：CSRF、DNS rebinding、同一個 Wi-Fi 的裝置。登入後，瀏覽器會自動附上 session cookie，所以惡意網站叫你的瀏覽器送出的請求，一樣帶著 cookie。所以登入之後，B 的 Host 檢查與「寫入用 JSON」規則還是需要
- 登入確實多補了一塊：DNS rebinding 的網頁是另一個網域，瀏覽器不會附上我們的 cookie，所以要登入的 API 它讀不到

**你說的「公開區＋登入區」**：搜尋、列表、詳細頁不用登入；個人資料、評分與推薦理由、通知設定、問答（會花錢）、第 10 天的設定與 agent 要登入。申請追蹤在 spec 排在 v2。

多一個選項 E，和原本的比較：

| | B 不登入 | D B＋自己的密碼登入 | E B＋用 Google 登入（公開區＋登入區） |
| --- | --- | --- | --- |
| 誰保管密碼 | 沒有密碼 | 我們（雜湊存在 `.env`） | Google；我們的程式看不到密碼 |
| 兩步驟驗證、可疑登入偵測 | 無 | 要自己做 | 用 Google 帳號本身的設定 |
| 沒網路時 | 照常 | 照常 | 已登入的 session 照常；session 過期時要連網才能重新登入（電腦白天常沒網路，ADR-057） |
| 要設定的 | 1–2 行 middleware | 登入頁、密碼雜湊、session、登出 | Google Cloud 專案、OAuth 同意畫面、OAuth 用戶端、登記 redirect URI、session、登出、驗證 ID token |
| CSRF、DNS rebinding | B 的防護 | 仍需要 B | 仍需要 B |
| 之後的公開版（多人） | 要另外做登入 | 要再做註冊、忘記密碼 | 多人登入直接沿用 |
| 個人資料 | 不涉及 | 不涉及 | 登入時 Google 會知道你在用這個應用程式；你的國籍、科系等不會給 Google；本機資料庫會存你的 Google 帳號 ID 與 email |
| 工作量（估計） | 約 1 小時 | 約 1 天 | 約 1 天（含 Google Cloud 設定） |

和限制條件「不送可識別個人的資料到雲端」的關係：E 登入時，會和 Google 交換你的身分（Google 帳號 ID、email），這些是 Google 原本就有的資料；獎學金的個人資料（國籍、學位、科系）不會送出。

來源：Google「OpenID Connect」與「Using OAuth 2.0 for Web Server Applications」（redirect URI 規則、client secret 的保管）；Authlib 的 Starlette OAuth Client 文件與 FastAPI Google 登入範例（2026-10-26 查證）

## #35b 使用者的搜尋方式

### 1. 這題在決定什麼

列表頁的搜尋框，打字之後用哪種方式找獎學金。篩選（國家、學位、還能申請、截止日）和排序本來就會做（spec：列表要排序與篩選），問答頁也照 spec 做；這題只決定「打字搜尋」。

### 2. 先懂的概念

- **篩選**：勾選條件，資料庫比對欄位，結果精確、可以預期。第 5 天問答的「條件篩選」路線已經有一張篩選表（國籍、學位、國家、截止日範圍、只看還能申請的），網頁可以直接用，不必經過 AI
- **關鍵字搜尋**：比對字面，字要一模一樣才找得到。我們的資料：名稱和領域幾乎都是英文；185 筆有 AI 翻譯的中文名稱；領域欄位沒有中文
- **語意搜尋**：第 5 天做好的 `find`。把搜尋的句子變成向量（一串代表意思的數字），找意思最接近的獎學金，所以中英文、同義詞都找得到；但它一定會排出結果，就算都不相關
- **混合搜尋（hybrid search）**：關鍵字和語意各找一次，再把兩份名次合併。常見的合併方法叫 Reciprocal Rank Fusion（RRF）：每份名單裡排第幾名就給幾分（名次越前分越高），加總後排序。RAG 系統很常用
- **費用與網路**：語意搜尋每次要把句子送到 Gemini 算向量。依第 5 天約 510 萬字元花 NT$10–15 換算，一句話不到 NT$0.001；沒網路就不能用。搜尋的字會送到雲端：一般不是個人資料，但如果在搜尋框打了個人資料，也會送出去

實測（10-25，關鍵字比對名稱、中文名稱、領域；語意用 `find`）：

| 搜尋的字 | 關鍵字 | 語意（前幾名與相似度） |
| --- | --- | --- |
| 資料科學 | 3 筆 | EMLDS 0.68、BDMA 0.67、NeuroData 0.67、DEAI 0.67、CoDaS 0.66 |
| 數據科學（另一種說法） | 0 筆 | EMLDS 0.68、BDMA 0.67、NeuroData 0.66 |
| data science | 6 筆 | （沒測） |
| DEAI（學程簡稱） | 1 筆 | DEAI 0.69，接著是不相關的 IMBRSEA 0.64、EMILDAI 0.63 |
| 烹飪（沒有相關的） | 0 筆 | 還是列出 MBUILD 0.62、WINTOUR 0.61、master-serp.eu 0.61 |

不相關結果的相似度（0.61–0.62）和相關結果（0.66–0.69）差很少，很難訂一條「低於多少就不顯示」的線。

### 3. 選項

**A 只有篩選，沒有搜尋框**

- 怎麼運作：列表只有篩選條件和排序
- 好處：最快；結果完全可以預期；不送任何東西到雲端
- 代價：想找某個主題（例如資料科學）只能一筆一筆看，或改去問答頁問
- 在這個專案：第 9 天只做篩選表

**B 篩選＋關鍵字**

- 怎麼運作：搜尋框的字去比對名稱、中文名稱、領域、提供單位
- 好處：簡單、快、不花錢、沒網路也能用；打學程簡稱一定找得到
- 代價：要打對字才找得到（「數據科學」0 筆）；中文搜英文資料只能靠 AI 翻譯的中文名稱
- 在這個專案：列表 API 多一個查詢參數，約 1 小時

**C 篩選＋語意**

- 怎麼運作：搜尋框的字交給 `find`，依意思排序；可以和篩選條件一起用
- 好處：中英文、不同說法都找得到；第 5 天已經做好，只要包成 API
- 代價：一定會列出結果，不相關的也會出現（打簡稱 DEAI，第 1 名對，後面跟著不相關的）；要網路
- 在這個專案：包一個搜尋 API，約 1 小時

**D 篩選＋混合（關鍵字＋語意）**

- 怎麼運作：兩種各找一次，用 RRF 合併名次；字面完全符合的通常排前面
- 好處：兩種的優點都有；作品集上是常見、說得出名堂的做法
- 代價：最多程式；沒網路時只剩關鍵字；多一個要測試的合併規則
- 在這個專案：B 和 C 都做，再加合併，約半天

### 4. 選了會怎樣

| 情境 | A 只有篩選 | B 關鍵字 | C 語意 | D 混合 |
| --- | --- | --- | --- | --- |
| 打「資料科學」 | 沒有搜尋框 | 3 筆 | 一串資料相關的學程 | 資料相關的學程，名稱寫著資料科學的在前面 |
| 打「數據科學」 | 沒有搜尋框 | 0 筆 | 和「資料科學」幾乎一樣 | 和 C 一樣 |
| 打「DEAI」 | 沒有搜尋框 | 只有 DEAI | DEAI 第 1，後面跟著不相關的 | DEAI 第 1 |
| 打不相關的字 | 沒有搜尋框 | 0 筆 | 還是列出結果 | 還是列出語意的結果 |
| 沒網路 | 可用 | 可用 | 不能搜尋 | 只剩關鍵字 |
| 每次費用 | 0 | 0 | 不到 NT$0.001 | 不到 NT$0.001 |
| 第 9 天多的工作 | 0 | 約 1 小時 | 約 1 小時 | 約半天 |

### 5. 對照品質屬性

- 盡快做出能用的版本：A 最快；B、C 差不多；D 最慢
- 學習價值與作品集：D 最多（混合搜尋、合併排名）；C 把第 5 天的 RAG 搬上網頁；B、A 少
- 結果準確可信：A、B 結果都是真的符合；C、D 會混進不相關的結果，要靠排序和使用者判斷

### 6. 可逆性

可回頭：只影響列表的一個 API 和搜尋框，之後要加別種搜尋，不必改資料表。

### 7. 原本的狀態與改完後

- 現在：沒有網頁；`find` 只能在終端機用，問答的篩選表只給 AI 填
- A：列表 API 接受篩選參數（國籍、學位、國家、截止日、只看還能申請的）
- B：A＋`q` 參數做關鍵字比對
- C：A＋搜尋 API 呼叫 `find`，結果可以再套篩選
- D：B＋C＋合併名次

## #55 金額怎麼抽

### 1. 這題在決定什麼

獎學金的「金額」要怎麼存：維持一格自由文字，或改成一筆一筆的金額（數字、幣別、期間、用途，附原文引用）。這會決定列表上「大概的數字」準不準，以及能不能依金額排序或篩選。

### 2. 先懂的概念

- **抽取表格決定 AI 怎麼填**：現在的抽取表格只有一格「金額」文字。AI 讀完整頁後，要自己決定放哪一句；官網常同時寫著好幾個金額（生活津貼、學費、旅費、交換補助），AI 每次可能挑不同的（第 8 天變更雜訊的原因之一）
- **原文引用（evidence）**：截止日、國籍、學位都附逐字引用，程式確認引用真的在原文裡（ADR-008、011）；金額沒有引用，沒辦法核對
- 金額的變更已經不通知（ADR-064），這題只影響「網頁上怎麼顯示」和「準不準」
- 你之前的方向：列表只要大概的數字，點進去看詳情
- 現在的資料：188 筆裡 145 筆有金額文字、43 筆空白；文字長度中位數 25 字、最長 216 字。例子：

| 獎學金 | 現在存的金額 |
| --- | --- |
| ReSound | 1,400 EUR per month |
| PIONEER | 5,613.10 EUR for the 2025-2026 PIONEER intake (tuition fee); Erasmus+ grant around 419 euros for Germany during academic year 2024-2025（學費和交換補助，都不是獎學金本身給的錢） |
| 教育部 | 一般生每人每年核發 1 萬 6 千美元。勵學優秀生、原住民生及身心障礙生每人每年核發 3 萬美元。特殊教育生每人每年核發 2 萬美元。 |
| Master LIVE | （空白） |

### 3. 選項

**A 維持一格文字**

- 怎麼運作：不改；列表顯示截短的文字，詳細頁顯示全文
- 好處：不花錢、不改程式
- 代價：列表上的數字可能是學費或交換補助（PIONEER）；不能依金額排序或篩選；沒有引用可以核對
- 在這個專案：第 9 天直接用現有欄位

**B 一格文字，但要 AI 列出所有金額並寫清楚用途**

- 怎麼運作：改抽取提示詞，要求列出原文寫的每個金額，各自註明用途、期間與適用對象，仍存在同一格
- 好處：資料表不用改；詳細頁看得到完整的金額說明
- 代價：改提示詞要換版本號、全部重抽（約 NT$34，依第 6 天重抽 180 筆的費用）；還是文字，列表截短後大概的數字可能被截掉；不能排序或篩選；仍然沒有引用核對
- 在這個專案：改提示詞約 1 小時，加上背景重抽

**C 每個金額一筆，附用途和原文引用**

- 怎麼運作：抽取表格改成金額清單，每筆有數字、幣別、期間（每月、每年、一次）、用途（生活津貼、學費、旅費、其他）、適用對象、逐字引用；程式核對引用在原文裡，而且引用裡真的有這個數字
- 好處：列表可以挑一個有意義的數字顯示（例如每月生活津貼）；每個數字都查得到出處；同一種幣別內可以排序或篩選；和截止日、國籍、學位一樣可以核對
- 代價：要改資料結構、抽取表格、提示詞與驗證，全部重抽約 NT$34；列表挑哪一個數字、要不要換算幣別，還要再定規則
- 在這個專案：約半天，加上背景重抽。教育部會變成三筆：一般生每年 16,000 美元；勵學優秀生、原住民生、身心障礙生每年 30,000 美元；特殊教育生每年 20,000 美元

### 4. 選了會怎樣

| 情境 | A 一格文字 | B 列出所有金額 | C 每個金額一筆 |
| --- | --- | --- | --- |
| 列表上 PIONEER 顯示的金額 | 學費 5,613.10 EUR（截短） | 截短的第一段，可能還是學費 | 依規則挑一個（例如生活津貼）；沒有就顯示「見詳細頁」 |
| 依金額排序或篩選 | 不行 | 不行 | 同一幣別內可以 |
| 數字是不是 AI 編的 | 無法檢查 | 無法檢查 | 程式核對引用 |
| 重抽費用 | 0 | 約 NT$34 | 約 NT$34 |
| 第 9 天多的工作 | 0 | 約 1 小時＋重抽 | 約半天＋重抽 |

### 5. 對照品質屬性

- 盡快做出能用的版本：A 最快；B 次之；C 最慢
- 學習價值與作品集：C 最多（抽取表格設計、引用核對）；B 練提示詞；A 沒有
- 結果準確可信：C 最高（每個數字可核對）；B 資訊比較完整但不能核對；A 可能顯示錯的數字

### 6. 可逆性

可回頭：原始快照都留著（ADR-019），之後改選都能重抽，代價是一次重抽費用（約 NT$34）。C 多一個資料結構，改回來要刪掉。

### 7. 原本的狀態與改完後

- 現在：`scholarships.amount`、`scholarship_categories.amount` 各一格文字
- A：不變
- B：同樣兩格，內容變成完整的金額說明
- C：多一個金額清單（每筆：數字、幣別、期間、用途、適用對象、引用）；原本的文字欄位留著，或改由清單產生
