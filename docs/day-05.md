# 第 5 天：RAG：段落向量、用一句話搜尋、路由問答附出處

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。依 ADR-039 的方式分階段做。

目標：把所有原文切段、建向量存進 PostgreSQL（pgvector）；每筆獎學金也有一個向量；兩個指令：`find`（用一句話找獎學金）和 `ask`（問問題，路由到適合的路線，答案附出處）。先用指令操作，網頁在第 9 天。

## 本計畫記錄的決定

- RAG 兩種：用一句話搜尋獎學金（每筆獎學金一個向量）、對原文提問附出處（每段一個向量）（ADR-032）
- 問答兩種模式：單一文件（整份交給 AI）、全部資料（先檢索再回答）（ADR-035）
- 表格四種處理：A 表格自成一段（第 3 天已做）、B 替每個表格寫一句說明並用說明建向量、命中時取回整格、C 每段標主題、D 精確數字存成欄位（類別表已做）（ADR-036）
- 切段依結構（ADR-038，第 3 天已做的 chunking）
- 向量存在 PostgreSQL，用 pgvector（ADR-050）
- 問答用路由：AI 先分類並抽參數，再走固定路線；不讓 AI 寫 SQL；查不到退回語意搜尋；答案附出處（ADR-051）
- 問答只透過模型插座呼叫，不綁定 Gemini（ADR-052）
- 第 5 天加上向量的相似度比對來找重複（ADR-048）

## Claude 自行決定（小問題，請事後檢查）

1. 嵌入模型 gemini-embedding-2、1,536 維（官方建議的大小之一，低於 pgvector 索引上限 2,000）；實測已正規化，用餘弦距離比對
2. 嵌入插座 `Embedder` 放在 core/llm（ADR-005）：`embed_documents(標題, 內容)`、`embed_query(問句)`；gemini-embedding-2 要求的前綴（`title: … | text: …`、`task: search result | query: …`）寫在 Gemini 轉接頭裡，功能程式不知道
3. 新功能資料夾 `features/search/`：段落表、建索引、找獎學金、問答
4. 段落向量的「標題」用章節路徑（例如「貳 > 四、獎助類別及名額」），讓向量知道這段在講什麼
5. 只重算有變的段落：段落內容雜湊和嵌入模型都一樣，就沿用舊的向量、說明和主題，不呼叫 AI
6. 表格說明（ADR-036 B）與主題標籤（ADR-036 C）都一次送多段給 AI（表格每次最多 10 個、主題每次最多 25 段），減少呼叫次數
7. 主題固定成一組代號：eligibility（資格）、nationality（國籍）、deadline（截止日）、documents（文件）、amount（金額）、quota（名額）、degree（學位）、application（申請方式）、programme（課程內容）、other；一段可以有多個主題
8. 每筆獎學金的向量用這些欄位組成：名稱、提供單位、國家、學位、領域、補助內容、金額、資格、語言要求；組成的文字有變才重算
9. `find` 只列出代表的那筆（排除 duplicate_of 有值的），列出前 10 筆，附最早還能申請的截止日
10. 路由的四條路線：lookup（問某一筆的名額、文件、截止日）、filter（依條件列出獎學金）、semantic（搜尋原文）、document（針對某一份文件整份讀）；分類和參數一次抽出
11. 名稱對應：問題裡的獎學金名稱，先用名稱正規化比對，再用獎學金向量找最像的 3 筆；最像的相似度低於門檻（0.75，實測後再調）就列出候選、不硬猜
12. filter 路線不呼叫第二次 AI：條件轉成 SQL，結果用固定格式列出（便宜、可預測）
13. 語意搜尋取最接近的 8 段；問題有指定獎學金就只在那筆的段落裡找；分類有給主題就先篩主題，篩完少於 3 段就不篩
14. 答案的出處用編號（例如 [C3]、[F2]），程式檢查編號都在這次給 AI 的資料裡，不在的刪掉並標記
15. 驗證沒通過的資料（申請期的驗證結果、類別的待確認）照樣給 AI，但標「待確認」，答案也要說待確認
16. 向量去重：獎學金向量餘弦相似度 ≥ 0.95 的配對列為「可能重複」，只列出、不自動標記（規則去重才自動標記）
17. 換 Docker 映像檔前，先用 pg_dump 備份資料庫到 `backend/data/backups/`（不進 git）

## 待使用者決策

（目前沒有）

## 設計草圖

### 資料表

chunks（新）：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | bigint identity，主鍵 | |
| source_id | bigint，外鍵，連動刪除 | 出自哪個來源 |
| snapshot_id | bigint，外鍵，連動刪除 | 出自哪一份快照 |
| position | integer | 在這份快照裡的順序 |
| heading_path | text[] | 章節路徑 |
| kind | varchar(8) | text／table |
| text | text | 段落原文（表格是整格） |
| content_hash | varchar(64) | 段落內容的雜湊 |
| summary | text | 表格的一句說明（ADR-036 B），文字段落是空白 |
| topics | text[] | 主題代號（ADR-036 C） |
| embedding | vector(1536) | 段落向量（表格用說明算） |
| embed_model | text | 嵌入模型名稱與維度，例如 gemini-embedding-2@1536 |

scholarships 新增：`embedding vector(1536)`、`embed_model`、`embed_hash`（組成向量的文字的雜湊）

### 介面

```python
# core/llm/base.py
class Embedder(Protocol):
    model_id: str                                            # 例如 gemini-embedding-2@1536
    def embed_documents(self, items: list[tuple[str, str]]) -> list[list[float]]: ...  # （標題, 內容）
    def embed_query(self, text: str) -> list[float]: ...

# features/search/（純函式）
def chunk_title(heading_path: list[str]) -> str
def scholarship_profile(row: dict) -> str                    # 組成獎學金向量的文字
def reuse_plan(old: dict[str, Reusable], hashes: list[str], model_id: str) -> tuple[dict[int, Reusable], list[int]]
def valid_citations(cited: list[str], allowed: set[str]) -> tuple[list[str], list[str]]
def similar_pairs(vectors: dict[int, list[float]], threshold: float) -> list[tuple[int, int, float]]
def build_filter_query(filters: Filters, now: datetime) -> Select                # 條件 → SQL（不讓 AI 寫 SQL）
```

### 指令

1. `uv run python -m app.features.search.index`：切段、表格說明、主題、段落向量、獎學金向量（只算有變的）
2. `uv run python -m app.features.search.find "一句話"`：找獎學金
3. `uv run python -m app.features.search.ask "問題"`：路由問答，答案附出處
4. `dedup` 指令加上向量相似度的「可能重複」清單

### 邊界情況

- PDF 快照用第 3 天的轉錄稿切段；沒有轉錄稿的跳過並印出
- 問題裡的獎學金對不到：列出最像的 3 筆，請使用者說清楚
- filter 路線篩不到：退回語意搜尋
- AI 回答引用了不存在的編號：刪掉並在輸出標記

### 不在第 5 天範圍

網頁介面（第 9 天）、評估資料集（#30，第 10–11 天；今天只用幾題固定問題實測）、給其他使用者用的模型選擇（ADR-052）、混合搜尋（關鍵字＋向量，之後需要再加）

## 測試哪些行為

| 檔案 | 行為 |
| --- | --- |
| test_search_text.py | 章節路徑變成標題、獎學金向量的文字包含各欄位且空的不寫 |
| test_search_plan.py | 內容雜湊與模型都一樣才沿用、模型不同要重算 |
| test_citations.py | 只留在資料裡的編號、不存在的另外列出 |
| test_similar.py | 相似度門檻以上的配對、每對只列一次 |
| test_filters.py | 篩選條件轉成的 SQL：國籍（all、listed、excluded）、學位、截止日範圍、只看還能申請的 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項先 commit 測試（red），再 commit 實作（green）。

### 1. 環境

- [ ] 備份資料庫 -> verify: `ls -la data/backups/`
- [ ] Docker 換成 pgvector 映像檔，資料還在 -> verify: `docker compose exec -T postgres psql -U scholar -c "select count(*) from scholarships"`（應為 181）
- [ ] 加入 pgvector 套件 -> verify: `uv pip show pgvector | head -2`

### 2. 純函式（紅綠循環）

- [ ] S1 章節路徑變成標題 -> verify: `uv run pytest tests/test_search_text.py -k title`
- [ ] S2 獎學金向量的文字 -> verify: `uv run pytest tests/test_search_text.py -k profile`
- [ ] S3 沿用舊向量的規則 -> verify: `uv run pytest tests/test_search_plan.py -k reuse`
- [ ] S4 出處編號檢查 -> verify: `uv run pytest tests/test_citations.py -k citations`
- [ ] S5 相似配對 -> verify: `uv run pytest tests/test_similar.py -k pairs`
- [ ] S6 篩選條件轉 SQL -> verify: `uv run pytest tests/test_filters.py -k filter`

### 3. 資料表與插座

- [ ] 遷移：vector 擴充功能、chunks、scholarships 的向量欄位 -> verify: `uv run alembic upgrade head` 與 `\d chunks`
- [ ] Embedder 插座與 Gemini 轉接頭（限速、前綴） -> verify: `uv run mypy app`，並在 index 的輸出看到向量數

### 4. 指令與實跑

- [ ] index：全部建索引 -> verify: 貼出段落數、表格數、主題分布、費用
- [ ] index 再跑一次全部沿用 -> verify: 貼出「沿用 N、重算 0」
- [ ] find：3 句實測 -> verify: 貼出結果
- [ ] ask：每條路線各 2 題實測 -> verify: 貼出路線、答案、出處
- [ ] dedup：向量可能重複清單 -> verify: 貼出配對

### 5. 收尾

- [ ] 完整檢查、更新 progress.md、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

## 執行時發現

（實作與實跑中遇到的事）
