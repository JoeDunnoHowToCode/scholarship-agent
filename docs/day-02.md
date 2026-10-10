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
def pagination_urls(html: str, page_url: str) -> list[str]:  # 同一路徑的 ?page=N 連結，完整網址、去重

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

### 5. 抓取

- [ ] 第一次抓：3 個來源都有快照（EACEA 11 頁、Chevening 1 頁、PDF 1 份），原始檔在 data/snapshots/ -> verify: `uv run python -m app.features.sources.fetch && docker compose exec -T postgres psql -U scholar -d scholar -c "select source_id, count(*) from snapshots group by source_id order by source_id" && find data/snapshots -type f | wc -l`
- [ ] 第二次抓：全部沒變，快照數不增加；同一網站的請求間隔至少 5 秒（看輸出的時間欄） -> verify: `uv run python -m app.features.sources.fetch && docker compose exec -T postgres psql -U scholar -d scholar -c "select count(*) from snapshots"`
- [ ] Chevening 的文字有「2027-2028」和「Closed for applications」 -> verify: `uv run python -c "from pathlib import Path; from app.core.fetch.text import html_to_text; f = sorted(Path('data/snapshots/2').glob('*.html'))[-1]; t = html_to_text(f.read_text()); print('2027-2028' in t, 'Closed for applications' in t)"`
- [ ] 被擋的來源會標記需人工（本機假伺服器回 403，測完刪除） -> verify:

  ```bash
  uv run python -c "import http.server as h; h.HTTPServer(('127.0.0.1', 8765), type('H', (h.BaseHTTPRequestHandler,), {'do_GET': lambda s: (s.send_response(403), s.end_headers())})).serve_forever()" & SERVER=$!
  docker compose exec -T postgres psql -U scholar -d scholar -c "insert into sources (name, url, kind) values ('403 測試', 'http://127.0.0.1:8765/', 'institution')"
  uv run python -m app.features.sources.fetch
  docker compose exec -T postgres psql -U scholar -d scholar -c "select name, manual_reason from sources where url = 'http://127.0.0.1:8765/'"
  docker compose exec -T postgres psql -U scholar -d scholar -c "delete from sources where url = 'http://127.0.0.1:8765/'"; kill $SERVER
  ```

### 6. 收尾

- [ ] 全部測試、ruff、mypy 通過 -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] `docs/progress.md` 更新為第 2 天完成 -> verify: `cat ../docs/progress.md`
- [ ] 推到 main -> verify（根目錄）: `git fetch -q && git status -sb | head -1`

## 第 3 天開始前要決定

#12 長文件處理策略、#13 抽取策略（含學程網站第 2、3 層怎麼找，ADR-029）、#23 是否需要向量檢索（依 `docs/decision-format.md` 說明後請使用者決定）。
