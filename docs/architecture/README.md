# 架構文件：從這裡開始

這一頁是整個專案架構的入口。下面六種視圖各回答一個問題；除了大地圖和設計決策是人寫的，其餘都由工具從程式碼或資料庫產生，CI 會檢查它們沒有過期。

## 六種視圖

| # | 想知道什麼 | 看哪裡 | 怎麼來的 |
| --- | --- | --- | --- |
| 1 | 整個系統有哪幾大塊、連到哪些外部服務 | [c4.md](c4.md) | 手寫 [workspace.dsl](workspace.dsl)，工具匯出成圖 |
| 2 | 後端提供哪些 API 端點 | [openapi.json](openapi.json)；啟動後端後開 <http://127.0.0.1:8000/docs> 可以互動操作 | 從 FastAPI 程式碼匯出 |
| 3 | 有哪些資料表、怎麼互相關聯 | [db/README.md](db/README.md)（ER 圖），每張表各有一頁 | tbls 讀資料庫的結構 |
| 4 | 前端的檔案誰 import 誰 | [frontend-deps.md](frontend-deps.md) | dependency-cruiser 讀 `frontend/src` |
| 5 | 後端的模組誰可以 import 誰 | [backend/.importlinter](../../backend/.importlinter)（規則本身就是文件） | 手寫規則，import-linter 檢查 |
| 6 | 為什麼這樣設計 | [docs/adr.md](../adr.md) | 手寫 |

在 GitHub 上直接點連結就能看圖：Mermaid 圖會自動顯示，不用裝任何東西。

## 每一種在看什麼

### 1 整體大地圖

用 C4 模型的前兩層。C4 是一套畫架構圖的慣例，像地圖的縮放：第 1 層看「這個系統和外面的人、外面的服務」，第 2 層放大看「系統裡各自獨立執行的幾大塊」（網頁前端、後端 API、背景 worker、資料庫、工作佇列）。更細的內容由下面的視圖 2 到 5 負責。

這張圖是人寫的：工具只能檢查 `workspace.dsl` 的語法與內容前後一致，檢查不了它和程式碼一不一致。加減外部服務或大方塊時，要記得改 `workspace.dsl`。

### 2 API 端點

`openapi.json` 是 OpenAPI 格式的 API 說明書：每個端點的網址、參數、回傳的資料形狀。它是排版過的 JSON，改了端點後看 `git diff` 就知道 API 哪裡變了。前端的 TypeScript 型別（`npm run gen:api`）也是從同一份匯出產生的。

### 3 資料表與關係

ER 圖（Entity-Relationship，實體關係圖）畫出每張表和表之間的外鍵。資料表的來源是 `backend/migrations/` 的遷移腳本；tbls 連到跑完 `alembic upgrade head` 的資料庫，只讀結構，不讀任何一列資料。

### 4 前端模組依賴

兩張圖：按資料夾（`pages`、`components`、`api`、`lib`）的總覽，和按檔案的細節。箭頭 A --> B 表示 A import 了 B。另外有規則檢查，目前會擋的是：循環依賴（A import B、B 又 import A）和沒有被任何檔案用到的孤兒檔案。規則在 [frontend/.dependency-cruiser.cjs](../../frontend/.dependency-cruiser.cjs)。

### 5 後端分層規則

兩條規則：

1. **分層**：`features` → `core` → `shared`。上層可以 import 下層，反過來不行。
2. **功能互相獨立**：`features/` 底下 12 個功能原則上不互相 import。

第 2 條在 2026-11-28 有 53 條既有的依賴，逐條列在 `.importlinter` 的 `ignore_imports`（豁免清單）。這份清單就是技術債清單：新增第 54 條會讓檢查失敗；重構拿掉某一條後，要把那一行刪掉，否則檢查也會失敗。

## 重新產生

```bash
scripts/gen-docs.sh            # 全部
scripts/gen-docs.sh backend    # 只做 API 端點與資料表
scripts/gen-docs.sh frontend   # 只做前端依賴圖
scripts/gen-docs.sh c4         # 只做大地圖
```

需要先準備好：

- `backend`：`docker compose up -d`、`uv run alembic upgrade head`，並安裝 tbls（`brew install k1LoW/tap/tbls`）
- `frontend`：`npm ci`
- `c4`：Docker 開著

什麼時候要跑：

| 你改了什麼 | 跑哪個 |
| --- | --- |
| API 的路由或回傳的資料形狀 | `scripts/gen-docs.sh backend` |
| 資料表（新的遷移腳本） | `scripts/gen-docs.sh backend` |
| 前端檔案之間的 import | `scripts/gen-docs.sh frontend` |
| `workspace.dsl` | `scripts/gen-docs.sh c4` |

跑完把 `docs/architecture/` 裡的變動一起提交。

## CI 怎麼檢查

每次推送，`.github/workflows/ci.yml` 會跑 `scripts/check-docs.sh`：它先跑同一個 `scripts/gen-docs.sh`，再看 `docs/architecture/` 有沒有變動。有變動就代表提交的文件比程式碼舊，CI 失敗；在本機重新產生、提交就會通過。

| 視圖 | CI 的檢查 | 本機自己檢查 |
| --- | --- | --- |
| 1 大地圖 | DSL 通過驗證；重新匯出後沒有變動 | `scripts/check-docs.sh c4` |
| 2 API 端點 | 重新匯出後沒有變動 | `scripts/check-docs.sh backend` |
| 3 資料表 | 重新產生後沒有變動 | `scripts/check-docs.sh backend` |
| 4 前端依賴 | 規則通過；重新產生後沒有變動 | `cd frontend && npx depcruise src`、`scripts/check-docs.sh frontend` |
| 5 後端分層 | 規則通過 | `cd backend && uv run lint-imports` |
| 6 設計決策 | 不檢查 | |

`scripts/check-docs.sh` 不加參數就是全部檢查。
