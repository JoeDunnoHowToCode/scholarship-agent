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
17. （執行時）Chevening 這類不翻頁的網頁來源也請 AI 挑連結：Chevening 台灣頁只有 5,300 字的摘要，資格與時程在別頁；fetch 加 `--repick`，首頁沒變也能重挑
18. （執行時）內容雜湊相同的頁面只抽一份：mipdal.eu 的三個 `?open=` 分頁其實是同一頁
19. （執行時）文件清單同一類型、同一類別只留一筆，保留寫得最詳細的；other 要連要求文字都一樣才算重複（教育部簡章在正文、檢核表、報名流程重複列文件，原本 27 筆，改完 12 筆）
20. （執行時）表格引用核對：Gemini 把表格轉成連續的一句，pdfplumber 原文卻是左右兩欄交錯；允許引用切成幾截，每截至少 6 個字、依序出現、下一截在 300 字內。測試確認改過的日期不會通過
21. （執行時）第一輪大綱讀全文時，順便列出每個類別的名額、學位、國家；合併優先順序：明確點名的規則 > 大綱 > 「全部」的規則 > 整個獎學金的值
22. （執行時）提示詞加上：學位是拿獎學金去讀的學位、不是申請人的學歷；台灣籍的引用必須明確寫出台灣人能或不能申請，只出現「Taiwan」不算（extract-5、outline-3、section-4、verify-2）
23. （執行時）fetch 加 `--shard K/N`，依網站分成 N 份平行抓：一個程序平均 55 秒一個網站，218 個要 3 小時以上；同一個網站一定在同一份，限速規則不變
24. （執行時）Google 與 LangChain 的各種錯誤在轉接頭統一成 LLMError，功能程式只接這一種

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

- [x] 加入 pypdf -> verify: `uv pip show pypdf | head -2`

  ```text
  Name: pypdf
  Version: 6.20.0
  ```

### 2. 純函式（紅綠循環）

T1–T7 由 sub agent A、T8–T17 由 sub agent B 各自在獨立的 worktree 做紅綠循環，再搬到 main（commit 編號是 main 上的）。

- [x] T1 目錄卡片的標題連結 -> verify: `uv run pytest tests/test_catalogue.py -k title_link`

  ```text
  紅（6dedfa1）：AttributeError: module 'app.features.sources.catalogue' has no attribute 'parse_catalogue'
  綠（e276f07）：1 passed, 5 deselected
  ```

- [x] T2 沒有標題連結時用說明裡的連結 -> verify: `uv run pytest tests/test_catalogue.py -k description_link`

  ```text
  紅（4ed9221）：AssertionError: assert [] == [CatalogueEnt...africa.com/')]
  綠（00285f4）：1 passed, 5 deselected
  ```

- [x] T3 略過 erasmus-plus 專案頁連結 -> verify: `uv run pytest tests/test_catalogue.py -k project_page`

  ```text
  紅（e51c01d）：AssertionError: url='https://erasmus-plus.ec.europa.eu/projects/search/details/101000001' != url='https://example-master.eu/'
  綠（370ff42）：1 passed, 5 deselected
  ```

- [x] T4 讀出 Projects(N) -> verify: `uv run pytest tests/test_catalogue.py -k total`

  ```text
  紅（95933d0）：AttributeError: ... has no attribute 'catalogue_total'（3 個測試）
  綠（e0c6cb3）：3 passed, 3 deselected
  ```

- [x] T5 相對網址變絕對、只留同網站 -> verify: `uv run pytest tests/test_links.py -k same_site`

  ```text
  紅（f7ef985）：AttributeError: module 'app.features.sources.links' has no attribute 'candidate_links'
  綠（06f0cf5）：1 passed, 2 deselected
  ```

- [x] T6 去掉錨點與重複、排除自己 -> verify: `uv run pytest tests/test_links.py -k duplicates`

  ```text
  紅（dc13d84）：AssertionError: Link(url='.../programme/apply#deadlines', text='') != Link(url='.../programme/apply', text='Apply now')
  綠（0cf6bbc）：1 passed, 2 deselected
  ```

- [x] T7 排除檔案連結與 mailto -> verify: `uv run pytest tests/test_links.py -k files`

  ```text
  紅（8b5f9f7）：AssertionError: Link(url='.../programme/brochure.PDF', ...) != Link(url='.../admission.html', ...)
  綠（87c74c1）：1 passed, 2 deselected
  ```

- [x] T8 轉錄稿依編號切段 -> verify: `uv run pytest tests/test_chunking.py -k numbering`

  ```text
  紅（d95df2f）：AttributeError: module 'app.features.documents.chunking' has no attribute 'chunk_transcript'
  綠（7653df1）：1 passed, 7 deselected
  ```

- [x] T9 轉錄稿依 Markdown 標題切段 -> verify: `uv run pytest tests/test_chunking.py -k markdown_heading`

  ```text
  紅（0c9dab1）：AssertionError（第 0 段是沒有標題路徑的 '# Scholarship Guide…'）
  綠（c3a9a9b）：1 passed, 7 deselected
  ```

- [x] T10 表格自成一段 -> verify: `uv run pytest tests/test_chunking.py -k transcript_table`

  ```text
  紅（bab4619）：AssertionError（全部留在同一段文字，少了 2 段）
  綠（ce50bc4）：1 passed, 7 deselected
  ```

- [x] T11 太長的段細切 -> verify: `uv run pytest tests/test_chunking.py -k too_long`

  ```text
  紅（fe48a94）：AssertionError: assert 1 == 2
  綠（214ba34）：1 passed, 7 deselected
  ```

- [x] T12 太短的段併入前一段 -> verify: `uv run pytest tests/test_chunking.py -k too_short`

  ```text
  紅（fe21b5c）：AssertionError（第 1 段太短卻沒有併入）
  綠（38d0f3e）：1 passed, 7 deselected
  ```

- [x] T13 網頁依 h1–h4 切段 -> verify: `uv run pytest tests/test_chunking.py -k html_heading`

  ```text
  紅（8caf92e）：AttributeError: ... has no attribute 'chunk_html'
  綠（b04b82a）：1 passed, 7 deselected
  ```

- [x] T14 網頁表格轉成 Markdown 表格並自成一段 -> verify: `uv run pytest tests/test_chunking.py -k html_table`

  ```text
  紅（2169b05）：AssertionError（表格變成一般文字；少一段 kind='table'）
  綠（5d63d12）：1 passed, 7 deselected
  ```

- [x] T15 同一章合併成一節、超過上限分開 -> verify: `uv run pytest tests/test_chunking.py -k sections`

  ```text
  紅（2cd8e79）：AttributeError: ... has no attribute 'group_sections'
  綠（849cc39）：1 passed, 7 deselected
  ```

- [x] T16 引用忽略空白與全形半形 -> verify: `uv run pytest tests/test_checks.py -k quote`

  ```text
  紅（a814264）：AttributeError: module 'app.features.documents.checks' has no attribute 'quote_in_source'
  綠（41b5c97）：3 passed, 1 deselected（-k quote 也選到 T16b 的兩個測試）
  ```

- [x] T17 轉錄稿多出的數字被找出 -> verify: `uv run pytest tests/test_checks.py -k numbers`

  ```text
  紅（e7ec3f8）：AttributeError: ... has no attribute 'unverified_numbers'
  綠（54b0fb3）：1 passed, 3 deselected
  ```

- [x] T16b（執行時新增）表格引用：允許切成幾截、依序就近出現；改過的日期不通過 -> verify: `uv run pytest tests/test_checks.py -k table_text`

  ```text
  紅（4d0a91c）：AttributeError: module 'app.features.documents.checks' has no attribute 'quote_in_table_text'（2 failed）
  綠（9ca0ce8）：2 passed, 2 deselected
  ```

- [x] T18 單一欄位取第一個，不同值記衝突 -> verify: `uv run pytest tests/test_merge.py -k conflict`

  ```text
  紅（2b89d70）：AttributeError: module 'app.features.scholarships.merge' has no attribute 'merge_sections'
  綠（556a1de）：1 passed
  ```

- [x] T19 清單欄位聯集、文字欄位串接 -> verify: `uv run pytest tests/test_merge.py -k union`

  ```text
  紅（dda6594）：AssertionError: assert [] == ['Denmark', '...en', 'Norway']
  綠（0b13fe8）：2 passed（-k union 也選到 T23）
  ```

- [x] T20 台灣籍優先順序（國籍描述同理） -> verify: `uv run pytest tests/test_merge.py -k taiwan`

  ```text
  紅（4a081f3）：AssertionError: assert 'unclear' == 'no'
  綠（748ce15）：1 passed
  ```

- [x] T20b 學位的引用取第一個有學位的那一節 -> verify: `uv run pytest tests/test_merge.py -k degrees_evidence`

  ```text
  紅（162cd46）：AssertionError: assert None == '一律以攻讀博士學位為限'
  綠（a1e26b0）：1 passed
  ```

- [x] T21 類別先用明確規則，沒有才用「全部」 -> verify: `uv run pytest tests/test_merge.py -k category_rules`

  ```text
  紅（329c228）：ValueError: not enough values to unpack (expected 3, got 0)（類別是空的）
  綠（86f3d01）：1 passed
  ```

- [x] T21b 大綱沒有類別時，用獎學金名稱建一個類別 -> verify: `uv run pytest tests/test_merge.py -k without_category`

  ```text
  紅（25b9f16）：ValueError: not enough values to unpack (expected 1, got 0)
  綠（3cc840a）：1 passed
  ```

- [x] T21c（執行時新增）第一輪讀全文的類別資料排在明確規則之後、「全部」之前 -> verify: `uv run pytest tests/test_merge.py -k outline_details`

  ```text
  紅（98d6183）：AssertionError: assert (None, ['master', 'phd'], []) == (10, ['phd'], ['Sweden'])
  綠（1f2ed4e）：1 passed
  ```

- [x] T22 未知類別名稱被丟掉並記警告 -> verify: `uv run pytest tests/test_merge.py -k unknown_category`

  ```text
  紅（ec71e83）：AssertionError: assert [] == ['未知類別：北歐']
  綠（9d45954）：1 passed
  ```

- [x] T23 文件要求聯集並去重 -> verify: `uv run pytest tests/test_merge.py -k requirements`

  ```text
  紅（b2c1774）：AssertionError: assert [] == [('cv', None)...cript', None)]
  綠（e06ccd8）：1 passed
  ```

- [x] T23b（執行時新增）同一類型、同一類別只留一筆，保留最詳細的要求 -> verify: `uv run pytest tests/test_merge.py -k longest_details`

  ```text
  紅（7df8f26）：AssertionError: assert [('cv', '履歷表'..., None, None)] == [('cv', '包括自我..., None, None)]
  綠（8229a2f）：1 passed
  ```

### 3. 資料表

- [x] 產生遷移並讀過 -> verify: `uv run alembic revision --autogenerate -m "add categories requirements parent and source ids"`，貼出遷移內容

  ```text
  837b61df1d63：create_table scholarship_categories（scholarship_id 外鍵 ON DELETE CASCADE）、
  create_table requirements（scholarship_id、category_id 外鍵 ON DELETE CASCADE）、
  scholarships 加 source_id（唯一＋外鍵）、sources 加 parent_id（外鍵）。
  讀過後修改：自動產生的限制名稱是 None，downgrade 會失敗，所以 upgrade 給明確名稱，
  downgrade 改成直接刪欄位（PostgreSQL 會一起刪掉欄位上的限制）
  ```

- [x] 套用遷移 -> verify: `uv run alembic upgrade head && docker compose exec -T postgres psql -U scholar -c '\d scholarship_categories' -c '\d requirements'`

  ```text
  Running upgrade ced471d15d28 -> 837b61df1d63（另外試過 downgrade -1 再 upgrade，兩個方向都成功）
  scholarship_categories：id, scholarship_id, name, quota, degrees text[], countries text[], amount, eligibility
  requirements：id, scholarship_id, category_id, doc_type varchar(32), details, required, count, evidence
  ```

### 4. AI 呼叫（實際執行驗證）

- [x] GeminiLLM 重試、讀 PDF、累計 tokens -> verify: `uv run mypy app`，並在第 5 步的實跑輸出看到 tokens 總量

  ```text
  Success: no issues found in 35 source files
  tokens：輸入 39,595、輸出 7,012，約 US$0.029（NT$0.9）  ← extract --limit 7 的結尾
  ```

- [x] 教育部 PDF 轉錄與數字核對 -> verify: `uv run python -m app.features.documents.transcribe data/snapshots/3/20261010T084757Z_093808c1e5b1.pdf`（計畫原本寫來源 id，改成快照檔路徑，documents 才不必 import sources 的內部）

  ```text
  批次：6，轉錄稿 35,865 字元，存在 data/snapshots/3/20261010T084757Z_093808c1e5b1.pdf.transcribe-1.json
  原文裡找不到的數字：['1151001234', '88.88', '80', '18']
  tokens：輸入 30,434、輸出 27,653，約 US$0.078（NT$2.5）
  ```

- [x] AI 挑連結 -> verify: 第 5 步的 fetch 輸出列出挑中的網址

  ```text
  == 14 EUropean master on COntrol of Renewable Energy systems
  new        9f64a38cb10a    https://master-eu-core.ec-nantes.fr
  picked     AI 挑連結          https://master-eu-core.ec-nantes.fr/admission/students/deadlines
  picked     AI 挑連結          https://master-eu-core.ec-nantes.fr/admission/students/fees-scholarships
  picked     AI 挑連結          https://master-eu-core.ec-nantes.fr/admission/students/who-can-apply
  ```

### 5. 指令與實跑

- [x] 目錄 → 子來源 -> verify: `uv run python -m app.features.sources.catalogue`，貼出解析數與 Projects(N)

  ```text
  解析出 218 個學程（11 頁）；頁面寫的總數：218
  ```

- [x] 抽 Chevening -> verify: `uv run python -m app.features.scholarships.extract --source 2`，貼出結果與驗證狀態

  ```text
  2 Chevening Taiwan｜類別 1、文件 3、截止 None、台灣 unclear｜deadline=empty taiwan_eligibility=not_supported degrees=supported
  ```

- [x] 抽教育部 PDF -> verify: `uv run python -m app.features.scholarships.extract --source 3`，貼出 8 個類別的名額與學位

  ```text
  3 教育部 115 年留學獎學金簡章｜類別 8、文件 12、截止 2026-02-13、台灣 yes｜deadline=supported taiwan_eligibility=supported degrees=not_supported
  一般學群 155 {phd}｜北歐國家 10｜新南向國家甲 15｜新南向國家乙 10｜勵學優秀生、原住民生、身心障礙生 各 10 {master,phd}｜特殊教育生 5 {master,phd}
  名額全對；北歐與新南向的學位被模型多加了 bachelor（見執行時發現）
  ```

- [x] 先抓 5 個學程試跑 -> verify: `fetch --unchecked --limit 3` 與 `extract --limit 7`（含 2 個種子）

  ```text
  12 MASTER IN INTELLECTUAL PROPERTY AND DATA LAW｜類別 1、文件 7、截止 2027-01-15、台灣 unclear｜deadline=supported …
  完成 6、沒變 1、失敗 0；tokens：輸入 39,595、輸出 7,012，約 NT$0.9
  ```

- [x] 218 個學程全部抓取 -> verify: fetch 輸出的統計（新增、被擋、錯誤）

  ```text
  218 個都檢查過；178 個有快照；27 個被擋（403×15、429×3、captcha×2、robots.txt 禁止×3、robots.txt 讀不到×4）；13 個連不上
  有快照的學程裡，13 個只有首頁（AI 沒挑到或挑到的頁面抓不到）
  ```

- [x] 218 個學程全部抽取 -> verify: extract 輸出的統計（成功、失敗、驗證狀態、tokens 與費用）

  ```text
  scholarships 共 180 筆（178 個學程＋Chevening＋教育部），失敗 0
  截止日：有依據 116、沒寫 57、待確認 7；學位有依據 161；台灣 yes 5、no 0、unclear 175
  國籍描述 worldwide 153；截止日在今天之後 66
  各次執行印出的 AI 費用加總約 NT$35（實際以帳單為準）
  ```

- [x] 抽查 10 筆和原網頁比對 -> verify: 貼出比對表

  | 來源 | 抽出的截止日 | 原網頁 | 結果 |
  | --- | --- | --- | --- |
  | 129 EPOG-JM | 2027-01-27 | January 27, 2027 (13:00, Paris time) | 對 |
  | 70 SuCat | 2026-02-19 | open … to February 19th, 2026 | 對（網站還沒更新到下一屆） |
  | 20 MemBioMed | 2027-02-28 | February 28th, 2027 Application deadline | 對 |
  | 21 E pico | 2027-01-31 | … scholarships: 31 January 2027 | 對 |
  | 19 MARIHE | 2026-09-21 | Deadline: September 21, 2026 | 對 |
  | 177 SARENA | 空白 | 抓到的頁面沒有日期 | 對 |
  | 159 Impact Entrepreneurship | 空白 | 只寫 application deadline，沒有日期 | 對 |
  | 209 Transnational German Studies | 空白 | 抓到的頁面沒有日期 | 對 |
  | 35 Lascala | 空白 | Mid-February（沒有年份與日） | 對：沒有硬換成日期，引用有存 |
  | 82 Sustainable Food Systems | 2025-03-01 | 1st of March（沒寫年份） | **錯**：年份是模型自己補的，驗證者也放行 |

  10 筆的學位都是 master、有依據，和原網頁一致

### 6. 收尾

- [x] 完整檢查 -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`（輸出見最後的推送紀錄）
- [x] 更新 progress.md、推上 main -> verify: `git log origin/main --oneline -1`

## 執行時發現

- 教育部 PDF 轉錄：6 批、35,865 字元、NT$2.5。原文核對找到 4 個對不上的數字，其中 2 個來自附錄的範例成績單（可能是圖片，pdfplumber 取不到字）
- Gemini 轉錄真的寫錯字：轉錄稿把「優秀青年」寫成「優秀青青年」，學位的引用因此在 pdfplumber 原文裡找不到，被標成待確認（ADR-037 的核對有作用）。第一次單獨試轉兩頁時沒有這個錯，同一份 PDF 兩次轉錄結果不同
- 抽取結果每次跑不一樣：同一份教育部轉錄稿，類別名稱有時是「新南向國家甲」，有時是整串國名；北歐與新南向的學位被加上原文沒有的 bachelor（直接看第一輪的輸出也一樣，是模型讀錯，不是合併規則的問題）。Chevening 有一次把沒有日期的句子當成截止日的依據，驗證者擋下來了
- 驗證者擋下的例子：Chevening 用「Taiwan」一個字當台灣籍的依據（改提示詞後判為不支持）；學程網站寫「open to students from all over the world」，模型填 yes，驗證者判為不支持而改成 unclear（見待決策第 1 題）
- 學程網站抓取：一個程序平均 55 秒一個網站（有些網站很慢或逾時 30 秒），改成 4 個程序平行抓
- 兩個抓取程序整晚卡住：卡在挑連結的 Gemini 呼叫，轉接頭沒有逾時；加上 120 秒逾時
- 撞到免費方案的每分鐘 15 次上限（同時 5 個程序），並發現專案用的是免費方案，和 ADR-012 衝突；使用者選擇付費＋限速器（ADR-042）
- 預付餘額是 0 時回 402：官方文件寫預付制要先有預付餘額，GCP 抵免額才會被使用、而且先扣抵免額；使用者購買 NT$150 後恢復
- 挑連結失敗時首頁快照照存，之後就不會重挑：改成整個來源退回（bug 修正）；已經受影響的 4 個來源用 `--repick` 補挑
- 有一個學程網頁不是 UTF-8，抽取時當機：快照改用頁面自己的編碼解碼（decode_snapshot，紅綠循環）
- 意外的好發現：Flood Risk Management 學程（來源 103）寫著教育部有給台灣學生的國家獎學金
- 抽查時發現截止日年份被模型自己補上（來源 82），驗證者沒擋住
- 驗證者的判斷不一致：同樣只寫「open to all nationalities」，2 筆被判為台灣 yes（122、193），另外 150 筆是 unclear

## 第 3 天補強（ADR-043、044、045）

使用者 2026-10-12 決定：國籍資格依國籍判斷、180 筆全部重抽；學程 PDF 照 ADR-037、缺資料才讀；五條程式檢查與兩種格式限制全做。改完只重抽一次。

### 設計草圖

國籍資格（ADR-043）：

- schema：`taiwan_eligibility`、`taiwan_evidence`、`nationality_scope`（舊四種）、`taiwan_conditions` 改成 `nationality_scope`（all／listed／excluded／unclear）、`nationalities`（英文國名清單）、`nationality_evidence`、`nationality_conditions`
- 資料表 scholarships：刪 `taiwan_eligibility`、`taiwan_conditions`，加 `nationality_scope`、`nationalities text[]`、`nationality_conditions`（舊資料會整批重抽，所以直接刪欄，不搬資料）
- 合併：範圍取 listed > excluded > all > unclear；國家清單取做出決定那一類的聯集
- 驗證者：第三個核對欄位從台灣籍改成國籍範圍；沒通過就改成 unclear

格式限制（ADR-045）：

- 截止日改成 `deadline_year`、`deadline_month`、`deadline_day` 三個整數欄位，年份可空；程式組成 `deadline`（三個都有才組）
- 第二輪抽取的 schema 依第一輪的類別名稱動態產生：`applies_to` 與文件的 `category` 只能選這些名稱（或 all）
- 第一輪的類別資料加 `evidence`；大綱與整份抽取加 `total_quota`（原文寫的總名額）

程式檢查（ADR-045，`features/scholarships/rules.py`，純函式）：

1. 截止日年份要在引用裡（民國年也算，例如 2026 對應「115 年」）；不符合就不組 `deadline`，狀態 year_not_in_quote
2. 學位要在原文寫到：bachelor／master／phd 各有關鍵字，要出現在該類別的引用或學位引用裡
3. 類別名稱要在原文裡，而且不超過 20 個字
4. 名額數字要在原文找得到；國籍清單的國名要在原文找得到
5. 原文寫了總名額，而且每個類別都有名額時，加總要相等

檢查結果存在 `extracted.verification`：`deadline`、`degrees`、`nationality` 三欄的狀態，加上 `categories`（類別名稱 → 問題清單）與 `issues`（其他問題）。

學程 PDF（ADR-044）：

- 新指令 `uv run python -m app.features.scholarships.pdfs`：找截止日或文件清單有缺的學程，從它的快照頁面列出 PDF 連結，請 AI 挑一份最可能是申請說明的，抓下來存成同一個來源的快照
- fetch 依 Content-Type 判斷 PDF（不再只看來源的抓取方式），已存的 PDF 快照之後照常重新檢查
- extract 遇到 PDF 快照就轉錄（ADR-037），轉錄稿當成一頁加進原文；核對基準加上 pdfplumber 原文

### Claude 自行決定（補強）

25. 每個學程最多讀 1 份 PDF，超過 30 頁就跳過不讀（26 個學程最壞約 NT$35，一般約 NT$10）
26. PDF 連結的候選：頁面上所有 .pdf 連結（不限同一個網站，大學常把說明放在主網域），由 AI 挑一份；沒有和申請相關的就不挑
27. 費用保護：extract 與 pdfs 加 `--max-cost`（新台幣），這次執行的估計費用超過就停下；本月已用約 NT$40（各次執行印出的估計），重抽＋PDF 預計再用 NT$30–55，會接近每月 NT$100 的上限
28. 改動既有的合併測試（台灣籍改成國籍、截止日拆成年月日）：使用者已同意設計變更（ADR-043、045），測試單獨一個 commit

29. （執行時）類別名稱檢查只在有 2 個以上類別時做：只有一個類別時名稱照規定用獎學金名稱，名稱本來就長（55 個誤報降到 6 個）；已存的 180 筆用一次性腳本重算純程式的檢查，沒有呼叫 AI
30. （執行時）英文類別名稱改用字數（最多 8 個字）判斷太長，中文仍是 20 個字
31. （執行時）驗證者提示詞加上民國年換算（verify-4）：教育部的截止日引用是「115 年」，原本被判為不支持

### 檢查清單（補強）

- [x] T24 截止年份在引用裡（含民國年） -> verify: `uv run pytest tests/test_rules.py -k deadline_year`（紅：AttributeError … 'deadline_year_in_quote'；綠：1 passed）
- [x] T25 學位要有關鍵字 -> verify: `uv run pytest tests/test_rules.py -k degree_keywords`（紅：AttributeError … 'degree_supported'；綠：1 passed）
- [x] T26 類別名稱在原文且不太長 -> verify: `uv run pytest tests/test_rules.py -k category_name`（紅：AttributeError … 'category_name_issue'；綠：1 passed）
- [x] T26b（執行時新增）英文類別名稱用字數 -> verify: `uv run pytest tests/test_rules.py -k english_category`（紅：AssertionError: assert 'name_too_long' is None；綠：1 passed）
- [x] T27 名額與國名在原文 -> verify: `uv run pytest tests/test_rules.py -k in_source`（紅：AttributeError … 'number_in_source'；綠：1 passed）
- [x] T28 名額加總等於總額 -> verify: `uv run pytest tests/test_rules.py -k quota_sum`（紅：AttributeError … 'quota_sum_mismatch'；綠：1 passed）
- [x] T29 合併：國籍範圍的優先順序與國家清單 -> verify: `uv run pytest tests/test_merge.py -k nationality`（紅：修改後的測試在舊 schema 下 10 failed；綠：10 passed）
- [x] T30 合併：截止日年月日當成一個事實 -> verify: `uv run pytest tests/test_merge.py -k conflict`（同上一個紅綠循環）
- [x] T31 動態 schema 只接受第一輪的類別名稱 -> verify: `uv run pytest tests/test_schemas.py -k section_schema`（紅：AttributeError … 'section_schema'；綠：1 passed）
- [x] 遷移：國籍欄位 -> verify: `uv run alembic upgrade head` 與 `\d scholarships`

  ```text
  Running upgrade 837b61df1d63 -> 38d397472d61, nationality eligibility replaces taiwan columns
  nationality_scope varchar(16) not null default 'unclear'｜nationalities text[] not null default '{}'｜nationality_conditions text
  ```

- [x] 缺資料的學程讀 PDF -> verify: `uv run python -m app.features.scholarships.pdfs --max-cost 3`

  ```text
  缺資料的學程 69 個，嘗試抓 PDF 19 份（存下 13 份；超過 30 頁跳過 3 份、被擋或錯誤 3 份）
  tokens：輸入 10,182、輸出 1,508，約 NT$0.2
  ```

- [x] 180 筆重抽 -> verify: 4 個 `extract --shard K/4 --max-cost 12` 的輸出統計

  ```text
  完成 33＋52＋48＋47＝180、失敗 0；約 NT$5.7＋11.0＋10.0＋9.9＝NT$36.6
  有完整截止日 115（都有依據）；年份不在引用裡 7；學位有依據 158
  國籍：all 93、listed 5、excluded 2、unclear 80（其中 38 筆模型說 all 但沒附引用，16 筆引用不支持）
  文件清單空白 29；截止日在今天之後 62
  程式檢查標出的問題：國名不在原文 23、學位關鍵字不在引用 16、名稱不在原文 13、名稱太長 6、名額加總不符 6、名額不在原文 3
  ```

- [x] T32（執行時新增）多類別規則的名額不複製到每一類 -> verify: `uv run pytest tests/test_merge.py -k group_quota`（紅：assert [35, 35, 35] == [10, 15, 10]；綠：68 passed）
- [x] 抽查與完整檢查、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

  抽查同樣 10 筆：截止日 82 不再自己補年份（改成空白）；20 有兩個截止日（夥伴國 2/28、歐盟國 3/31），模型取了歐盟國的；國籍 159 錯（引用寫的是「各種學術背景」不是國籍，驗證者放行）。教育部名額加總 250≠225（新南向兩類都填了 25），程式檢查有標出來

### 執行時發現（補強）

- 溫度實驗：gemini-3.5-flash-lite 使用固定的取樣設定，LangChain 會忽略 temperature；9 次結果顯示錯誤大多固定（教育部新南向每次都寫成國名清單）
- 國籍改由驗證者核對後，unclear 從原本未核對的狀態變成 80 筆；之前的 153 筆 worldwide 從來沒有被驗證過
- 同一個學程對不同申請人有不同截止日（夥伴國、歐盟國），現在只能存一個；第 4 天做申請期（cycles）時要處理
- 教育部名額錯誤的根本原因（使用者要求追查）：轉錄稿正確（甲 15、乙 10，全文沒有 25）；第一輪大綱也正確；錯在第二輪把「選送赴特定國家名額計 35 名」寫成一條同時套用北歐、新南向甲、乙的規則，名額填總數 35，而合併規則把它複製給每一類。這是 schema 與合併規則的設計漏洞，不是模型讀錯。修法：名額只取只點名一個類別的規則（T32，紅綠循環）；quota 欄位說明改成「套用多個類別時留空」（section-6）。重抽後 8 類名額全對，加總 225

## 第 3 天補強之二（ADR-046，2026-10-18）

使用者要求先追查根本原因，三個錯誤的結果：

- 北歐被加上碩士：類別的名額和學位共用一格引用，模型只引用名額那句，學位沒有依據；學位檢查又接受整份簡章的學位引用，所以放行；模型可能把「選送赴特定國家『新南向國家』」理解成包括北歐（推測）；學位清單表達不了「碩士限藝術、建築學群」。bachelor 在要求附引用（outline-4）之後 4 次都沒有再出現（outline-3 是 9 次都有）
- 學程 159 的國籍：不是錯誤。完整引用是「open to individuals of all academic backgrounds and of all nationalities」，抽查時把引用截到 70 字，誤判成錯誤；之後抽查看完整引用
- 學程 20 的截止日：同一頁有夥伴國 2/28、歐盟國 3/31 兩個截止日，資料格式只有一格截止日，模型每次挑的不一樣；178 個學程中 69 個在 deadline 附近提到申請人分組或輪次（關鍵字粗估）。屬於第 4 天申請期（cycles）的設計

### 設計

- CategoryDraft：`evidence` 拆成 `quota_evidence`、`degrees_evidence`，加 `degree_conditions`
- OutlineCategory：同上；CategoryFact 加 `degree_conditions`（`evidence` 仍是這條規則的原文）
- 合併：名額引用跟著名額來源（只點名一類的規則，或第一輪）；學位引用與學位條件跟著學位來源（明確規則 > 第一輪 > 全部 > 整個獎學金）
- 學位檢查：有多個類別時只看該類別自己的學位引用；只有一個類別時才可以用整個獎學金的學位引用
- 資料表 scholarship_categories 加 `degree_conditions`
- 提示詞：extract-7、outline-5、section-7；這次只重抽教育部（約 NT$1）

### Claude 自行決定（補強之二）

32. 改既有測試：category_rules 的斷言從 `evidence` 改成 `degrees_evidence`（欄位拆開，使用者已同意方向，單獨一個 commit）
33. 新欄位在 CategoryFact、OutlineCategory 給預設值空白（模型可以不填）；CategoryDraft 的新欄位必填但可空，讓整份抽取時模型一定會考慮

### 檢查清單（補強之二）

- [ ] T33 合併：名額引用、學位引用、學位條件跟著各自的來源 -> verify: `uv run pytest tests/test_merge.py -k evidence_follows`
- [ ] T34 學位檢查：多個類別時只看自己的學位引用 -> verify: `uv run pytest tests/test_verify.py -k own_degree_quote`
- [ ] 遷移：degree_conditions -> verify: `uv run alembic upgrade head` 與 `\d scholarship_categories`
- [ ] 重抽教育部 -> verify: `uv run python -m app.features.scholarships.extract --source 3`，貼出 8 類的學位與條件
- [ ] 完整檢查、推上 main -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`
