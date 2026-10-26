# #35 前端框架：完整中立比較（decision brief）

你的問題：#35 前端框架的四個選項，做一份完整的中立比較。沒有哪個設定或一行改動能解決這題，一定要選一套前端技術。

本檔只放中立的比較，不給推薦；你要求的「我的選擇」在對話裡另外回答。事實都在 2026-10-25 對照官方或原始來源查證（見最後的延伸閱讀），版本與數字以那天為準。選項依「要動的東西」由少到多排列（這是複雜度的順序，不是偏好的順序）：D → C → A → B。

## 1. 決定

**問題**：第 9 天起的網頁介面（列表、詳細頁、個人資料、搜尋、問答；第 10 天的設定與成本統計）要用哪一套前端技術？

**決策因素**：每一項後面附上它在 ISO/IEC 25010:2023 對應的品質特性。這是國際標準的軟體產品品質模型，2023 版有 9 個特性：功能適合性、效能效率、相容性、互動能力、可靠性、安全性、可維護性、彈性、安全保障。

| 因素 | 為什麼在這個專案重要 | ISO/IEC 25010 |
| --- | --- | --- |
| 做出第一版的時間 | 品質屬性第一項「盡快做出能用的版本」（ADR-001）；第 9 天就要用 | 不是產品品質，是專案時程（標準不涵蓋開發速度） |
| 看得懂、改得動 | Claude 寫、你讀，之後你也要能改 | 可維護性：可分析性（analysability）、可修改性（modifiability） |
| 要安裝與執行的東西 | 背景程式由 launchd 管（ADR-061）；每多一個程式就多一個會停的地方 | 彈性：可安裝性（installability）；可靠性：可用性（availability） |
| 安全 | 個人資料與會花錢的問答（#43）；套件來源的風險 | 安全性：機密性（confidentiality）、完整性（integrity）、抗攻擊性（resistance） |
| 欄位錯誤在哪裡被抓到 | 品質屬性「結果準確可信」；前後端欄位不一致會讓畫面顯示錯（#36） | 功能適合性：功能正確性（functional correctness） |
| 畫面互動 | 問答要等幾秒、篩選與搜尋、第 10 天的圖表 | 互動能力：可操作性（operability） |
| 學習價值與作品集 | 品質屬性第二項（ADR-001） | 專案目標，標準裡沒有對應 |
| 之後換掉的成本 | 公開版、上雲（#44）時可能要調整 | 彈性：可替換性（replaceability）；可維護性：模組化（modularity） |

不列為因素的：效能效率。資料只有 188 筆、只有你一個人在本機用，四個選項的速度差別在這裡感覺不到。

## 2. 在整個系統的位置

```text
官網 ──抓取──▶ 抽取＋驗證（Gemini）──▶ PostgreSQL ◀── 評分、通知（RQ worker，launchd 在背景跑）
                                          ▲
                                          │ SQL
                                  FastAPI（127.0.0.1:8000）
                                          ▲
                          ┌───────────────┴────────────────┐
                          │  #35 決定這一層：網頁怎麼產生   │
                          └───────────────┬────────────────┘
                                          ▼
                                  你的瀏覽器（網頁）
```

四個選項的差別在最下面這一段：

```text
D HTMX       瀏覽器 ◀──HTML 片段── FastAPI（Jinja2 模板）
C、A 單頁應用 瀏覽器裡的 JS 程式 ◀──JSON── FastAPI（也負責送出建好的 JS 檔）
B Next.js    瀏覽器 ◀──HTML／資料── Node 伺服器（Next.js）◀──JSON── FastAPI
```

- D：FastAPI 直接把畫面（HTML）做好送出，瀏覽器只負責顯示和換掉一小塊
- C、A：FastAPI 只送資料（JSON），畫面由瀏覽器裡的 JavaScript 程式組出來
- B：中間多一台 Node 伺服器，先向 FastAPI 拿資料、做好畫面，再送到瀏覽器

## 3. 比較表

依複雜度由少到多排列（不是偏好順序）。

| 因素 | D HTMX＋Jinja2 | C Vue＋Vite | A React＋Vite | B Next.js |
| --- | --- | --- | --- | --- |
| 第一版要寫的 | 模板＋HTMX 屬性；頁面直接呼叫現有的 Python 函式 | JSON API＋Vue 元件＋路由＋建置設定 | JSON API＋React 元件＋自選路由＋建置設定 | JSON API＋React 元件＋伺服器與瀏覽器元件的分界＋Node 伺服器 |
| 程式語言 | Python＋HTML（少量 JavaScript） | Python＋TypeScript | Python＋TypeScript | Python＋TypeScript |
| 做好後要跑的程式 | 1 個（FastAPI） | 1 個（FastAPI 用 `app.frontend()` 送出建好的檔案） | 1 個（同 C） | 2 個（Node＋FastAPI） |
| 開發時的伺服器 | 1 個 | 2 個（Vite＋FastAPI） | 2 個 | 2 個 |
| 要安裝的 | htmx（一個 JS 檔）、Jinja2 | Node.js＋npm 套件與它們的間接依賴 | 同 C | 同 C |
| 欄位錯誤在哪裡被抓到 | 在 Python 端；模板可設 `StrictUndefined` 改為報錯 | 編譯時（搭配 #36 的 B 或 C） | 同 C | 同 C |
| 同一個網址（#43 的 CORS） | 是 | 做好後是；開發時用 Vite 轉發 | 同 C | 瀏覽器只連 Node，Node 再連 FastAPI |
| npm 套件的供應鏈風險 | 幾乎沒有（不用 npm 也可以） | 有（2025-09 CISA 警示的那類攻擊） | 同 C | 同 C |
| 要跟的安全更新 | htmx、Jinja2 | Vue、Vite 與套件 | React、Vite 與套件 | Next.js（2026-07 起固定發安全更新）與套件 |
| 互動的上限 | htmx 作者：適合列表、表單、文字為主；不適合畫面上很多互相牽動的部分 | 完整的前端框架 | 完整的前端框架 | 完整的前端框架＋伺服器端渲染 |
| 第 10 天的成本圖表 | 另外載入一個 JavaScript 圖表庫 | 用 Vue 的圖表套件 | 用 React 的圖表套件 | 用 React 的圖表套件 |
| 用過的人（Stack Overflow 2026） | 5.4% | 17.2% | 41.5% | 20.6% |
| 滿意（State of JS 2025） | 69% | 84% | 72% | 55% |
| 改主意的成本 | 模板改寫成元件，另外補 JSON API | 元件重寫；JSON API 與型別契約可沿用 | 同 C | 同 C，再加拿掉 Node 伺服器 |

## 4. 各選項

### D HTMX＋Jinja2（FastAPI 直接產生網頁）

**是什麼**：伺服器把整頁或一部分的 HTML 做好再送到瀏覽器。Jinja2 是 Python 的模板工具，把資料填進 HTML；HTMX 是一個 JavaScript 檔，讓按鈕、表單送出請求後，只把回來的 HTML 換進頁面的某一塊（例如只換掉搜尋結果）。比喻：廚房（伺服器）直接把做好的菜端上桌，你只說「這盤換一下」。

**軟體工程背景**：

- 這是伺服器端渲染（SSR）。web.dev 的定義：在伺服器產生 HTML 送給瀏覽器，而不是送 JavaScript；送到瀏覽器的 JavaScript 比較少
- htmx 作者稱這種做法為超媒體驅動的應用（Hypermedia-Driven Application）。網頁最早就是這樣運作
- 作者自己寫的適用範圍（2022-10-23）：
  - 適合：以文字和圖片為主的介面、CRUD 型的應用（新增、讀取、修改、刪除）、更新範圍是明確區塊的畫面
  - 不適合：畫面上很多部分互相牽動（例如試算表）、需要離線使用、狀態更新非常頻繁（例如滑鼠操作的遊戲）、想用 shadcn 這類為 React 設計的元件庫

**在這個專案怎麼運作**：

- FastAPI 多一個 `app/web/`，路由回傳模板
- 列表的篩選用 `hx-get` 換掉結果區塊；問答頁用 `hx-post` 送出問題，用 `hx-indicator` 顯示「等待中」
- 頁面直接呼叫現有的 Python 函式（篩選表、`find`、`ask`）
- 第 10 天的圖表另外載入一個 JavaScript 圖表庫

**優點**：

- 一個程式、一種語言
- 不用 Node、不用建置、不用 npm 套件
- 同一個網址，#43 不需要 CORS
- #36 不需要型別契約

**缺點**：

- 練不到前端框架，作品集上的前端分量低
- 用的人最少（Stack Overflow 2026 5.4%）
- 不能用 shadcn 這類元件庫（作者自己寫的）
- htmx 4 已經發表：2 版會一直支援，但新功能在 4
- 欄位錯誤要靠 Python 端的測試或 `StrictUndefined` 抓

**適合的情況**：介面以列表、表單、文字為主；只有一個人在本機用；想把學習時間留給 AI 的部分。

**改主意的成本**：之後換成單頁應用，所有模板要改寫成元件，還要補一套 JSON API（現在頁面直接呼叫 Python 函式）；Python 函式本身可以沿用。

### C Vue＋Vite（單頁應用）

**是什麼**：瀏覽器下載一個用 Vue 寫的 JavaScript 程式，畫面在瀏覽器裡組出來，資料用 JSON 向 FastAPI 要。Vite 是開發與建置工具：開發時即時更新畫面，完成後打包成靜態檔。比喻：廚房只把食材（JSON）端上桌，桌上有一位廚師（瀏覽器裡的程式）現場組合。

**軟體工程背景**：

- 這是單頁應用（SPA），也叫瀏覽器端渲染（CSR）。web.dev 的定義：在瀏覽器裡用 JavaScript 修改畫面
- web.dev 列的主要缺點：JavaScript 的量會隨著應用變大而增加
- 前後端分離（後端只提供 API、前端獨立）是常見架構；FastAPI 官方全端範本也是這樣
- 已知的失敗模式：
  - 前後端的資料形狀不同步（#36 處理）
  - 畫面上的資料和伺服器不一致，例如改了資料沒重抓（#37 的快取與失效處理）
  - JavaScript 檔越來越大
- Vue 官方自己提供路由（Vue Router）與狀態管理（Pinia）

**在這個專案怎麼運作**：

- 新增 `frontend/`（Vite＋Vue＋TypeScript），每個頁面一個 `.vue` 檔
- 開發時 Vite 把 `/api` 轉發到 FastAPI
- 做好後 `vite build`，由 FastAPI 的 `app.frontend("/", directory=...)` 提供（我們的 FastAPI 0.143.0 已確認有這個功能）

**優點**：

- 模板寫法接近 HTML
- 滿意度高（State of JS 84%）
- 路由與狀態管理有官方的，要選的東西少
- 做好後仍然只有一個程式

**缺點**：

- 多一套語言與工具（TypeScript、Vite、npm 套件與它們的安全更新）
- 開發時兩個伺服器
- 用的人比 React 少（Stack Overflow 2026 17.2%）
- 元件庫要注意授權（PrimeVue 5 改成商業授權）

**適合的情況**：想練前端框架，而且偏好接近 HTML 的寫法。

**改主意的成本**：換成 React 要重寫所有元件，JSON API 與型別契約可以沿用；換成 HTMX 要把頁面改回模板。

### A React＋Vite（單頁應用）

**是什麼**：和 C 一樣是單頁應用，改用 React 寫。畫面用 JSX（在 JavaScript 裡寫像 HTML 的標籤）描述；會變的資料用 hooks（例如 `useState`）管理。

**軟體工程背景**：

- 和 C 一樣是單頁應用，失敗模式也相同
- React 官方文件建議新專案先用框架，也說明了用 Vite 從頭建的做法；從頭建時，路由、資料抓取要自己選
- FastAPI 官方全端範本（2026-10-15 更新）就是這套，可以直接當參考結構：
  - React 19.3＋TypeScript＋Vite 8
  - TanStack Router 與 TanStack Query
  - Tailwind 4＋shadcn/ui
  - 用 Hey API 產生呼叫程式
  - 建置後由 `app.frontend()` 提供
- 多一個已知的失敗模式：路由、資料抓取、表單都要自己選套件，選擇多

**在這個專案怎麼運作**：

- 新增 `frontend/`（Vite＋React＋TypeScript），其他和 C 一樣
- 可以照官方範本的結構排資料夾

**優點**：

- 用的人最多（兩份問卷都第一）
- FastAPI 官方範本同一套，有現成的參考
- 元件庫選擇最多（shadcn/ui 等）
- 做好後仍然只有一個程式

**缺點**：

- 要學的東西多（JSX、hooks、路由、建置）
- 路由與資料抓取要自己選
- 要跟 npm 套件的安全更新
- 開發時兩個伺服器

**適合的情況**：想練用的人最多的前端框架、想讓作品集有前端分量、想照 FastAPI 官方範本的做法。

**改主意的成本**：和 C 一樣。

### B Next.js

**是什麼**：React 的全端框架。頁面預設在 Node.js 伺服器上執行（React Server Components），伺服器把結果送到瀏覽器；需要互動的部分標上 `'use client'`，在瀏覽器執行。

**軟體工程背景**：

- 這是伺服器端渲染加上瀏覽器端互動的混合
- 放在 Python API 前面的 Node 伺服器，類似 Backends For Frontends（BFF）模式。Sam Newman 2015 年的說法是每一種使用者體驗一個專屬後端（"one experience, one BFF"）
- 已知的失敗模式：
  - 伺服器元件與瀏覽器元件的分界容易搞混（官方文件專門有一章說明）
  - 多一個伺服器，就多一份攻擊面與安全更新：2025-12 有 React Server Components 的嚴重漏洞（CVE-2025-66478），Next.js 2026-07 起固定發安全更新
  - 輸出成靜態檔的話，伺服器端功能都不能用

**在這個專案怎麼運作**：

- `frontend/` 是 Next.js 專案
- Node 伺服器向 FastAPI 拿資料
- launchd 多管一個 Node 伺服器
- #43 要保護兩個伺服器

**優點**：

- 伺服器端渲染、串流、路由都內建
- 屬於 React 生態
- 用的人多（Stack Overflow 2026 20.6%）

**缺點**：

- 兩個後端（Node＋Python）要啟動、更新、保護
- 要懂的觀念最多
- 滿意度最低（State of JS 55%）
- 固定的安全更新要跟

**適合的情況**：想練 Next.js 本身，或打算之後讓前端伺服器做更多事（例如公開版的頁面渲染）。

**改主意的成本**：換成 A 要把伺服器元件改成瀏覽器元件，並拿掉 Node 伺服器；JSON API 可以沿用。

## 5. 取捨

| 選項 | 得到 | 放棄 |
| --- | --- | --- |
| D | 最少的東西要裝、要跑、要保護（可安裝性、安全性） | 前端框架的學習與作品集分量；互動上限（互動能力） |
| C、A | 完整的前端框架、編譯時的型別檢查（功能正確性、互動能力、學習價值） | 多一套語言與工具（可安裝性、安全性的供應鏈）；第一版比較慢 |
| A 比起 C | 用的人更多、和官方範本同一套 | 要自己選的套件更多 |
| B | 伺服器端渲染、React 全端經驗 | 多一個後端：可用性（多一個會停的程式）、安全性（攻擊面與更新）、可維護性（觀念最多） |

互相拉扯的品質特性：

- **學習價值與作品集 ↔ 可安裝性、安全性**：工具越多，學得越多，要裝、要更新、要防的也越多
- **功能正確性（編譯時型別檢查）↔ 第一版的時間**：型別契約要多一個產生步驟
- **互動能力 ↔ 可維護性**：互動越複雜，越需要完整的前端框架；但框架本身也是要維護的東西

## 6. 想一想的問題

以下問題都沒有標準答案，用來幫你衡量各項因素。

1. **前端是你這個專案想練的技能，還是「能用的介面」就好？**
   - 為什麼重要：決定「學習價值」這一項要不要算進前端
   - 影響：D 對上 A、B、C
2. **你讀程式時，Python 模板（HTML 加一點標記）和 TypeScript 元件，哪個比較容易看懂？**
   - 為什麼重要：Claude 寫、你讀，看得懂才改得動（可維護性）
   - 影響：D、C 的寫法最接近 HTML，A、B 是 JSX
3. **公開版（給別人用）大概會不會做、什麼時候？**
   - 為什麼重要：公開版要登入、多人，可能還有手機版
   - 影響：A、B、C 的 JSON API 可以給其他用戶端用；D 的頁面和伺服器綁在一起，要另外補 API
4. **能接受電腦上多 Node 和 npm 套件，並定期更新（含安全更新）嗎？**
   - 為什麼重要：可安裝性與安全性
   - 影響：A、B、C；B 還多一個背景伺服器
5. **第 10 天之後的畫面，互動會多複雜？**（例如圖表、拖拉、即時更新）
   - 為什麼重要：互動越多，D 越難寫
   - 影響：D 的上限
6. **第 9 天你希望花多少時間在前端？**
   - 為什麼重要：品質屬性第一項
   - 影響：D 最短，B 最長

## 7. 名詞解釋

- **單頁應用（SPA，Single-Page Application）**：瀏覽器只載入一次程式，之後換頁、更新都由瀏覽器裡的 JavaScript 處理
- **瀏覽器端渲染（CSR，Client-Side Rendering）**：畫面由瀏覽器裡的 JavaScript 組出來
- **伺服器端渲染（SSR，Server-Side Rendering）**：畫面（HTML）在伺服器做好再送出
- **React Server Components（RSC）**：React 的一種元件，在伺服器上執行，結果再送到瀏覽器
- **HTMX**：一個 JavaScript 檔，用 HTML 屬性讓頁面只更新一部分
- **Jinja2**：Python 的模板工具，把資料填進 HTML
- **模板（template）**：留好空格的 HTML，執行時把資料填進去
- **Vite**：前端的開發伺服器與建置工具
- **建置（build）**：把原始碼打包成瀏覽器能直接載入的檔案
- **Node.js**：在電腦上執行 JavaScript 的程式；Vite、Next.js 都需要它
- **npm**：Node.js 的套件管理工具，也是套件的公開倉庫
- **間接依賴**：你裝的套件自己又用到的套件
- **供應鏈攻擊**：攻擊者把惡意程式放進大家會安裝的套件，例如 2025-09 的 Shai-Hulud（CISA 警示：超過 500 個 npm 套件被入侵，會偷開發者的金鑰）
- **TypeScript**：加上型別的 JavaScript，編譯時檢查型別
- **JSX**：在 JavaScript 裡寫像 HTML 的標籤（React 用）
- **hooks**：React 管理狀態與副作用的函式，例如 `useState`
- **元件（component）**：畫面上可重複使用的一塊
- **狀態（state）**：畫面上會變的資料，例如篩選條件
- **路由（router）**：網址對應到哪個頁面
- **同源與 CORS**：協定、網域、連接埠都一樣才算同源；CORS 決定其他來源能不能讀回應（#43）
- **OpenAPI**：描述 API 的標準格式；FastAPI 自動產生 `/openapi.json`（#36）
- **BFF（Backends For Frontends）**：專門為某個前端服務的後端
- **`app.frontend()`**：FastAPI 0.138 起的功能，讓 FastAPI 送出建置好的前端檔案
- **`StrictUndefined`**：Jinja2 的設定，模板用到不存在的欄位時報錯，而不是印成空白
- **launchd**：macOS 管理背景程式的系統（ADR-061）
- **ISO/IEC 25010**：國際標準的軟體產品品質模型，2023 版有 9 個品質特性

## 8. 延伸閱讀

- ISO/IEC 25010 的特性與子特性：<https://iso25000.com/en/iso-25000-standards/iso-25010>、2023 版的結構與改名（Portability 改為 Flexibility、Usability 改為 Interaction capability）：<https://quality.arc42.org/standards/iso-25010>
- web.dev，Rendering on the Web（Addy Osmani、Jason Miller，2019，2026-01-05 更新）：<https://web.dev/articles/rendering-on-the-web>
- htmx，When Should You Use Hypermedia?（Carson Gross，2022-10-23）：<https://htmx.org/essays/when-to-use-hypermedia/>
- htmx 文件：<https://htmx.org/docs/>；htmx 4 公告：<https://four.htmx.org/announcements/2026-08-28-htmx-4.0.0-is-released>
- FastAPI，Templates：<https://fastapi.tiangolo.com/advanced/templates/>；Frontend（`app.frontend()`）：<https://fastapi.tiangolo.com/tutorial/frontend/>
- FastAPI 官方全端範本：<https://github.com/fastapi/full-stack-fastapi-template>
- React，Creating a React App：<https://react.dev/learn/creating-a-react-app>
- Vite，部署靜態網站：<https://vite.dev/guide/static-deploy>
- Vue，Quick Start：<https://vuejs.org/guide/quick-start>
- Next.js，Server and Client Components：<https://nextjs.org/docs/app/getting-started/server-and-client-components>；Static Exports：<https://nextjs.org/docs/app/guides/static-exports>
- Sam Newman，Backends For Frontends（2015-11-18）：<https://samnewman.io/patterns/architectural/bff/>
- CISA，Widespread Supply Chain Compromise Impacting npm Ecosystem（2025-09-23）：<https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem>
- State of JS 2025：<https://2025.stateofjs.com/>；Stack Overflow Developer Survey 2026：<https://survey.stackoverflow.co/2026/technology>
