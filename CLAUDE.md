# 留學獎學金 Agent

自動收集歐洲留學獎學金，依使用者條件評分並說明理由，用 Telegram 通知，在網頁列出獎學金與所需文件。目前是第一版：只有使用者本人，跑在本機。

## 合作方式（最重要）

- 使用者決定架構，Claude 負責實作。使用者的目標是學會 AI 工程師需要的知識。
- 每完成一個步驟，用繁體中文說明：做了什麼、為什麼這樣做、背後的 AI 或軟體工程概念。程式碼附上初學者看得懂的註解。
- 一個階段一個階段做完，不要遇到問題就整個停下來：
  - 產品設計或軟體架構的選擇由使用者決定：包含 `docs/adr.md` 裡「待決定」的題目，以及任何新出現、會影響結構或難回頭的選擇。那個功能先不做完，繼續做不受影響的部分，問題統整到最後的報告，依 `docs/decision-format.md` 的格式說明；使用者選擇後，把決定追加成新的 ADR
  - 和架構無關的小問題（實作細節、命名、門檻數字等），Claude 直接決定，記在當天計畫的「Claude 自行決定」段落，讓使用者事後檢查
  - 可以替每個功能派 sub agent，由 Claude 當中樞分派工作、回答小問題
  - 使用者的選擇若和品質屬性或先前的 ADR 衝突，要明確指出後果（架構審查）
- 依「最後負責時刻」（ADR-014）：開始某一天的工作前，先處理 `docs/adr.md` 中排在那一天之前的待決定題目。
- 實作前先讀 `docs/adr.md` 的「已決定」，技術組合以那裡為準。
- 每完成一天，更新 `docs/progress.md`。
- 單人開發：直接在 main 上 commit 並推到 origin/main，不開分支、不開 PR（取代全域 Gate 3 的分支與 PR 規定）。推之前先在 `backend/` 跑完整檢查：`uv run pytest && uv run ruff check . && uv run mypy app`。
- 不寫目前無法測試的程式。例如沒有 OpenAI 金鑰，就先不寫 OpenAI 轉接頭。
- 不要要求使用者把 API 金鑰貼進對話；請使用者自己寫進 `backend/.env`。

## 目標與限制

| 主題 | 決定 | ADR |
| --- | --- | --- |
| 品質屬性 | 盡快做出能用的版本、學習價值與作品集、結果準確可信 | 001 |
| 限制 | 每月 AI 費用上限 NT$7,000；不送可識別個人的資料到雲端 | 001、012、013、049 |

## 程式規範

- 資料夾：`backend/app/features/<功能>/` 放路由、邏輯與資料表類別；`backend/app/core/{llm,notify,fetch}/` 放插座與轉接頭；`backend/app/shared/` 放 db 與 settings
- 每個資料表類別另有給 API 用的 Pydantic 模型；API 不直接回傳資料表物件
- 存取個人資料的函式一律把 `user_id` 當必要參數
- 覆寫獎學金資料與寫入變更紀錄要在同一個交易內
- JSONB 欄位要整個重新指定，不要原地修改字典（否則 SQLAlchemy 偵測不到變更）
- 列表查詢關聯資料時用 `selectinload`，避免 N+1 查詢
- 抽取用的 Pydantic schema：可能缺的欄位允許 null 或 unclear；關鍵欄位附逐字引用的 evidence，並用程式確認引用真的存在於原文
- 提示詞有版本號；改提示詞必須改版本號（它是快取鍵的一部分）
- 截止時間以 UTC 存，同時保留原始時區
- RQ 的工作必須冪等：重複執行結果相同，寫入前先用網址與內容雜湊檢查
- Alembic 自動產生的遷移腳本要先讀過再套用（欄位改名會被誤判成刪除再新增）
- 秘密放在 `backend/.env`，不進 git；`backend/data/snapshots/` 也不進 git

## 常用指令

```bash
docker compose up -d                            # 在 repo 根目錄啟動 Redis 與 PostgreSQL
cd backend
uv run uvicorn app.main:app --reload            # 啟動 API
uv run rq worker                                # 啟動背景 worker
uv run alembic revision --autogenerate -m "說明"  # 產生遷移，讀過再套用
uv run alembic upgrade head                     # 套用遷移
uv run pytest && uv run ruff check . && uv run mypy app
```

## 文件

- `docs/spec.md`：規格摘要（範圍、資料模型、評分、通知與維護規則、開發排程、成本粗估）
- `docs/adr.md`：架構決策紀錄與待決定清單
- `docs/decision-format.md`：向使用者說明架構選項的格式
- `docs/day-NN.md`：每一天的步驟與完成標準
- `docs/progress.md`：目前做到哪一天
- 完整的學習筆記與圖解在使用者的 claude.ai 文件「留學獎學金 Agent 規格書 v1」
