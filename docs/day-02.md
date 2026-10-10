# 第 2 天：來源清單與抓取、快照與雜湊

軌道：一般功能（Gate 1–3；Gate 3 依 CLAUDE.md 改成直接推 main）。這份是 Gate 1 計畫，使用者核准後才動程式。

目標：用一個指令抓下 3 個種子來源，原始檔存成快照，文字正規化後算雜湊；內容沒變就不重新下載、不重存；全程遵守 ADR-028 的三條界線。

## 本計畫記錄的決定

- 只做第 1 層：Chevening 台灣頁、教育部 115 年簡章 PDF、EACEA 目錄（含翻頁）（ADR-029）
- 來源存在資料庫，種子寫在 seed 指令（ADR-026）
- httpx 抓取，BeautifulSoup 取出全部可見文字，PDF 用 pdfplumber；無頭瀏覽器之後再加（ADR-027）
- httpx 預設 User-Agent；Protego 遵守 robots.txt；限速；條件式請求；被擋就標記「需人工」（ADR-028）
- 今天新增 sources、snapshots 兩張表（ADR-024）

## 需要你確認的設計選擇（spec 沒寫，或和 spec 不同）

1. sources 表不放 spec 的「上次內容雜湊」：EACEA 一個來源有 11 頁，雜湊要記在每個網址上，所以改記在 snapshots（每個網址最新的那一筆）
2. 只有內容變了才新增快照（存原始檔＋新增一列）；沒變只更新來源的「上次檢查時間」，避免每天多出一堆一樣的檔案
3. 種子用 seed 指令（重跑也不會重複，以網址判斷），不寫進遷移：遷移只管資料表結構，種子清單之後比較好改
4. 限速：同一個網站兩次請求至少間隔 5 秒；robots.txt 寫的 Crawl-delay 更長就照它。EACEA 11 頁約 1 分鐘，每天跑一次可以接受。秒數放在設定裡，可以改
5. 「需人工」用一個「需人工原因」欄位：空白代表自動抓取；有內容（例如「403」「robots.txt 禁止」）代表之後跳過，等你處理
6. 翻頁：sources 加一個「跟隨翻頁」欄位；只跟同一路徑的 `?page=數字` 連結，最多 50 頁，避免無限翻下去
7. 網路錯誤和 5xx：這次跳過、下次再試，不標記需人工（重試策略是 #25，第 6–7 天決定）
8. 種子分類：EACEA 歸為「政府」（歐盟執行機構的官方目錄），Chevening 歸為「政府」（英國政府的獎學金），教育部歸為「政府」
9. 已知限制：教育部 PDF 的網址每年都會換，監看它只能發現這份 PDF 被修改，發現不了明年的新簡章；要偵測新年度，得改監看公告頁，第 4 天做申請期時處理

## 執行時發現、由使用者決定

- 憑證：教育部的根憑證缺少一個格式欄位，Python 3.13 的嚴格檢查會拒絕連線；改成關掉嚴格檢查、基本驗證照做（ADR-030）
- 翻頁連結帶 `#main-content` 錨點，同一頁被抓兩次：屬於 bug，已修（pagination_urls 去掉錨點，T12b）
- `?page=0` 和目錄首頁是同一頁：方式 1，來源加「第 0 頁就是首頁」設定，只有 EACEA 打開（T13）；方式 3，加「漏抓警示」
- 漏抓警示：上次抓到多頁、這次只剩 1 頁以下才警示（門檻 C）；上次頁數記在 sources 新欄位 last_page_count（存放 A）。只算翻頁來源；中途出錯的那次不比較、不更新；警示先印在 fetch 輸出，第 7 天再接 Telegram。翻頁壞掉後一直是 1 頁時只警示一次（甲）：警示後照常把上次頁數更新成這次的頁數

## 使用者要做的事

不需要先做任何事。Docker 要開著（已在執行）。

## 設計草圖

### 資料夾（第 2 天新增的部分）

```text
backend/
  app/
    core/fetch/
      base.py          # 插座：Fetcher、FetchResult、BlockedError（之後的瀏覽器轉接頭也實作它）
      http.py          # 轉接頭：HttpFetcher（httpx、robots、限速、條件式請求、被擋偵測）
      etiquette.py     # robots_allows、detect_block（純函式，ADR-028）
      text.py          # html_to_text、pdf_to_text、content_hash（純函式）
    features/sources/
      models.py        # Source、Snapshot 資料表類別
      pagination.py    # pagination_urls（純函式）
      seed.py          # seed 指令
      fetch.py         # fetch 指令：抓所有該抓的來源、存快照
  data/snapshots/      # 原始檔（已在 .gitignore）
  tests/
    test_text.py
    test_etiquette.py
    test_pagination.py
```

### 資料模型：sources（ADR-024、025、026）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | bigint identity，主鍵 | ADR-025 |
| name | text，必填 | 名稱 |
| url | text，必填，唯一 | 網址；唯一限制擋掉重複（ADR-026） |
| kind | varchar，必填 | government／institution／university／aggregator（政府、機構、大學、彙整網站） |
| country | text | 提供單位的國家或地區，用英文名稱（和 scholarships.countries 一致） |
| fetch_method | varchar，必填，預設 html | html／pdf；之後加 browser（ADR-027） |
| follow_pagination | boolean，必填，預設 false | 是否跟隨翻頁 |
| page_zero_is_first | boolean，必填，預設 false | 第 0 頁就是首頁：打開時 `?page=0` 換成首頁網址（只有 EACEA 打開） |
| last_page_count | integer | 上次完整抓取時成功檢查到的頁數；只記翻頁來源，漏抓警示用 |
| check_interval_hours | integer，必填，預設 24 | 檢查頻率；第 6 天排程時才用到 |
| enabled | boolean，必填，預設 true | 是否啟用 |
| discovery | varchar，必填，預設 seed | seed／search（種子或搜尋） |
| status | varchar，必填，預設 approved | candidate／approved（候選或已核准） |
| manual_reason | text | 需人工的原因；空白代表自動抓取 |
| last_checked_at | timestamptz | 上次檢查時間（UTC） |

### 資料模型：snapshots（ADR-019）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | bigint identity，主鍵 | |
| source_id | bigint，必填，外鍵 → sources | 屬於哪個來源 |
| url | text，必填 | 實際抓的網址（翻頁時每頁一個） |
| fetched_at | timestamptz，必填 | 抓取時間（UTC） |
| content_hash | varchar(64)，必填 | 正規化文字的 SHA-256 |
| file_path | text，必填 | 原始檔路徑，相對於 `backend/data/snapshots/` |
| http_status | smallint，必填 | HTTP 狀態 |
| etag | text | 伺服器給的 ETag，下次條件式請求用 |
| last_modified | text | 伺服器給的 Last-Modified，下次條件式請求用 |

- 原始檔命名：`<source_id>/<UTC 時間>_<雜湊前 12 碼>.html`（或 `.pdf`）
- 選項欄位和第 1 天一樣用文字欄位加 Python StrEnum，不用 PostgreSQL 原生 ENUM

### 種子

| 名稱 | 網址 | kind | fetch_method | 翻頁 |
| --- | --- | --- | --- | --- |
| Erasmus Mundus Catalogue | https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en | government | html | 是 |
| Chevening Taiwan | https://www.chevening.org/scholarship/taiwan/ | government | html | 否 |
| 教育部 115 年留學獎學金簡章 | https://ws.moe.edu.tw/001/Upload/7/relfile/9909/103401/7332fb46-00f7-4ed4-9af7-6fc63a301b13.pdf | government | pdf | 否 |

### 介面

```python
# core/fetch/base.py：插座（ADR-005）
@dataclass(frozen=True)
class FetchResult:
    url: str                    # 跟隨轉址後的網址
    status: int                 # 200 或 304
    content: bytes              # 304 時是空的
    content_type: str
    etag: str | None
    last_modified: str | None

class BlockedError(Exception):  # reason：「403」「429」「captcha」「robots.txt 禁止」
    reason: str

class Fetcher(Protocol):
    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult: ...

# core/fetch/http.py：轉接頭
class HttpFetcher:
    # httpx.Client（預設 User-Agent，跟隨轉址）
    # 每個網站先讀 robots.txt（同一次執行內快取，符合 RFC 9309 的 24 小時上限）
    # 同一網站兩次請求間隔 ≥ max(設定秒數, Crawl-delay)
    # 帶 If-None-Match／If-Modified-Since；被擋就丟 BlockedError

# core/fetch/etiquette.py（純函式）
def robots_allows(status: int, robots_txt: str, url: str, user_agent: str) -> bool:
    """robots.txt 回 4xx 視為允許、5xx 視為禁止（RFC 9309）；200 時用 Protego 判斷。"""
def detect_block(status: int, body: str) -> str | None:
    """回傳「403」「429」「captcha」，沒被擋回傳 None。"""

# core/fetch/text.py（純函式）
def html_to_text(html: str) -> str:   # 去掉 script、style；區塊元素換行；行內元素直接接起來
def pdf_to_text(data: bytes) -> str:  # pdfplumber，逐頁接起來
def content_hash(text: str) -> str:   # 空白正規化後的 SHA-256

# features/sources/pagination.py（純函式）
def pagination_urls(html: str, page_url: str, *, page_zero_is_first: bool = False) -> list[str]:
    # 同一路徑的 ?page=N 連結，完整網址、去掉錨點、去重；page_zero_is_first 時 ?page=0 換成首頁網址
def missing_pages_warning(previous: int | None, current: int) -> str | None:
    # 上次多頁、這次只剩 1 頁以下就回傳警示文字（漏抓警示，門檻 C）

# shared/settings.py 新增
fetch_min_interval_seconds: float = 5.0

# 指令
# uv run python -m app.features.sources.seed    寫入或更新 3 個種子
# uv run python -m app.features.sources.fetch   抓所有啟用、已核准、不需人工的來源，每個網址印一行結果
```

### fetch 指令的流程

1. 選出 enabled、status=approved、manual_reason 是空白的來源
2. 每個來源要檢查的網址：來源網址、這個來源以前快照過的網址，再加上這次從頁面找到的翻頁連結（最多 50 頁）
3. 每個網址：用最新快照的 ETag／Last-Modified 發條件式請求
   - 304，或雜湊和最新快照相同：沒變，不存檔
   - 雜湊不同或第一次抓：存原始檔、新增一列快照
   - BlockedError：寫入 manual_reason，這個來源停止
   - 網路錯誤或 5xx：印出錯誤，這個來源這次跳過
4. 更新來源的 last_checked_at；每個網址印一行：時間、網址、結果（new／changed／unchanged／blocked／error）、雜湊前 12 碼

### 邊界情況

- 被標籤切開的字（Chevening 的 `<span>202</span><span>7</span>`）要接回「2027」
- 翻頁來源遇到 304 拿不到頁面內容時，沿用上次記錄的頁面網址繼續檢查
- 頁面如果有每次都會變的內容（例如時間戳），雜湊會一直變：實作時連抓兩次比對，發生的話停下來問你
- robots.txt 讀不到：4xx 照 RFC 9309 視為允許，5xx 視為禁止（標記需人工）
- 教育部 PDF 每年換網址（見上方第 9 點）

### 不在第 2 天範圍

- 學程網站的第 2、3 層（ADR-029）
- AI 抽取（第 3 天）；變更紀錄表 changes（第 4 天）
- 排程、重試（第 6 天，#25）；無頭瀏覽器（之後，ADR-027）
- 候選來源與發掘（第 9 天，#27 筆記）；From 標頭（ADR-028）

## 測試哪些行為

依 ADR-022 只測核心邏輯：下面的純函式走紅綠循環（Gate 2），其他用檢查清單的指令驗證。順序就是實作順序，排過讓每個測試都會先紅燈。

| 行為 | 測試檔 | 對象 |
| --- | --- | --- |
| T1 html_to_text 不含 script、style 的內容 | `tests/test_text.py` | `html_to_text` |
| T2 區塊元素之間換行 | 同上 | 同上 |
| T3 被行內標籤切開的字會接回來 | 同上 | 同上 |
| T4 只差空白的兩段文字，雜湊相同 | 同上 | `content_hash` |
| T5 一般回應不算被擋 | `tests/test_etiquette.py` | `detect_block` |
| T6 403 算被擋 | 同上 | 同上 |
| T7 429 算被擋 | 同上 | 同上 |
| T8 內容是驗證碼頁算被擋 | 同上 | 同上 |
| T9 robots.txt 回 4xx 視為允許 | 同上 | `robots_allows` |
| T10 robots.txt 回 5xx 視為禁止 | 同上 | 同上 |
| T11 robots.txt 規則禁止的網址（含萬用字元）視為禁止 | 同上 | 同上 |
| T12 翻頁只取同一路徑的 `?page=N`，轉成完整網址並去重 | `tests/test_pagination.py` | `pagination_urls` |
| T12b 翻頁連結去掉 `#` 錨點（實跑發現的 bug） | 同上 | 同上 |
| T13 打開「第 0 頁就是首頁」時，`?page=0` 換成首頁網址；沒打開時照舊 | 同上 | 同上 |
| T14 第一次抓（沒有上次頁數）不警示 | 同上 | `missing_pages_warning` |
| T15 上次多頁、這次只剩 1 頁，警示並寫出兩次的頁數 | 同上 | 同上 |
| T16 不是「從多頁掉到 1 頁」就不警示（例如 11 → 6、1 → 1） | 同上 | 同上 |

- 每個測試檔先建空的對象模組，測試用「模組.函式」呼叫，紅燈是「找不到函式」，不是匯入錯誤
- 每個行為：先寫測試、跑出紅燈、commit `test: ... (red)`；再寫最少的程式、跑出綠燈、commit

## 檢查清單

指令都在 `backend/` 執行；標「根目錄」的在 `scholarship-agent/` 執行。每一步驗證通過就 commit；收尾跑完整檢查後推到 main。

### 1. 套件

- [x] 加入 httpx、beautifulsoup4、pdfplumber、protego -> verify: `uv run python -c "import httpx, bs4, pdfplumber, protego; print('ok')"`

  ```text
  ok
  ```

  httpx 原本就因為 langchain-google-genai 間接裝了，這次改成直接依賴。

### 2. 資料表

- [x] 自動產生的遷移讀過再套用（貼出 upgrade 內容） -> verify: `sed -n '/def upgrade/,/def downgrade/p' migrations/versions/*sources*.py`

  ```text
  def upgrade() -> None:
      """Upgrade schema."""
      # ### commands auto generated by Alembic - please adjust! ###
      op.create_table('sources',
      sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
      sa.Column('name', sa.Text(), nullable=False),
      sa.Column('url', sa.Text(), nullable=False),
      sa.Column('kind', sa.Enum('government', 'institution', 'university', 'aggregator', name='sourcekind', native_enum=False, length=16), nullable=False),
      sa.Column('country', sa.Text(), nullable=True),
      sa.Column('fetch_method', sa.Enum('html', 'pdf', name='fetchmethod', native_enum=False, length=16), server_default='html', nullable=False),
      sa.Column('follow_pagination', sa.Boolean(), server_default=sa.text('false'), nullable=False),
      sa.Column('check_interval_hours', sa.Integer(), server_default=sa.text('24'), nullable=False),
      sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
      sa.Column('discovery', sa.Enum('seed', 'search', name='discovery', native_enum=False, length=16), server_default='seed', nullable=False),
      sa.Column('status', sa.Enum('candidate', 'approved', name='sourcestatus', native_enum=False, length=16), server_default='approved', nullable=False),
      sa.Column('manual_reason', sa.Text(), nullable=True),
      sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
      sa.PrimaryKeyConstraint('id'),
      sa.UniqueConstraint('url')
      )
      op.create_table('snapshots',
      sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
      sa.Column('source_id', sa.BigInteger(), nullable=False),
      sa.Column('url', sa.Text(), nullable=False),
      sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
      sa.Column('content_hash', sa.String(length=64), nullable=False),
      sa.Column('file_path', sa.Text(), nullable=False),
      sa.Column('http_status', sa.SmallInteger(), nullable=False),
      sa.Column('etag', sa.Text(), nullable=True),
      sa.Column('last_modified', sa.Text(), nullable=True),
      sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
      sa.PrimaryKeyConstraint('id')
      )
      # ### end Alembic commands ###
  ```

  讀過：只有新建兩張表，沒有改名或刪除。產生時 ruff 自動修了 6 處寫法。

- [x] upgrade 建好 sources、snapshots（url 唯一、snapshots.source_id 外鍵） -> verify: `uv run alembic upgrade head && docker compose exec -T postgres psql -U scholar -d scholar -c '\d sources' -c '\d snapshots'`

  ```text
  INFO  [alembic.runtime.migration] Running upgrade 789d912f3a63 -> e6fb5992530b, create sources and snapshots
                                            Table "public.sources"
          Column        |           Type           | Collation | Nullable |             Default
  ----------------------+--------------------------+-----------+----------+----------------------------------
   id                   | bigint                   |           | not null | generated by default as identity
   name                 | text                     |           | not null |
   url                  | text                     |           | not null |
   kind                 | character varying(16)    |           | not null |
   country              | text                     |           |          |
   fetch_method         | character varying(16)    |           | not null | 'html'::character varying
   follow_pagination    | boolean                  |           | not null | false
   check_interval_hours | integer                  |           | not null | 24
   enabled              | boolean                  |           | not null | true
   discovery            | character varying(16)    |           | not null | 'seed'::character varying
   status               | character varying(16)    |           | not null | 'approved'::character varying
   manual_reason        | text                     |           |          |
   last_checked_at      | timestamp with time zone |           |          |
  Indexes:
      "sources_pkey" PRIMARY KEY, btree (id)
      "sources_url_key" UNIQUE CONSTRAINT, btree (url)
  Referenced by:
      TABLE "snapshots" CONSTRAINT "snapshots_source_id_fkey" FOREIGN KEY (source_id) REFERENCES sources(id)

                                        Table "public.snapshots"
      Column     |           Type           | Collation | Nullable |             Default
  ---------------+--------------------------+-----------+----------+----------------------------------
   id            | bigint                   |           | not null | generated by default as identity
   source_id     | bigint                   |           | not null |
   url           | text                     |           | not null |
   fetched_at    | timestamp with time zone |           | not null |
   content_hash  | character varying(64)    |           | not null |
   file_path     | text                     |           | not null |
   http_status   | smallint                 |           | not null |
   etag          | text                     |           |          |
   last_modified | text                     |           |          |
  Indexes:
      "snapshots_pkey" PRIMARY KEY, btree (id)
  Foreign-key constraints:
      "snapshots_source_id_fkey" FOREIGN KEY (source_id) REFERENCES sources(id)
  ```

- [x] 遷移能退回再重做 -> verify: `uv run alembic downgrade -1 && uv run alembic upgrade head && uv run alembic current`

  ```text
  INFO  [alembic.runtime.migration] Running downgrade e6fb5992530b -> 789d912f3a63, create sources and snapshots
  INFO  [alembic.runtime.migration] Running upgrade 789d912f3a63 -> e6fb5992530b, create sources and snapshots
  e6fb5992530b (head)
  ```

- [x] 第二支遷移：sources 加 page_zero_is_first（讀過再套用，能退回再重做） -> verify: `sed -n '/def upgrade/,/def downgrade/p' migrations/versions/*page_zero*.py && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head && uv run alembic current`

  ```text
  def upgrade() -> None:
      """Upgrade schema."""
      # ### commands auto generated by Alembic - please adjust! ###
      op.add_column('sources', sa.Column('page_zero_is_first', sa.Boolean(), server_default=sa.text('false'), nullable=False))
      # ### end Alembic commands ###
  INFO  [alembic.runtime.migration] Running upgrade e6fb5992530b -> aa43fb501dbe, add page_zero_is_first to sources
  INFO  [alembic.runtime.migration] Running downgrade aa43fb501dbe -> e6fb5992530b, add page_zero_is_first to sources
  INFO  [alembic.runtime.migration] Running upgrade e6fb5992530b -> aa43fb501dbe, add page_zero_is_first to sources
  aa43fb501dbe (head)
  ```

  讀過：只有新增一個欄位，既有的 3 筆預設 false。

- [x] 第三支遷移：sources 加 last_page_count（讀過再套用，能退回再重做） -> verify: `sed -n '/def upgrade/,/def downgrade/p' migrations/versions/*last_page_count*.py && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head && uv run alembic current`

  ```text
  def upgrade() -> None:
      """Upgrade schema."""
      # ### commands auto generated by Alembic - please adjust! ###
      op.add_column('sources', sa.Column('last_page_count', sa.Integer(), nullable=True))
      # ### end Alembic commands ###
  INFO  [alembic.runtime.migration] Running upgrade aa43fb501dbe -> ced471d15d28, add last_page_count to sources
  INFO  [alembic.runtime.migration] Running downgrade ced471d15d28 -> aa43fb501dbe, add last_page_count to sources
  INFO  [alembic.runtime.migration] Running upgrade aa43fb501dbe -> ced471d15d28, add last_page_count to sources
  ced471d15d28 (head)
  ```

  讀過：只有新增一個可以留空的欄位。

### 3. 純函式（紅綠循環）

- [x] T1 html_to_text 不含 script、style -> verify: `uv run pytest tests/test_text.py -k excludes_script -q`

  ```text
  紅（commit cf3452f）：
  E       AttributeError: module 'app.core.fetch.text' has no attribute 'html_to_text'
  1 failed in 0.04s
  綠（BeautifulSoup 去掉 script、style 後取文字）：
  1 passed in 0.09s
  ```

- [x] T2 區塊元素之間換行 -> verify: `uv run pytest tests/test_text.py -k block_elements -q`

  ```text
  紅（commit 14bcc26）：
  E       AssertionError: assert 'AB' == 'A\nB'
  1 failed, 1 deselected in 0.12s
  綠（每段文字之間用換行接起來）：
  1 passed, 1 deselected in 0.08s
  ```

- [x] T3 行內標籤切開的字接回來 -> verify: `uv run pytest tests/test_text.py -k inline_split -q`

  ```text
  紅（commit 231d227）：
  E       AssertionError: assert 'Applications...n7\n-\n202\n8' == 'Applications for 2027-2028'
  1 failed, 2 deselected in 0.11s
  綠（只在區塊元素前後換行，行內文字直接接起來）：
  1 passed, 2 deselected in 0.08s
  ```

- [x] T4 只差空白的文字雜湊相同 -> verify: `uv run pytest tests/test_text.py -k hash_ignores_whitespace -q`

  ```text
  紅（commit 6174407）：
  E       AttributeError: module 'app.core.fetch.text' has no attribute 'content_hash'
  1 failed, 3 deselected in 0.12s
  綠（空白縮成一個空格後算 SHA-256）：
  1 passed, 3 deselected in 0.08s
  ```
- [x] T5 一般回應不算被擋 -> verify: `uv run pytest tests/test_etiquette.py -k normal_response -q`

  ```text
  紅（commit c7b5aef）：
  E       AttributeError: module 'app.core.fetch.etiquette' has no attribute 'detect_block'
  2 failed in 0.04s
  綠（回傳 None）：
  2 passed in 0.01s
  ```

- [x] T6 403 算被擋 -> verify: `uv run pytest tests/test_etiquette.py -k status_403 -q`

  ```text
  紅（commit 0c58c70）：
  E       AssertionError: assert None == '403'
  1 failed, 2 deselected in 0.04s
  綠（狀態 403 回傳「403」）：
  1 passed, 2 deselected in 0.01s
  ```

- [x] T7 429 算被擋 -> verify: `uv run pytest tests/test_etiquette.py -k status_429 -q`

  ```text
  紅（commit 261eff1）：
  E       AssertionError: assert None == '429'
  1 failed, 3 deselected in 0.04s
  綠（狀態 403、429 都回傳狀態碼）：
  1 passed, 3 deselected in 0.01s
  ```

- [x] T8 驗證碼頁算被擋 -> verify: `uv run pytest tests/test_etiquette.py -k captcha -q`

  ```text
  紅（commit 099870c）：
  E       assert None == 'captcha'
  1 failed, 1 passed, 3 deselected in 0.04s
  綠（只認整頁攔截頁的特徵）：
  2 passed, 3 deselected in 0.01s
  ```

  `-k captcha` 也會選到 T5 的「表單內嵌驗證碼元件」案例，紅綠兩次都通過，代表新規則沒有誤判內嵌元件。

- [x] T9 robots.txt 4xx 視為允許 -> verify: `uv run pytest tests/test_etiquette.py -k robots_4xx -q`

  ```text
  紅（commit 3cbb32a）：
  E       AttributeError: module 'app.core.fetch.etiquette' has no attribute 'robots_allows'
  1 failed, 5 deselected in 0.11s
  綠（回傳 True）：
  1 passed, 5 deselected in 0.01s
  ```

- [x] T10 robots.txt 5xx 視為禁止 -> verify: `uv run pytest tests/test_etiquette.py -k robots_5xx -q`

  ```text
  紅（commit 7e0f6f7）：
  E       AssertionError: assert True is False
  1 failed, 6 deselected in 0.04s
  綠（狀態 500 以上回傳 False）：
  1 passed, 6 deselected in 0.01s
  ```

- [x] T11 robots.txt 規則禁止（含萬用字元） -> verify: `uv run pytest tests/test_etiquette.py -k robots_rule -q`

  ```text
  紅（commit f854157）：
  E       AssertionError: assert True is False
  FAILED tests/test_etiquette.py::test_robots_rule_decides_when_robots_txt_exists[wildcard_disallow]
  PASSED tests/test_etiquette.py::test_robots_rule_decides_when_robots_txt_exists[allowed_path]
  1 failed, 1 passed, 7 deselected in 0.04s
  綠（200 時交給 Protego 判斷）：
  2 passed, 7 deselected in 0.03s
  ```

- [x] T12 翻頁連結 -> verify: `uv run pytest tests/test_pagination.py -q`

  ```text
  紅（commit 5d37bcd）：
  E       AttributeError: module 'app.features.sources.pagination' has no attribute 'pagination_urls'
  1 failed in 0.04s
  綠（同網站、同路徑、page 是數字才保留）：
  1 passed in 0.08s
  ```

  整套測試：`uv run pytest -q` → 20 passed。

- [x] T12b 翻頁連結去掉 `#` 錨點（實跑發現的 bug） -> verify: `uv run pytest tests/test_pagination.py -k drops_fragments -q`

  ```text
  紅（commit 5b9c503）：
  E       AssertionError: assert ['https://www...main-content'] == ['https://www...ue_en?page=1']
  E         Left contains one more item: 'https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=1#main-content'
  1 failed, 1 deselected in 0.11s
  綠（urldefrag 去掉錨點）：
  1 passed, 1 deselected in 0.09s
  ```

- [x] T13 打開「第 0 頁就是首頁」時 `?page=0` 換成首頁網址 -> verify: `uv run pytest tests/test_pagination.py -k page_zero -q`

  ```text
  紅（commit 79b385c；先用 commit 691b3a7 加上沒有作用的參數，讓紅燈是斷言失敗）：
  E         At index 0 diff: 'https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=0' != 'https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en'
  FAILED tests/test_pagination.py::test_pagination_urls_page_zero_setting[setting_on]
  PASSED tests/test_pagination.py::test_pagination_urls_page_zero_setting[setting_off]
  1 failed, 1 passed, 2 deselected in 0.15s
  綠（設定打開時拿掉 page=0 參數）：
  2 passed, 2 deselected in 0.08s
  ```

  整套測試：`uv run pytest -q` → 23 passed。

- [x] T14 第一次抓不警示 -> verify: `uv run pytest tests/test_pagination.py -k first_run -q`

  ```text
  紅（commit a106233）：
  E       AttributeError: module 'app.features.sources.pagination' has no attribute 'missing_pages_warning'
  1 failed, 4 deselected in 0.12s
  綠（回傳 None）：
  1 passed, 4 deselected in 0.09s
  ```

- [x] T15 多頁掉到 1 頁要警示 -> verify: `uv run pytest tests/test_pagination.py -k drop_to_one -q`

  ```text
  紅（commit bcbda56；commit 時選取字打錯沒選到測試，修正選取字後補驗）：
  E       AssertionError: assert None == '只抓到 1 頁（上次 11 頁），翻頁可能失效'
  綠（有上次頁數就警示）：
  1 passed, 5 deselected in 0.08s
  ```

- [x] T16 其他情況不警示 -> verify: `uv run pytest tests/test_pagination.py -k no_warning -q`

  ```text
  紅（commit d5aeb79）：
  E       AssertionError: assert '只抓到 1 頁（上次 1 頁），翻頁可能失效' is None
  E       AssertionError: assert '只抓到 6 頁（上次 11 頁），翻頁可能失效' is None
  2 failed, 6 deselected in 0.12s
  綠（上次大於 1 頁、這次 1 頁以下才警示）：
  2 passed, 6 deselected in 0.08s
  ```

  整套測試：`uv run pytest -q` → 27 passed。

### 4. 種子

- [x] seed 寫入 3 個來源，重跑不重複 -> verify: `uv run python -m app.features.sources.seed && uv run python -m app.features.sources.seed && docker compose exec -T postgres psql -U scholar -d scholar -c "select id, name, kind, fetch_method, follow_pagination from sources order by id"`

  ```text
  已寫入或更新 3 個種子來源
  已寫入或更新 3 個種子來源
   id |            name             |    kind    | fetch_method | follow_pagination
  ----+-----------------------------+------------+--------------+-------------------
    1 | Erasmus Mundus Catalogue    | government | html         | t
    2 | Chevening Taiwan            | government | html         | f
    3 | 教育部 115 年留學獎學金簡章 | government | pdf          | f
  (3 rows)
  ```

- [x] 重跑 seed 後只有 EACEA 打開「第 0 頁就是首頁」 -> verify: `uv run python -m app.features.sources.seed && docker compose exec -T postgres psql -U scholar -d scholar -c "select id, name, page_zero_is_first from sources order by id"`

  ```text
  已寫入或更新 3 個種子來源
   id |            name             | page_zero_is_first
  ----+-----------------------------+--------------------
    1 | Erasmus Mundus Catalogue    | t
    2 | Chevening Taiwan            | f
    3 | 教育部 115 年留學獎學金簡章 | f
  (3 rows)
  ```

### 5. 抓取

- [x] 第一次抓：3 個來源都有快照（EACEA 11 頁、Chevening 1 頁、PDF 1 份），原始檔在 data/snapshots/，EACEA 的上次頁數是 11 -> verify: `uv run python -m app.features.sources.fetch && docker compose exec -T postgres psql -U scholar -d scholar -c "select source_id, count(*) from snapshots group by source_id order by source_id" -c "select id, last_page_count from sources order by id" && find data/snapshots -type f | wc -l`

  ```text
  == 1 Erasmus Mundus Catalogue
  08:46:40  new        5f23889b2b41    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en
  08:46:45  new        45acfb2318ee    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=1
  08:46:51  new        f7f4cc18604c    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=2
  08:46:57  new        3dbb6af7f6db    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=10
  08:47:02  new        0850b5922c9e    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=3
  08:47:08  new        c0798a95250b    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=4
  08:47:14  new        cd5e9b842eb3    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=9
  08:47:19  new        101c2f353a6d    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=8
  08:47:25  new        c0d347faca25    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=5
  08:47:31  new        249508a5dd3c    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=6
  08:47:36  new        7422bcf81983    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=7
  == 2 Chevening Taiwan
  08:47:48  new        89e8dd7e7f9a    https://www.chevening.org/scholarship/taiwan/
  == 3 教育部 115 年留學獎學金簡章
  08:47:57  new        093808c1e5b1    https://ws.moe.edu.tw/001/Upload/7/relfile/9909/103401/7332fb46-00f7-4ed4-9af7-6fc63a301b13.pdf
   source_id | count
  -----------+-------
           1 |    11
           2 |     1
           3 |     1
   id | last_page_count
  ----+-----------------
    1 |              11
    2 |
    3 |
        13
  ```

  這是修好錨點、`?page=0` 和憑證之後，清空資料庫重跑的結果；第一次實跑的問題記在上方「執行時發現、由使用者決定」。

- [x] 第二次抓：全部沒變，快照數不增加；同一網站的請求間隔至少 5 秒（看輸出的時間欄） -> verify: `uv run python -m app.features.sources.fetch && docker compose exec -T postgres psql -U scholar -d scholar -c "select count(*) from snapshots"`

  ```text
  == 1 Erasmus Mundus Catalogue
  08:48:14  unchanged  5f23889b2b41    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en
  08:48:20  unchanged  0850b5922c9e    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=3
  08:48:26  unchanged  45acfb2318ee    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=1
  08:48:31  unchanged  cd5e9b842eb3    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=9
  08:48:37  unchanged  c0d347faca25    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=5
  08:48:42  unchanged  f7f4cc18604c    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=2
  08:48:48  unchanged  3dbb6af7f6db    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=10
  08:48:54  unchanged  101c2f353a6d    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=8
  08:48:59  unchanged  c0798a95250b    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=4
  08:49:05  unchanged  7422bcf81983    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=7
  08:49:11  unchanged  249508a5dd3c    https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en?page=6
  == 2 Chevening Taiwan
  08:49:21  unchanged  89e8dd7e7f9a    https://www.chevening.org/scholarship/taiwan/
  == 3 教育部 115 年留學獎學金簡章
  08:49:27  unchanged  304             https://ws.moe.edu.tw/001/Upload/7/relfile/9909/103401/7332fb46-00f7-4ed4-9af7-6fc63a301b13.pdf
   count
  -------
      13
  ```

  EACEA 每次請求間隔 5–6 秒；教育部回 304（伺服器說沒更新，沒有重新下載）；每頁雜湊和第一次相同，頁面沒有每次都會變的內容。

- [x] Chevening 的文字有「2027-2028」和「Closed for applications」 -> verify: `uv run python -c "from pathlib import Path; from app.core.fetch.text import html_to_text; f = sorted(Path('data/snapshots/2').glob('*.html'))[-1]; t = html_to_text(f.read_text()); print('2027-2028' in t, 'Closed for applications' in t)"`

  ```text
  True True
  ```

- [x] 被擋的來源標記需人工；翻頁來源從 5 頁掉到 1 頁會警示，且上次頁數更新成 1（本機假伺服器：`/blocked` 回 403、`/list` 回只有一頁的 HTML，測完刪除） -> verify:

  ```bash
  uv run python -c "
  import http.server as h
  class H(h.BaseHTTPRequestHandler):
      def do_GET(s):
          if s.path == '/blocked':
              s.send_response(403); s.end_headers()
          elif s.path == '/list':
              s.send_response(200); s.send_header('Content-Type', 'text/html'); s.end_headers(); s.wfile.write(b'<p>only one page</p>')
          else:
              s.send_response(404); s.end_headers()
      def log_message(s, *a): pass
  h.HTTPServer(('127.0.0.1', 8765), H).serve_forever()
  " & SERVER=$!
  docker compose exec -T postgres psql -U scholar -d scholar -c "insert into sources (name, url, kind) values ('403 測試', 'http://127.0.0.1:8765/blocked', 'institution')" -c "insert into sources (name, url, kind, follow_pagination, last_page_count) values ('漏抓測試', 'http://127.0.0.1:8765/list', 'institution', true, 5)"
  uv run python -m app.features.sources.fetch
  docker compose exec -T postgres psql -U scholar -d scholar -c "select name, manual_reason, last_page_count from sources where url like 'http://127.0.0.1:8765/%' order by id"
  for id in $(docker compose exec -T postgres psql -U scholar -d scholar -t -A -c "select id from sources where url like 'http://127.0.0.1:8765/%'"); do rm -rf "data/snapshots/$id"; done
  docker compose exec -T postgres psql -U scholar -d scholar -c "delete from snapshots where source_id in (select id from sources where url like 'http://127.0.0.1:8765/%')" -c "delete from sources where url like 'http://127.0.0.1:8765/%'"; kill $SERVER
  ```

  ```text
  == 10 403 測試
  08:51:15  blocked    403             http://127.0.0.1:8765/blocked
  == 11 漏抓測試
  08:51:20  new        14f102440849    http://127.0.0.1:8765/list
  08:51:20  warning    漏抓警示            只抓到 1 頁（上次 5 頁），翻頁可能失效
     name   | manual_reason | last_page_count
  ----------+---------------+-----------------
   403 測試 | 403           |
   漏抓測試 |               |               1
  DELETE 1
  DELETE 2
  ```

  清除後檢查：sources 3 筆、snapshots 13 筆、檔案 13 個，回到測試前的狀態。（同一次執行裡 3 個真實來源都是 unchanged，輸出省略。）

### 6. 收尾

- [x] 全部測試、ruff、mypy 通過 -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`

  ```text
  platform darwin -- Python 3.13.13, pytest-9.1.1, pluggy-1.6.0
  configfile: pyproject.toml
  collected 27 items

  tests/test_etiquette.py .........                                        [ 33%]
  tests/test_pagination.py ........                                        [ 62%]
  tests/test_scoring.py ......                                             [ 85%]
  tests/test_text.py ....                                                  [100%]

  ============================== 27 passed in 0.31s ==============================
  All checks passed!
  Success: no issues found in 25 source files
  ```

- [x] `docs/progress.md` 更新為第 2 天完成 -> verify: `cat ../docs/progress.md`

  ```text
  # 目前進度

  每完成一天，更新這一檔。各天的範圍見 `docs/spec.md` 的「開發排程」。

  - 第 1 天完成（2026-10-09），已合併進 main：專案骨架、scholarships 表與第一支遷移、Gemini 抽取指令、評分上限規則
  - 第 2 天完成（2026-10-10），已推上 main：sources、snapshots 表，種子指令，抓取指令（遵守 robots.txt、限速、條件式請求、被擋就標記需人工、漏抓警示），3 個種子都抓得到

  下一步：第 3 天開始前，先決定 #12 長文件處理策略、#13 抽取策略（含學程網站第 2、3 層怎麼找，ADR-029）、#23 是否需要向量檢索。
  ```
- [x] 推到 main -> verify（根目錄）: `git fetch -q && git status -sb | head -1`

  ```text
  ## main...origin/main
  ```

  推之前檢查：要推的 53 個 commit 裡沒有金鑰，也沒有被追蹤的 `.env`。沒有 `[ahead N]` 代表本機和 GitHub 一致。

## 第 3 天開始前要決定

#12 長文件處理策略、#13 抽取策略（含學程網站第 2、3 層怎麼找，ADR-029）、#23 是否需要向量檢索（依 `docs/decision-format.md` 說明後請使用者決定）。
