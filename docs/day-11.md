# 第 11 天：持續整合、模型評估、README

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 直接推 main）。段 2 第 1 步是重構（只走 Gate 1、3，前後各貼一次完整測試結果）。

目標：做完之後，

- 每次推上 GitHub，GitHub Actions 自動跑完整檢查（後端測試、ruff、mypy、前端建置），repo 上看得到結果
- 用同一批來源，比較 Gemini 3.5 與 3.1 Flash-Lite 的抽取品質、穩定度與成本，你抽查兩個模型不一致的地方，最後決定要不要換模型
- repo 有 README：這個專案做什麼、架構、怎麼跑、評估結果，以及示範影片的腳本

## 本計畫依據的決定

- 評估：替代指標＋抽查不一致，結果不寫回資料庫，原始結果不進公開 repo（ADR-098）
- 持續整合：GitHub Actions，PostgreSQL（pgvector）與 Redis 當服務、跑遷移與種子（ADR-099）
- 第一版模型 Gemini 3.5 Flash-Lite，要用評估和 3.1 Flash-Lite 比較（ADR-015）
- 提示詞一版一檔，評估時兩個模型用同一版（ADR-088）
- 費用都經過 `costs.gemini()` 記錄並受每月上限約束（ADR-089）
- 不送可識別個人的資料到雲端；截圖不含評分理由與個人資料（ADR-001、記憶裡的規則）

## 分四段做

| 段 | 內容 | 做完就有 | 估計 |
| --- | --- | --- | --- |
| 1 持續整合 | `.github/workflows/ci.yml`，在空的資料庫上跑遷移、種子與全部檢查 | 每次推送自動檢查 | 約半天 |
| 2 評估程式 | 抽取拆出「只算、不寫資料庫」的函式（重構）；評估指令；指標計算；不一致清單 | 可以重複跑的模型評估 | 約半天 |
| 3 跑評估與抽查 | 兩個模型各抽兩次；產生報告與不一致清單；你抽查約 10 筆；決定要不要換模型 | 評估報告與決定 | 約 1 小時程式＋你約 1 小時 |
| 4 README 與示範影片腳本 | README（用途、架構圖、功能、怎麼跑、評估結果、成本、CI 徽章）；示範影片的分鏡腳本 | 作品集可以給人看 | 約半天 |

每段做完：跑完整檢查、推 main、寫學習卡（`docs/learning/day-11.md`）。

## 設計草圖

### 段 1 持續整合

- 觸發：推送到 main、開 PR
- 兩個工作：
  - 後端：Ubuntu，服務 `pgvector/pgvector:pg17-trixie`（和本機同一個映像）、`redis:7`；安裝 uv 和 Python 3.13，`uv sync --frozen`；`alembic upgrade head`；`python -m app.features.sources.seed`；`pytest`、`ruff check .`、`mypy app`
  - 前端：Node 22，`npm ci`、`npm run build`（`schema.d.ts` 已經在 git 裡，不需要啟動後端產生）
- 環境變數只放測試用的連線網址；沒有任何金鑰（測試本來就不呼叫真的 AI、Tavily、Telegram）
- 用到的 GitHub Actions 固定到特定版本的 commit（供應鏈安全，和 `npm ci` 版本寫死同一個道理）

### 段 2 評估程式

- 重構：把 `extract_source` 裡「抽取＋核對、組出結果」的部分，拆成不寫資料庫的 `build_extraction(session, llm, source)`；`extract_source` 改成呼叫它再存檔。行為不變，完整測試前後各跑一次
- `costs.gemini()` 加上可選的 `model` 參數，評估時指定模型；費用照常記錄，功能名稱就是提示詞名稱
- 評估指令 `uv run python -m app.features.evaluation.run --models gemini-3.5-flash-lite gemini-3.1-flash-lite --rounds 2 --max-cost 80`
  - 固定的評估樣本：所有非 Erasmus 來源，加上用固定亂數種子挑的 40 個 Erasmus 學程，約 60 個；清單存檔，下次跑同一批
  - 用已存的快照，不重新抓網頁；結果存成 JSON 在 `backend/data/eval/<日期>/`（`.gitignore` 已排除 `backend/data/` 的快照，這個資料夾也加進去）
- 指標（純函式，有單元測試）：
  - 各欄位有根據率：國籍、學位、截止日、金額
  - 截止日不完整率
  - 平均規則問題數
  - 穩定度：同一模型兩次，截止日、國籍、學位、金額一樣的比例
  - 兩模型一致率
  - 每個來源的平均費用、平均秒數、失敗次數
- 報告：`docs/eval/2026-11-xx.md` 只放數字（進 git）
- 不一致清單：`backend/data/eval/<日期>/disagreements.md`（不進 git），列出兩模型答案不同的欄位，最多 10 筆：來源網址、欄位、兩邊的值與引用、空白的「誰對」讓你填
- 統計抽查：`uv run python -m app.features.evaluation.run --tally <日期>` 讀你填的結果，補進報告

### 邊界情況

- 某個來源抽取失敗：記成失敗、繼續下一個，算進失敗率
- 費用：每次評估指令都有 `--max-cost`，也受每月上限約束（ADR-049）
- 長簡章（教育部 PDF）走分段抽取，一樣比較
- 兩模型都沒抽到的欄位：不算進一致率，另外列出

### 不做（這次範圍外）

- 人工標註完整的正確答案（ADR-098 選了替代指標）
- 評估 agent 的發掘品質、問答品質（之後再說）
- 雲端部署（#44，公開版前）
- 自動剪輯示範影片：我寫腳本，影片由你錄

## 步驟

### 段 1 持續整合
1. 寫 `.github/workflows/ci.yml`
2. 本機用空的資料庫模擬一次：新的資料庫名稱 → 遷移 → 種子 → 完整測試，先在本機找出依賴既有資料的測試
3. 推上去，看 GitHub Actions 的結果；沒過就修到過
4. 記下第一次跑的時間

### 段 2 評估程式
1. 重構前完整測試，貼結果
2. pin 測試：同一份假的 AI 回覆，`build_extraction` 和原本的 `extract_source` 組出的結果一樣
3. 拆出 `build_extraction`，重構後完整測試，貼結果
4. `costs.gemini(model=...)`
5. 指標的紅綠燈：有根據率、不完整率、穩定度、一致率
6. 評估指令：樣本、跑模型、存 JSON、報告、不一致清單、統計抽查

### 段 3 跑評估與抽查
1. 先用 3 個來源試跑，確認流程和費用
2. 跑完整評估（兩個模型各兩次），貼出報告
3. 你抽查不一致清單（約 10 筆），填「誰對」
4. 統計抽查，報告補完
5. 列出選項給你決定：維持 3.5 或換 3.1（會改 ADR-015）

### 段 4 README 與示範影片腳本
1. README：
   - 一段話說明用途
   - 架構圖（Mermaid）
   - 主要功能
   - 重要的設計決定（連到 ADR）
   - 怎麼在本機跑
   - 評估結果
   - 每月成本
   - CI 徽章
2. 截圖：只用不含個人資料的頁面（詳細頁的公開資訊、紀錄頁、設定頁），不截評分理由與個人資料
3. 示範影片腳本 `docs/demo-script.md`：3 分鐘的分鏡（畫面、旁白、要點開哪裡）

## 測試與檔案

| 行為 | 測試檔 | 對象 |
| --- | --- | --- |
| 拆出的抽取函式和原本組出的結果一樣 | `tests/test_extract_build.py` | `features/scholarships/extract.py` |
| 指標計算 | `tests/test_eval_metrics.py` | `features/evaluation/metrics.py` |
| 樣本挑選固定、不一致清單 | `tests/test_eval_run.py` | `features/evaluation/run.py` |
| CI | GitHub Actions 的執行結果 | `.github/workflows/ci.yml` |

## 完成標準

### 段 1
- [ ] 空的資料庫跑遷移與種子後，完整測試全過 -> verify: `docker compose exec postgres createdb -U scholar scholar_ci && cd backend && export DATABASE_URL=postgresql+psycopg://scholar:scholar@localhost:5432/scholar_ci && uv run alembic upgrade head && uv run python -m app.features.sources.seed && uv run pytest -q`
- [ ] GitHub Actions 後端與前端兩個工作都過 -> verify: `gh run list --workflow ci.yml --limit 1`

### 段 2
- [ ] 重構前完整測試全過 -> verify: `cd backend && uv run pytest -q`
- [ ] `build_extraction` 和原本組出的結果一樣 -> verify: `cd backend && uv run pytest tests/test_extract_build.py -q`
- [ ] 重構後完整檢查全過 -> verify: `cd backend && uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] 指標計算正確（有根據率、不完整率、穩定度、一致率） -> verify: `cd backend && uv run pytest tests/test_eval_metrics.py -q`
- [ ] 樣本固定、不一致清單最多 10 筆 -> verify: `cd backend && uv run pytest tests/test_eval_run.py -q`

### 段 3
- [ ] 試跑 3 個來源 -> verify: `cd backend && uv run python -m app.features.evaluation.run --limit 3 --rounds 1 --max-cost 5`
- [ ] 完整評估的報告 -> verify: `cat docs/eval/2026-11-xx.md`
- [ ] 抽查統計補進報告 -> verify: `cd backend && uv run python -m app.features.evaluation.run --tally <日期>`

### 段 4
- [ ] README 的指令照著做真的跑得起來 -> verify: 照 README 的步驟在空的資料庫上跑一次
- [ ] 截圖不含評分理由與個人資料 -> verify: 逐張檢查
- [ ] 示範影片腳本 -> verify: `cat docs/demo-script.md`

### 全部
- [ ] 完整檢查全過 -> verify: `cd backend && uv run pytest && uv run ruff check . && uv run mypy app`，`cd frontend && npm run build`
- [ ] 學習卡寫完 -> verify: `ls docs/learning/day-11.md`
- [ ] `docs/progress.md` 更新 -> verify: `grep -n "第 11 天" docs/progress.md`

## Claude 自行決定（小問題，請事後檢查）

1. 評估樣本約 60 個：所有非 Erasmus 的來源（教育部、Chevening、agent 加的大學頁），加上固定亂數種子挑的 40 個 Erasmus 學程；兩個模型各抽兩次，約 240 次抽取，粗估 NT$40–50（3.1 比較便宜）
2. 評估的原始結果和不一致清單存在 `backend/data/eval/`，不進 git（含各網站的原文引用，repo 是公開的）；報告只放數字
3. 3.1 Flash-Lite 的模型名稱實作時用 Gemini API 的模型清單確認
4. 不一致清單只挑「國籍、學位、截止日、金額」四個欄位的不一致，最多 10 筆，每個來源最多 1 筆，讓抽查涵蓋不同來源
5. CI 用的 GitHub Actions 固定到 commit；Python 版本和本機一樣是 3.13
6. 示範影片只寫腳本，影片由你錄；我可以幫你準備好畫面和要點開的頁面
