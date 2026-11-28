# 會自動更新的架構文件：實作計畫（2026-11-28）

狀態：**等使用者核准**。核准前不動任何程式碼、設定檔或 CI。

- 軌道：Everything else → Gates 1–3
- 分支：`feat/architecture-docs`（從 `main` 開；這次照任務說明開分支與 PR，不照專案 `CLAUDE.md` 的「直接在 main 提交」）
- 範圍：只加文件與檢查工具。不重構、不修架構違規。

## 使用者的決定（11-28）

| 題目 | 選擇 | 內容 |
| --- | --- | --- |
| 1 import-linter 嚴格程度 | a | 分層規則＋feature 互相獨立規則，現有 53 條依賴寫進豁免清單，只防止變更糟 |
| 2 大地圖工具 | A | Structurizr DSL。匯出的圖在 GitHub 顯示不好時，入口頁改用連結 |
| 3 文件過期時 | a | CI 只檢查，過期就失敗；本機重新產生後提交 |
| 4 圖的格式 | A | Mermaid |

這四個決定之後要追加成 ADR。這次不能動 `docs/adr.md`（使用者有未提交的修改），所以 ADR 文字放在完成報告裡，由使用者決定何時加。

## 查證過的事實（11-28）

| 項目 | 結果 |
| --- | --- |
| 後端分層 | `core` 只 import `shared`；`shared` 不 import 任何 `app.*`；沒有 `core`／`shared` → `features` |
| feature 之間 | 53 條依賴、13 對互相 import（表在本文件最後） |
| 前端 | `frontend/src` 共 30 個檔案；別名 `@/` → `src/`；TypeScript 5.9.3；Node 22 |
| OpenAPI | `python -m app.export_openapi` 印到標準輸出；目前 repo 裡沒有提交過的 OpenAPI 檔 |
| tbls | v1.97.0；`er.format: mermaid`；不需另裝 Graphviz；`exclude` 可排除資料表 |
| dependency-cruiser | 18.9.0；`--output-type mermaid`；`--init oneshot` 不互動；沒有安裝腳本 |
| import-linter | 2.17；合約類型 `layers`、`independence`；`ignore_imports` 支援萬用字元；沒對上的豁免預設報錯 |
| Structurizr | 舊 CLI 已封存；現用 `structurizr/structurizr:2026.10.26-noble`；沒有官方 GitHub Action；Mermaid 匯出是 `graph` 語法 |
| setup-tbls | v1.4.1 = `5e8e69748c0bb15fdb5e51a0ecdb84f1ecd0e3a1` |
| 本機工具 | 有 Docker；沒有 tbls、沒有 Graphviz |

還沒驗證、實作時第一個要確認的：

1. dependency-cruiser 的 Mermaid 輸出每次是否完全相同
2. Structurizr 的 Mermaid 匯出每次是否完全相同，以及 GitHub 能否正常顯示
3. tbls 能否正確讀 pgvector 的 `vector` 欄位
4. 本機資料庫的結構是否等於 CI 跑完 `alembic upgrade head` 的結構

任何一項不成立，停下來回報，不自己繞過去。

## 設計草圖

### 檔案配置

```
docs/architecture/
  README.md              入口頁（手寫）
  workspace.dsl          大地圖的來源（手寫，Structurizr DSL）
  c4.md                  ← 產生：大地圖兩張（系統情境、容器）
  openapi.json           ← 產生：API 端點
  db/README.md、db/*.md   ← 產生：ER 圖與每張資料表（tbls）
  frontend-deps.md       ← 產生：前端依賴圖（按資料夾合併）
scripts/
  gen-docs.sh            重新產生上面所有「產生」的檔案
backend/.importlinter    後端分層規則
backend/.tbls.yml        tbls 設定
frontend/.dependency-cruiser.cjs   前端依賴規則
```

### 一個腳本：`scripts/gen-docs.sh`

```bash
scripts/gen-docs.sh            # 全部重新產生
scripts/gen-docs.sh backend    # 只做 openapi.json 與 db/
scripts/gen-docs.sh frontend   # 只做 frontend-deps.md
scripts/gen-docs.sh c4         # 只做 c4.md（需要 Docker）
```

- 開頭 `set -euo pipefail`。
- 本機和 CI 跑同一個腳本。CI 跑完後檢查 `docs/architecture/` 有沒有變動；有變動代表提交的文件過期，CI 失敗。
- 產生的 Mermaid 會包進 Markdown 的 ` ```mermaid ` 區塊，因為 GitHub 只在 Markdown 裡顯示 Mermaid，不顯示單獨的 `.mmd` 檔。

### 六種視圖

| # | 視圖 | 來源 | 產生的檔案 | CI 檢查 |
| --- | --- | --- | --- | --- |
| 1 | 大地圖 | `workspace.dsl`（手寫） | `c4.md` | `validate` 通過；重新匯出後沒有變動 |
| 2 | API 端點 | FastAPI 程式碼 | `openapi.json`（排版成多行、鍵排序，diff 才看得懂） | 重新匯出後沒有變動 |
| 3 | ER 圖 | 跑完遷移的 Postgres | `db/` | 重新產生後沒有變動 |
| 4 | 前端依賴 | `frontend/src` | `frontend-deps.md` | 依賴規則通過；重新產生後沒有變動 |
| 5 | 後端分層 | `backend/app` 的 import | 無（規則本身就是文件） | `lint-imports` 通過 |
| 6 | 設計決策 | `docs/adr.md` | 無 | 無；入口頁只加連結 |

### 後端規則：`backend/.importlinter`

兩個合約：

1. **分層**：`app.features` → `app.core` → `app.shared`，下層不能 import 上層。今天就通過。
2. **feature 互相獨立**：12 個 feature 彼此不能 import。現有 53 條用 `ignore_imports` 逐條豁免，一條一行，格式 `app.features.costs.** -> app.features.discovery.**`。

效果：第 54 條依賴出現時 CI 失敗；將來重構拿掉某條依賴時，import-linter 會報「豁免沒對上」，提醒把那一行刪掉。

### 前端規則：`frontend/.dependency-cruiser.cjs`

用 `npx depcruise --init oneshot` 產生預設規則（禁止循環依賴、禁止孤兒檔案等）。先跑一次：

- 通過的規則：維持 error。
- 現況就違反的規則：降成 warn，違規列進完成報告，交給使用者決定。不修程式碼。

圖用 `--collapse` 按資料夾合併（`api`、`components`、`components/ui`、`lib`、`pages`），`minify: false` 顯示真實名稱。

### CI 的改動：`.github/workflows/ci.yml`

| 位置 | 新增步驟 |
| --- | --- |
| backend job | `uv run lint-imports` |
| backend job | 安裝 tbls：`k1LoW/setup-tbls@5e8e69748c0bb15fdb5e51a0ecdb84f1ecd0e3a1  # v1.4.1`，`version: v1.97.0` |
| backend job | `scripts/gen-docs.sh backend` 後檢查沒有變動（排在 `alembic upgrade head` 之後） |
| frontend job | `npx depcruise src`（規則檢查） |
| frontend job | `scripts/gen-docs.sh frontend` 後檢查沒有變動 |
| 新 job `architecture` | `docker run` Structurizr（用 digest `sha256:1081d615…` 固定）跑 `scripts/gen-docs.sh c4` 後檢查沒有變動 |

- 權限維持 `contents: read`。
- 新增的 action 只有 setup-tbls 一個，固定到 commit SHA 並加版本註解。
- 「沒有變動」的檢查同時看已追蹤的修改與新出現的檔案：`git status --porcelain -- docs/architecture` 輸出必須是空的。

### 邊界情況

| 情況 | 處理 |
| --- | --- |
| `alembic_version` 資料表 | tbls 用 `exclude` 排除 |
| 本機資料庫有真實資料 | tbls 只讀結構，不讀資料列；產生後檢查 `db/` 裡沒有任何資料內容再提交 |
| 本機沒開 Docker | `gen-docs.sh c4` 直接失敗並說明要先開 Docker |
| 產生的輸出不穩定（見「還沒驗證」1、2） | 停下來回報 |

### 不在範圍內

- 重構、修正任何架構違規（53 條依賴、13 對循環只列不修）
- graphify 相關檔案、`docs/adr.md`、`docs/rag-decisions.md`
- DeepWiki 之類的外部服務
- C4 第 3 層以下（由視圖 2–5 取代）
- 自動開 PR 更新文件

## Gate 2（紅綠）怎麼套用

這個任務沒有應用程式邏輯，「測試」就是每個可重跑的檢查指令。每一片先讓檢查因為**真的抓到問題**而失敗，提交紅；再讓它通過，提交綠。

| 片 | 紅（檢查失敗的原因） | 綠 |
| --- | --- | --- |
| 1 後端分層 | 加入兩個合約、不寫豁免 → `lint-imports` 列出 53 條違規 | 加入 53 行豁免 |
| 2 API | 提交一份少一個端點的 `openapi.json` 與腳本 → 重新匯出後有變動 | 提交正確的檔案 |
| 3 ER 圖 | 提交 `.tbls.yml` 與空的 `db/README.md` → 重新產生後有變動 | 提交產生的 `db/` |
| 4 前端 | 提交規則檔與空的 `frontend-deps.md` → 重新產生後有變動 | 提交產生的圖 |
| 5 大地圖 | 提交一份有箭頭指向未定義方塊的 `workspace.dsl` → `validate` 失敗 | 修正 DSL、提交 `c4.md` |
| 6 CI | 把上面的檢查接進 `ci.yml` | `gh run watch` 全綠 |

綠之後每一片再做一次「變異驗證」（不提交）：暫時改一處程式（例如加一個假的路由、加一條 feature 間的 import），確認檢查會變紅，然後還原。輸出貼在清單底下。

紅的提交訊息用 `test: <行為> (red)`，不壓縮、不改寫。

## Claude 自行決定

1. 計畫檔放 `docs/architecture-docs-plan.md`，照現有 `docs/*-plan.md` 的慣例。
2. tbls 本機安裝用 `brew install k1LoW/tap/tbls`（會在你的電腦裝一個程式；核准計畫即同意）。
3. 本機的資料庫連線由 `gen-docs.sh` 讀環境變數 `TBLS_DSN`，沒設時用 `docker-compose.yml` 已公開的本機開發帳密。CI 沿用 `ci.yml` 現有的 `scholar:scholar@localhost`。不讀 `backend/.env`。
4. 大地圖除了「能匯出」也檢查「重新匯出後沒有變動」，避免 `workspace.dsl` 改了但 `c4.md` 沒更新。
5. 根目錄 `README.md` 加一行連到入口頁。
6. 不跑 `graphify update .`（graphify 不在這次範圍）。

## 驗收清單

- [ ] 從 `main` 開分支，未提交的檔案沒被動到 -> verify: `git status --short`（`CLAUDE.md`、`docs/adr.md`、graphify 相關檔案與開始時相同）
- [ ] import-linter 寫進 lockfile -> verify: `cd backend && uv sync --frozen && uv run lint-imports --version`
- [ ] 後端分層規則：不豁免時列出 53 條（紅） -> verify: `cd backend && uv run lint-imports`
- [ ] 後端分層規則通過（綠） -> verify: `cd backend && uv run lint-imports`
- [ ] 新增一條 feature 間的 import 會被抓到（變異驗證） -> verify: `cd backend && uv run lint-imports`
- [ ] OpenAPI 檔過期時檢查失敗（紅） -> verify: `scripts/gen-docs.sh backend && git status --porcelain -- docs/architecture`
- [ ] OpenAPI 檔和程式一致（綠） -> verify: `scripts/gen-docs.sh backend && git status --porcelain -- docs/architecture/openapi.json`
- [ ] tbls 能讀 `vector` 欄位 -> verify: `grep -rn "vector" docs/architecture/db/`
- [ ] ER 圖過期時檢查失敗（紅） -> verify: `scripts/gen-docs.sh backend && git status --porcelain -- docs/architecture/db`
- [ ] ER 圖和資料庫一致（綠） -> verify: `scripts/gen-docs.sh backend && git status --porcelain -- docs/architecture/db`
- [ ] `db/` 裡沒有資料列內容、沒有 `alembic_version` -> verify: `ls docs/architecture/db && grep -rn "alembic_version" docs/architecture/db`
- [ ] dependency-cruiser 寫進 lockfile -> verify: `cd frontend && npm ci && npx depcruise --version`
- [ ] 前端依賴圖連跑兩次輸出相同 -> verify: `scripts/gen-docs.sh frontend && git status --porcelain -- docs/architecture/frontend-deps.md`（跑兩次）
- [ ] 前端依賴圖過期時檢查失敗（紅） -> verify: `scripts/gen-docs.sh frontend && git status --porcelain -- docs/architecture/frontend-deps.md`
- [ ] 前端依賴規則通過（綠） -> verify: `cd frontend && npx depcruise src`
- [ ] 前端依賴圖和程式一致（綠） -> verify: `scripts/gen-docs.sh frontend && git status --porcelain -- docs/architecture/frontend-deps.md`
- [ ] 大地圖 DSL 寫錯時檢查失敗（紅） -> verify: `scripts/gen-docs.sh c4`
- [ ] 大地圖 DSL 通過驗證並匯出（綠） -> verify: `scripts/gen-docs.sh c4 && git status --porcelain -- docs/architecture/c4.md`
- [ ] 大地圖連跑兩次輸出相同 -> verify: `scripts/gen-docs.sh c4 && git status --porcelain -- docs/architecture/c4.md`（跑兩次）
- [ ] 一個指令重新產生全部 -> verify: `scripts/gen-docs.sh && git status --porcelain -- docs/architecture`
- [ ] 入口頁說明六種視圖、重新產生的指令、CI 怎麼檢查，連結都有效 -> verify: `grep -o "](\([^)]*\))" docs/architecture/README.md` 逐一 `ls`
- [ ] 設定檔與腳本裡沒有金鑰 -> verify: `git diff main --stat` 加 `git diff main | grep -inE "api[_-]?key|token|secret"`
- [ ] 完整測試通過 -> verify: `cd backend && uv run pytest -q && uv run ruff check . && uv run mypy app && uv run lint-imports`
- [ ] 前端建置通過 -> verify: `cd frontend && npm run build && npx depcruise src`
- [ ] 只提交自己的檔案 -> verify: `git diff main --name-only`
- [ ] CI 全綠 -> verify: 推上分支後 `gh run watch`
- [ ] 每張圖在 GitHub 上能顯示（大地圖顯示不好就改成連結） -> verify: 在瀏覽器開 PR 分支的 `docs/architecture/` 各頁
- [ ] 學習卡與進度 -> verify: `ls docs/learning/ && git diff main -- docs/progress.md`

## 完成時回報

1. 入口頁路徑，以及每張圖在 GitHub 上怎麼看
2. feature 依賴表、import-linter 與 dependency-cruiser 找到的違規清單（只列不修）
3. 本機重新產生全部文件的指令
4. PR 連結與 CI 結果
5. 四個決定的 ADR 文字（待使用者加進 `docs/adr.md`）

## 附：12 個 feature 之間的實際 import（11-28）

| feature | import 了哪些其他 feature |
| --- | --- |
| costs | discovery, pipeline, profiles, settings, sources |
| discovery | costs, matching, notifications, pipeline, profiles, scholarships, sources |
| documents | costs |
| evaluation | costs, scholarships, sources |
| matching | costs, profiles, scholarships |
| notifications | matching, profiles, scholarships, settings |
| pipeline | costs, discovery, matching, notifications, profiles, scholarships, search, sources |
| profiles | pipeline, scholarships |
| scholarships | costs, documents, matching, notifications, pipeline, profiles, search, sources |
| search | costs, documents, pipeline, scholarships, sources |
| settings | pipeline, profiles, scholarships, sources |
| sources | costs, discovery, scholarships |

互相 import 的 13 對：costs⇄discovery、costs⇄pipeline、costs⇄sources、discovery⇄pipeline、discovery⇄sources、matching⇄scholarships、notifications⇄scholarships、pipeline⇄profiles、pipeline⇄scholarships、pipeline⇄search、profiles⇄scholarships、scholarships⇄search、scholarships⇄sources。
