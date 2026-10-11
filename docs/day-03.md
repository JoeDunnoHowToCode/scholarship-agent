# 第 3 天：抽取與驗證者、文件清單、學程網站第 2、3 層

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。依 ADR-039 分階段做，需要使用者決策的功能先暫緩，其他繼續；問題統整在最後的報告。

目標：一個指令把 EACEA 目錄變成 218 個學程來源，抓下每個學程首頁和 AI 挑的申請頁；另一個指令把每個來源的快照抽成獎學金、類別、文件清單，關鍵欄位經驗證者核對原文。教育部 PDF 走「Gemini 轉錄 → 依結構切段 → 一段一段抽 → 程式合併」。

## 本計畫記錄的決定

- 抽取後加驗證者，核對截止日、台灣籍、學位的原文依據；找不到就標「待確認」（ADR-008）
- 原生 schema 結構化輸出，驗證失敗把錯誤回饋給模型重試，最多 2 次（ADR-011）
- EACEA 目錄用專屬解析器；內容頁交給 AI；學程網站第 3 層由 AI 從首頁連結挑（ADR-031）
- 長文件切段、一段一段抽、程式合併（ADR-034）；切段依結構，表格自成一段（ADR-036 A、ADR-038）
- PDF 交給 Gemini 轉錄，pdfplumber 原文當核對基準（ADR-037）
- 名額存成類別表欄位（ADR-036 D、ADR-040）
- 218 個學程全部跑（ADR-041）
- 今天新增 scholarship_categories、requirements 兩張表，scholarships 加 source_id，sources 加 parent_id（ADR-024）

## Claude 自行決定（和架構無關的小問題，請事後檢查）

1. 學程網站存成 sources 的子來源：`parent_id` 指向 EACEA 目錄，`discovery` 新增 `catalogue`，`kind` 填 `university`。理由：抓取、快照、限速、被擋處理都能直接重用第 2 天的流程；AI 挑到的申請頁存成同一個來源的快照，下次抓取會自動重新檢查（和翻頁頁面一樣）
2. 暫時一個來源對應一筆獎學金：scholarships 加 `source_id` 當重跑時的更新鍵（冪等）。跨來源合併是第 4 天的去重
3. 解析器自我檢查：EACEA 頁面寫著「Projects(218)」，解析出的學程數和這個數字不同就印警示（ADR-031 要求「能發現解析器壞掉」）
4. 目錄卡片的網址：標題有連結就用標題連結；沒有（實測 7 張）就用說明裡第一個不是 erasmus-plus.ec.europa.eu 專案頁的連結
5. 挑連結只看同一個網站的連結（忽略開頭的 www.），最多挑 3 頁；排除 PDF、Word、圖片等檔案連結（原因見「待使用者決策」第 2 題）
6. 「長文件」的定義：PDF 一律走切段流程；網頁合併後超過 100,000 字元也走切段流程，其他網頁整份讀（ADR-034 說一般網頁整頁讀）
7. 切段長度：每段最多 3,000 字元，超過就在段落邊界細切；少於 200 字元併到前一段（同一章內）。抽取時把同一章（第一層標題）的段落合併成一節，每節最多 12,000 字元
8. 長文件合併的做法：分兩輪。第一輪把整份轉錄稿交給 AI，只列出名稱與類別清單（輸出短）；第二輪一節一節抽，AI 必須用第一輪的類別名稱標出每條規則適用哪些類別（或「全部」）；程式再依名稱合併。這樣教育部第 3 章的學位規則能正確套回第 4 章的各類別
9. 合併規則：單一欄位取第一個有值的，後面出現不同的值就記成「衝突」並標待確認；清單欄位取聯集；台灣籍取「不行 > 可以 > 不確定」；類別欄位先用明確套用到該類別的規則，沒有才用「全部」的規則；文件要求取聯集並去重
10. 驗證者：先由程式確認引用逐字存在於原文（忽略空白與全形半形差異），再用一次 AI 呼叫判斷引用是否支持該值。任一關沒過就標待確認；台灣籍沒過就改成 unclear。結果存在 extracted 的 verification
11. PDF 轉錄：用 pypdf 把 PDF 每 10 頁切成一批送 Gemini（避免輸出太長被截斷），轉錄稿存在快照旁邊（`<快照檔名>.transcribe-1.md`），只有改版才重轉。每一批的數字都要在同一批頁面的 pdfplumber 原文裡找得到，找不到的列在 extracted 的 unverified_numbers
12. 冪等：extracted 記錄快照雜湊、提示詞版本、模型；三者都沒變就跳過，不花 AI 費用
13. 文件類型固定成一組代號（cv、motivation_letter、recommendation_letter、transcript、degree_certificate、language_test、passport、research_proposal、portfolio、admission_letter、financial_proof、application_form、other）
14. 使用量：GeminiLLM 累計每次呼叫的輸入與輸出 tokens，指令結束時印出總量與估計費用（完整成本表是第 10 天）
15. 「documents」新功能資料夾放切段、原文核對、PDF 轉錄：抽取（第 3 天）和 RAG（第 5 天）都會用，放在一個功能裡，兩邊都只用它公開的函式
16. 第 1 天測試用的那筆獎學金（id=1，範例文字抽出來的）保留不刪，它沒有 source_id；要刪再告訴我

## 待使用者決策（不擋今天的其他工作，先用保守做法）

1. 「開放所有國籍」算不算「台灣可以申請」？Erasmus Mundus 學程多半寫「open to students of any nationality」，沒寫到台灣。spec 規則是「沒提到台灣一律待確認」，所以今天先照規則填 unclear，同時另存 nationality_scope（worldwide／listed_countries／taiwan_specific／unclear）和引用，之後改規則不必重抽
2. 學程網站上的 PDF 要不要讀？ADR-037 規定 PDF 交給 Gemini 轉錄（每份約 NT$3）。218 個學程如果各挑到一份 PDF，費用約 NT$650，超過每月上限。今天先排除 PDF 連結，跑完統計有多少學程的申請資訊只在 PDF 裡

（執行中發現的新題目，追加在下面「執行時發現」）

## 使用者要做的事

不需要先做任何事。Docker 要開著（已在執行），`backend/.env` 已有 Gemini 金鑰。

## 設計草圖

### 資料夾（第 3 天新增或修改的部分）

```text
backend/app/
  core/llm/
    base.py            # 插座：StructuredLLM 加 read_pdf
    gemini.py          # 重試（ADR-011）、讀 PDF、累計 tokens
  features/sources/
    models.py          # Source 加 parent_id；Discovery 加 catalogue
    catalogue.py       # parse_catalogue、catalogue_total（純函式）＋ catalogue 指令
    links.py           # candidate_links（純函式）
    pick.py            # AI 挑連結（提示詞 links-1）
    fetch.py           # 子來源的首頁變了就請 AI 挑連結
  features/documents/
    chunking.py        # chunk_transcript、chunk_html、group_sections（純函式）
    checks.py          # quote_in_source、unverified_numbers（純函式）
    transcribe.py      # PDF → Gemini 轉錄稿（提示詞 transcribe-1）
  features/scholarships/
    models.py          # Scholarship 加 source_id；新增 ScholarshipCategory、Requirement
    schemas.py         # ScholarshipDraft、CategoryDraft、RequirementDraft、Outline、SectionFacts
    merge.py           # merge_sections（純函式）
    verify.py          # 驗證者（程式核對＋提示詞 verify-1）
    extract.py         # extract 指令（提示詞 extract-2、outline-1、section-1）
tests/
  test_catalogue.py  test_links.py  test_chunking.py  test_checks.py  test_merge.py
```

### 資料模型

sources 新增：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| parent_id | bigint，外鍵 sources.id，可空 | 學程來源指向 EACEA 目錄 |

discovery 選項加 `catalogue`（從目錄解析出來的）。

scholarships 新增：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| source_id | bigint，外鍵 sources.id，可空，唯一 | 抽自哪個來源；重跑時用它找到同一筆更新 |

scholarship_categories（ADR-040）：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | bigint identity，主鍵 | |
| scholarship_id | bigint，外鍵，必填 | 刪掉獎學金時一起刪 |
| name | text，必填 | 類別名稱，例如「北歐國家」；只有一個類別時用獎學金名稱 |
| quota | integer | 名額（ADR-036 D）；原文沒寫就留空 |
| degrees | text[] | bachelor／master／phd |
| countries | text[] | 英文國名 |
| amount | text | 這個類別的補助金額原文 |
| eligibility | text | 這個類別的資格條件 |

requirements（文件清單）：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | bigint identity，主鍵 | |
| scholarship_id | bigint，外鍵，必填 | |
| category_id | bigint，外鍵，可空 | 空白代表所有類別都要 |
| doc_type | varchar(32)，必填 | 上面第 13 點的代號 |
| details | text | 具體要求，例如「最多 1,000 字、PDF」 |
| required | boolean | 必要或選填；不知道就留空 |
| count | integer | 份數，例如推薦信 2 封 |
| evidence | text | 原文出處（逐字引用） |

### 抽取 schema（schemas.py）

ScholarshipDraft（一般網頁整份抽，或長文件合併後的結果）：
name、name_zh、provider、countries、degrees、degrees_evidence、fields、coverage、amount、taiwan_eligibility、taiwan_evidence、nationality_scope、nationality_evidence、taiwan_conditions、language_requirements、other_eligibility、requires_admission、intake（例如 2027/28）、deadline（YYYY-MM-DD）、deadline_timezone、deadline_evidence、categories（至少一個 CategoryDraft）、requirements（RequirementDraft 清單，category 欄位填類別名稱或空白）

長文件另外兩個：Outline（name、name_zh、provider、category_names）與 SectionFacts（ScholarshipDraft 的欄位全部可空，加上 category_facts：每條有 applies_to＝類別名稱清單或 ["all"]）

### 介面

```python
# features/sources/catalogue.py
@dataclass(frozen=True)
class CatalogueEntry:
    name: str
    url: str
def parse_catalogue(html: str) -> list[CatalogueEntry]: ...
def catalogue_total(html: str) -> int | None: ...   # 「Projects(218)」→ 218

# features/sources/links.py
@dataclass(frozen=True)
class Link:
    url: str
    text: str
def candidate_links(html: str, page_url: str) -> list[Link]: ...

# features/documents/chunking.py
@dataclass(frozen=True)
class Chunk:
    heading_path: tuple[str, ...]   # 例如 ("貳、…簡章", "三、留學國別、領域及學位別")
    text: str
    kind: Literal["text", "table"]
def chunk_transcript(markdown: str) -> list[Chunk]: ...   # PDF 轉錄稿
def chunk_html(html: str) -> list[Chunk]: ...             # 網頁
def group_sections(chunks: list[Chunk], max_chars: int = 12_000) -> list[str]: ...

# features/documents/checks.py
def quote_in_source(quote: str, source: str) -> bool: ...
def unverified_numbers(transcript: str, raw: str) -> list[str]: ...

# features/scholarships/merge.py
def merge_sections(outline: Outline, sections: list[SectionFacts]) -> MergeResult: ...  # draft＋conflicts

# core/llm/base.py
class StructuredLLM(Protocol):
    def extract[M: BaseModel](self, prompt: str, schema: type[M]) -> M: ...
    def read_pdf(self, prompt: str, pdf: bytes) -> str: ...
```

### 指令的流程

1. `uv run python -m app.features.sources.catalogue`：讀 EACEA 每一頁最新的快照 → 解析 → 和「Projects(N)」比對 → 以網址 upsert 子來源
2. `uv run python -m app.features.sources.fetch`：照第 2 天的流程抓所有來源；子來源的首頁是新的或變了，就取出候選連結、請 AI 挑最多 3 頁，加進這次的抓取佇列
3. `uv run python -m app.features.scholarships.extract [--source ID] [--limit N]`：每個有快照、不是目錄的來源：
   - 網頁：合併每頁的可見文字（每頁前面標網址）→ 整份抽 → 驗證者 → 存檔
   - PDF：轉錄（有快取就用快取）→ 核對數字 → 切段、分節 → 第一輪大綱 → 第二輪逐節抽 → 合併 → 驗證者（引用核對 pdfplumber 原文）→ 存檔
   - 存檔：獎學金、類別、文件清單在同一個交易裡整批重寫

### 邊界情況

- 目錄卡片沒有標題連結：用說明裡的連結；兩個都沒有就跳過並印出
- 學程首頁被擋或連不上：照第 2 天的規則（需人工或下次再試），沒有快照就不抽
- AI 挑的網址不在候選清單裡：丟掉（防止模型編造網址）
- 抽取重試 2 次仍失敗：印出錯誤，跳過這個來源，繼續下一個
- 轉錄稿沒有編號或標題：整份退回依長度切
- 第二輪的 applies_to 出現大綱沒有的類別名稱：丟掉並記成警告

### 不在第 3 天範圍

申請期與截止日存成 cycles（第 4 天）；跨來源去重與變更紀錄（第 4 天）；表格說明 B、主題標籤 C、向量（第 5 天）；從目錄消失的學程要停用（第 4 天封存）；需要 JavaScript 的網站

## 測試哪些行為

只測純函式（ADR-022）；AI 呼叫與指令用實際執行驗證。

| 檔案 | 目標 | 行為 |
| --- | --- | --- |
| test_catalogue.py | sources/catalogue.py | 標題連結、沒有標題連結時用說明連結、略過 erasmus-plus 專案頁、讀出 Projects(N) |
| test_links.py | sources/links.py | 相對網址變絕對、只留同網站（忽略 www.）、去掉錨點與重複、排除檔案連結與 mailto |
| test_chunking.py | documents/chunking.py | 依「壹、」「一、」「(一)」編號切、依 Markdown 標題切、表格自成一段、太長細切、太短併入、網頁依 h1–h4 切、網頁表格轉成 Markdown 表格、分節上限 |
| test_checks.py | documents/checks.py | 引用忽略空白與全形半形、引用不存在、轉錄稿多出的數字被找出 |
| test_merge.py | scholarships/merge.py | 單一欄位取第一個、不同值記衝突、清單聯集、台灣籍優先順序、類別規則與「全部」規則、未知類別名稱被丟掉、文件去重 |

## 檢查清單

在 `backend/` 執行。紅綠循環的每一項：先 commit 測試（red），再 commit 實作（green）。

### 1. 套件

- [ ] 加入 pypdf -> verify: `uv pip show pypdf | head -2`

### 2. 純函式（紅綠循環）

- [ ] T1 目錄卡片的標題連結 -> verify: `uv run pytest tests/test_catalogue.py -k title_link`
- [ ] T2 沒有標題連結時用說明裡的連結 -> verify: `uv run pytest tests/test_catalogue.py -k description_link`
- [ ] T3 略過 erasmus-plus 專案頁連結 -> verify: `uv run pytest tests/test_catalogue.py -k project_page`
- [ ] T4 讀出 Projects(N) -> verify: `uv run pytest tests/test_catalogue.py -k total`
- [ ] T5 相對網址變絕對、只留同網站 -> verify: `uv run pytest tests/test_links.py -k same_site`
- [ ] T6 去掉錨點與重複、排除自己 -> verify: `uv run pytest tests/test_links.py -k duplicates`
- [ ] T7 排除檔案連結與 mailto -> verify: `uv run pytest tests/test_links.py -k files`
- [ ] T8 轉錄稿依編號切段 -> verify: `uv run pytest tests/test_chunking.py -k numbering`
- [ ] T9 轉錄稿依 Markdown 標題切段 -> verify: `uv run pytest tests/test_chunking.py -k markdown_heading`
- [ ] T10 表格自成一段 -> verify: `uv run pytest tests/test_chunking.py -k transcript_table`
- [ ] T11 太長的段細切 -> verify: `uv run pytest tests/test_chunking.py -k too_long`
- [ ] T12 太短的段併入前一段 -> verify: `uv run pytest tests/test_chunking.py -k too_short`
- [ ] T13 網頁依 h1–h4 切段 -> verify: `uv run pytest tests/test_chunking.py -k html_heading`
- [ ] T14 網頁表格轉成 Markdown 表格並自成一段 -> verify: `uv run pytest tests/test_chunking.py -k html_table`
- [ ] T15 同一章合併成一節、超過上限分開 -> verify: `uv run pytest tests/test_chunking.py -k sections`
- [ ] T16 引用忽略空白與全形半形 -> verify: `uv run pytest tests/test_checks.py -k quote`
- [ ] T17 轉錄稿多出的數字被找出 -> verify: `uv run pytest tests/test_checks.py -k numbers`
- [ ] T18 單一欄位取第一個，不同值記衝突 -> verify: `uv run pytest tests/test_merge.py -k conflict`
- [ ] T19 清單欄位聯集 -> verify: `uv run pytest tests/test_merge.py -k union`
- [ ] T20 台灣籍優先順序 -> verify: `uv run pytest tests/test_merge.py -k taiwan`
- [ ] T21 類別先用明確規則，沒有才用「全部」 -> verify: `uv run pytest tests/test_merge.py -k category_rules`
- [ ] T22 未知類別名稱被丟掉並記警告 -> verify: `uv run pytest tests/test_merge.py -k unknown_category`
- [ ] T23 文件要求聯集並去重 -> verify: `uv run pytest tests/test_merge.py -k requirements`

### 3. 資料表

- [ ] 產生遷移並讀過 -> verify: `uv run alembic revision --autogenerate -m "add categories requirements parent and source ids"`，貼出遷移內容
- [ ] 套用遷移 -> verify: `uv run alembic upgrade head && docker compose exec -T postgres psql -U scholar -c '\d scholarship_categories' -c '\d requirements'`

### 4. AI 呼叫（實際執行驗證）

- [ ] GeminiLLM 重試、讀 PDF、累計 tokens -> verify: `uv run mypy app`，並在第 5 步的實跑輸出看到 tokens 總量
- [ ] 教育部 PDF 轉錄與數字核對 -> verify: `uv run python -m app.features.documents.transcribe 3`，貼出批次數、字數、未核對數字
- [ ] AI 挑連結 -> verify: 第 5 步的 fetch 輸出列出挑中的網址

### 5. 指令與實跑

- [ ] 目錄 → 子來源 -> verify: `uv run python -m app.features.sources.catalogue`，貼出解析數與 Projects(N)
- [ ] 抽 Chevening -> verify: `uv run python -m app.features.scholarships.extract --source 2`，貼出結果與驗證狀態
- [ ] 抽教育部 PDF -> verify: `uv run python -m app.features.scholarships.extract --source 3`，貼出 8 個類別的名額與學位
- [ ] 先抓 5 個學程試跑 -> verify: `uv run python -m app.features.sources.fetch --limit 5` 與 `extract --limit 5`
- [ ] 218 個學程全部抓取 -> verify: fetch 輸出的統計（新增、被擋、錯誤）
- [ ] 218 個學程全部抽取 -> verify: extract 輸出的統計（成功、失敗、驗證狀態、tokens 與費用）
- [ ] 抽查 10 筆和原網頁比對 -> verify: 貼出比對表

### 6. 收尾

- [ ] 完整檢查 -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] 更新 progress.md、推上 main -> verify: `git log origin/main --oneline -1`

## 執行時發現

（實作與實跑中遇到的事，Claude 自行處理的和要使用者決策的分開寫）
