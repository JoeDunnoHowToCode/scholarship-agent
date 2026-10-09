# 第 1 天：開工

軌道：一般功能（Gate 1–3）。這份是 Gate 1 計畫，使用者核准後才動程式。

目標：專案骨架跑得起來、scholarships 表建好、Gemini 能回傳結構化資料並存進資料庫、評分上限規則的單元測試通過。

## 本計畫記錄的決定

- 第 1 天只建 scholarships 表，其他表在用到的那天加上（ADR-024）
- 主鍵用整數自動遞增（ADR-025）
- GitHub repo 用 private，名稱 `scholarship-agent`；第 1 天收尾時才建立
- commit 身分：`Joe <38872920+JoeDunnoHowToCode@users.noreply.github.com>`，設成全域（執行時發現沒設定，使用者決定）
- SQLAlchemy 鎖在 2.0 系列（`>=2.0,<2.1`）：`>=2` 會裝到 2.1，和 ADR-017 不符（執行時發現，使用者決定）
- Alembic 每產生一支遷移就自動跑 `ruff check --fix`（alembic.ini 的 post_write_hooks）：Alembic 範本的 import 順序與舊式型別寫法不符合 ruff 規則（執行時發現，使用者決定）

## 和原版不同的地方

1. 只裝第 1 天用得到的套件；rq（第 6 天）、langgraph（第 9 天）、httpx（第 2 天）用到再裝
2. 不跑 `brew install uv`：uv 0.11.14 已經裝好，再裝會有兩份
3. Docker 的連接埠只綁 127.0.0.1：預設會開放給同一個網路的其他裝置，而資料庫密碼很弱
4. Docker 加健康檢查：`docker compose up -d --wait` 會等到資料庫真的能連線才結束
5. 金鑰由 settings 明確傳給模型：pydantic-settings 讀 `.env` 時不會放進環境變數，LangChain 自己讀不到
6. 不設定 temperature：Gemini 3 系列官方建議維持預設 1.0，調低可能出現重複迴圈（評分的溫度另列待決定 #45）
7. main 的第一個 commit 只放現有文件：新 repo 沒有 main 就開不了 PR；之後所有程式都在 `day-01` 分支
8. ADR-011 的「驗證失敗回饋重試」和 ADR-008 的引用檢查移到第 3 天（抽取與驗證者那天）

## 使用者要做的事

- Gemini 金鑰：從有開帳單的 Google AI Studio 專案建立（ADR-012 的付費方案），在 `backend/.env` 寫一行 `GOOGLE_API_KEY=你的金鑰`，不要貼進對話。第 7 步才用到
- 已確認（2026-10-09）：Docker 29.4.3 執行中、uv 0.11.14、Homebrew

## 設計草圖

### 資料夾（第 1 天建立的部分）

```text
scholarship-agent/
  docker-compose.yml
  backend/
    pyproject.toml            # 依賴，以及 ruff、mypy、pytest 設定
    .python-version           # 3.13
    .env                      # 使用者自己寫，不進 git
    alembic.ini
    migrations/
    app/                      # 每個資料夾都有 __init__.py
      main.py                 # FastAPI，只有 GET /health
      shared/settings.py      # 讀 backend/.env
      shared/db.py            # Base、engine、Session（同步，ADR-017）
      core/llm/base.py        # 插座：StructuredLLM
      core/llm/gemini.py      # 轉接頭：GeminiLLM
      features/scholarships/models.py    # Scholarship 資料表類別
      features/scholarships/extract.py   # ScholarshipDraft、提示詞、extract 指令
      features/matching/scoring.py       # apply_caps
    tests/
      test_scoring.py
      fixtures/sample_call.txt           # 自己寫的虛構簡章，不抓真網站
```

### docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: scholar
      POSTGRES_PASSWORD: scholar
      POSTGRES_DB: scholar
    ports: ["127.0.0.1:5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U scholar -d scholar"]
      interval: 2s
      retries: 15
  redis:
    image: redis:7
    ports: ["127.0.0.1:6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      retries: 15
volumes:
  pgdata:
```

### 資料模型：scholarships（ADR-018、024、025）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | bigint identity，主鍵 | ADR-025 |
| name | text，必填 | 原文名稱 |
| name_zh | text | 中文名稱 |
| provider | text | 提供單位 |
| countries | text[]，必填，預設空 | 留學國家（篩選用） |
| degrees | text[]，必填，預設空 | 學位：bachelor、master、phd（篩選用） |
| fields | text[]，必填，預設空 | 領域 |
| coverage | text | 補助內容 |
| amount | text | 金額，保留原文，例如「每月 GBP 1,400」 |
| taiwan_eligibility | varchar，必填，預設 unclear | yes／no／unclear（篩選用） |
| taiwan_conditions | text | 台灣專屬條件 |
| language_requirements | text | 語言要求 |
| other_eligibility | text | 其他資格 |
| requires_admission | boolean | 是否需先錄取；不知道就留空 |
| official_url | text | 官方網址 |
| last_verified_at | timestamptz | 最後驗證時間（UTC），第 3 天由驗證者寫入 |
| status | varchar，必填，預設 active | active／archived |
| extracted | jsonb，必填 | 完整抽取結果（ADR-018） |

- yes／no／unclear 這類選項用文字欄位，Python 端用 StrEnum 檢查；不用 PostgreSQL 原生 ENUM，因為改選項時要手寫遷移
- 不加索引：約 300 筆用不到

### 介面

```python
# shared/settings.py
class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://scholar:scholar@localhost:5432/scholar"
    google_api_key: SecretStr | None = None   # 用到 Gemini 時才檢查
    llm_model: str = "gemini-3.5-flash-lite"  # ADR-015

# core/llm/base.py：插座（ADR-005）
class StructuredLLM(Protocol):
    def extract(self, prompt: str, schema: type[M]) -> M: ...   # M 是 Pydantic 模型

# core/llm/gemini.py：轉接頭（ADR-010、011、015）
class GeminiLLM:
    def __init__(self, model: str, api_key: SecretStr | None) -> None: ...
    def extract(self, prompt: str, schema: type[M]) -> M: ...
    # ChatGoogleGenerativeAI(model=..., api_key=...).with_structured_output(schema)
    # 預設 method="json_schema"，就是 Gemini 原生 schema

# features/scholarships/extract.py
PROMPT_VERSION = "extract-1"            # 改提示詞就要改版本號
class ScholarshipDraft(BaseModel):
    name: str
    provider: str | None
    countries: list[str]
    degrees: list[Literal["bachelor", "master", "phd"]]
    taiwan_eligibility: Literal["yes", "no", "unclear"]   # 原文沒提到台灣一律 unclear
    taiwan_evidence: str | None         # 逐字引用原文
    deadline: str | None                # YYYY-MM-DD
    deadline_evidence: str | None       # 逐字引用原文
# 指令：uv run python -m app.features.scholarships.extract <簡章文字檔> [--url 官方網址]
# 存檔：上面欄位寫進同名欄位，整個 ScholarshipDraft 寫進 extracted

# features/matching/scoring.py
CheckResult = Literal["pass", "fail", "unclear"]
def apply_caps(score: float, checks: Sequence[CheckResult]) -> float: ...

# main.py
GET /health -> {"status": "ok"}
```

工具設定：ruff 用預設規則（0.16 版預設就有 30 多類，已包含 import 排序 I；原本寫「預設規則加 I」是誤以為預設只有 E、F）；mypy 用 strict 並啟用 pydantic 外掛；pytest 設 `pythonpath = ["."]`，讓測試能 import app。

### 邊界情況

- 原文沒提到台灣：提示詞要求填 unclear（spec：絕不推定可以）。第 1 天的範例有明寫台灣，準確度留到第 10 天評估
- 原文沒有截止日：deadline 留空
- 模型回傳的資料不符合 schema：第 1 天直接報錯結束，重試在第 3 天
- 金鑰沒設定或是空的：extract 指令停下來，提示在 `backend/.env` 設定 `GOOGLE_API_KEY`；不需要金鑰的步驟照常能跑
- 重跑 extract 會再新增一列：去重在第 4 天
- apply_caps：不符合和待確認同時出現時取 20；分數本來就低於上限時不變；沒有檢查項目時不變

### 不在第 1 天範圍

- 其他 8 張表（ADR-024）
- 驗證失敗回饋重試（ADR-011）、引用是否真的出現在原文（ADR-008）→ 第 3 天
- 截止日轉 UTC 並保留原始時區（cycles 表）→ 第 4 天
- 給 API 用的 Scholarship Pydantic 模型 → 第一個回傳獎學金的 API 那天
- token 與費用紀錄、快取（ADR-013）→ 第 9 天
- RQ、LangGraph、抓取、通知

## 測試哪些行為

依 ADR-022 只測核心邏輯：只有評分上限規則走紅綠循環（Gate 2），其他步驟用檢查清單的指令驗證。

| 行為 | 測試檔 | 對象 |
| --- | --- | --- |
| B1 有「待確認」時總分上限 80 | `backend/tests/test_scoring.py` | `app/features/matching/scoring.py` 的 `apply_caps` |
| B2 有「不符合」時上限 20，而且優先於待確認 | 同上 | 同上 |
| B3 全部符合或沒有檢查項目時，分數不變 | 同上 | 同上 |
| B4 分數本來就低於上限時不被拉高 | 同上 | 同上 |

- 骨架步驟先建一個空的 `scoring.py`，測試用 `scoring.apply_caps(...)` 呼叫，所以 B1 的紅燈是「找不到 apply_caps」，不是匯入錯誤
- 每個行為：先寫測試、跑出紅燈、commit `test: ... (red)`；再寫最少的程式、跑出綠燈、commit

## 檢查清單

指令都在 `backend/` 執行；標「根目錄」的在 `scholarship-agent/` 執行。每一步驗證通過就 commit。

### 1. Git 起步

- [x] main 有一個只含現有文件（CLAUDE.md、docs/、.gitignore）的 commit，目前在 day-01 分支 -> verify（根目錄）: `git log --oneline main && git branch --show-current`

  ```text
  e8b664e docs: import project docs before day 1
  day-01
  ```

### 2. 後端專案

- [x] backend 專案用 Python 3.13，裝好第 1 天的套件 -> verify: `uv run python -c "import sys, fastapi, sqlalchemy, alembic, psycopg, pydantic_settings, langchain_google_genai; print(sys.version.split()[0])"`

  ```text
  3.13.13
  ```

  補充檢查 `uv run python -c "import sqlalchemy; print('sqlalchemy', sqlalchemy.__version__)"`：

  ```text
  sqlalchemy 2.0.54
  ```

### 3. Docker

- [x] PostgreSQL 與 Redis 都健康，連接埠只綁 127.0.0.1 -> verify（根目錄）: `docker compose up -d --wait && docker compose ps`

  ```text
  NAME                           IMAGE         COMMAND                  SERVICE    CREATED         STATUS                   PORTS
  scholarship-agent-postgres-1   postgres:17   "docker-entrypoint.s…"   postgres   4 seconds ago   Up 2 seconds (healthy)   127.0.0.1:5432->5432/tcp
  scholarship-agent-redis-1      redis:7       "docker-entrypoint.s…"   redis      4 seconds ago   Up 2 seconds (healthy)   127.0.0.1:6379->6379/tcp
  ```

### 4. API 骨架

- [x] API 啟動，GET /health 回 {"status":"ok"} -> verify: `uv run uvicorn app.main:app --port 8000 & PID=$!; curl -s --retry 10 --retry-connrefused --retry-delay 1 localhost:8000/health; kill $PID`

  ```text
  {"status":"ok"}
  ```

### 5. scholarships 表與第一個遷移

- [x] 自動產生的遷移讀過再套用（貼出 upgrade 內容） -> verify: `sed -n '/def upgrade/,/def downgrade/p' migrations/versions/*.py`

  ```text
  def upgrade() -> None:
      """Upgrade schema."""
      # ### commands auto generated by Alembic - please adjust! ###
      op.create_table('scholarships',
      sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
      sa.Column('name', sa.Text(), nullable=False),
      sa.Column('name_zh', sa.Text(), nullable=True),
      sa.Column('provider', sa.Text(), nullable=True),
      sa.Column('countries', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
      sa.Column('degrees', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
      sa.Column('fields', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
      sa.Column('coverage', sa.Text(), nullable=True),
      sa.Column('amount', sa.Text(), nullable=True),
      sa.Column('taiwan_eligibility', sa.Enum('yes', 'no', 'unclear', name='taiwaneligibility', native_enum=False, length=16), server_default='unclear', nullable=False),
      sa.Column('taiwan_conditions', sa.Text(), nullable=True),
      sa.Column('language_requirements', sa.Text(), nullable=True),
      sa.Column('other_eligibility', sa.Text(), nullable=True),
      sa.Column('requires_admission', sa.Boolean(), nullable=True),
      sa.Column('official_url', sa.Text(), nullable=True),
      sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
      sa.Column('status', sa.Enum('active', 'archived', name='scholarshipstatus', native_enum=False, length=16), server_default='active', nullable=False),
      sa.Column('extracted', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
      sa.PrimaryKeyConstraint('id')
      )
      # ### end Alembic commands ###


  def downgrade() -> None:
  ```

  讀過：只有新建 scholarships 一張表，沒有改名或刪除。

- [x] alembic upgrade head 建好 scholarships：bigint identity 主鍵、三個 text[]、jsonb -> verify: `uv run alembic upgrade head && docker compose exec -T postgres psql -U scholar -d scholar -c '\d scholarships'`

  ```text
  INFO  [alembic.runtime.migration] Running upgrade  -> 789d912f3a63, create scholarships
                                          Table "public.scholarships"
          Column         |           Type           | Collation | Nullable |             Default
  -----------------------+--------------------------+-----------+----------+----------------------------------
   id                    | bigint                   |           | not null | generated by default as identity
   name                  | text                     |           | not null |
   name_zh               | text                     |           |          |
   provider              | text                     |           |          |
   countries             | text[]                   |           | not null | '{}'::text[]
   degrees               | text[]                   |           | not null | '{}'::text[]
   fields                | text[]                   |           | not null | '{}'::text[]
   coverage              | text                     |           |          |
   amount                | text                     |           |          |
   taiwan_eligibility    | character varying(16)    |           | not null | 'unclear'::character varying
   taiwan_conditions     | text                     |           |          |
   language_requirements | text                     |           |          |
   other_eligibility     | text                     |           |          |
   requires_admission    | boolean                  |           |          |
   official_url          | text                     |           |          |
   last_verified_at      | timestamp with time zone |           |          |
   status                | character varying(16)    |           | not null | 'active'::character varying
   extracted             | jsonb                    |           | not null |
  Indexes:
      "scholarships_pkey" PRIMARY KEY, btree (id)
  ```

- [x] 遷移能退回再重做 -> verify: `uv run alembic downgrade base && uv run alembic upgrade head && uv run alembic current`

  ```text
  INFO  [alembic.runtime.migration] Running downgrade 789d912f3a63 -> , create scholarships
  INFO  [alembic.runtime.migration] Running upgrade  -> 789d912f3a63, create scholarships
  789d912f3a63 (head)
  ```

  補充檢查（ruff 自動修正遷移之後）：`uv run alembic revision -m "hook check"` 產生一支空遷移，確認自動修正有跑，檢查完刪掉；再跑 `uv run ruff check . && uv run mypy app`。上面三項重跑結果相同，建表內容沒變。

  ```text
  Running post write hook 'ruff' ...
  Found 10 errors (10 fixed, 0 remaining).
  All checks passed!
  Success: no issues found in 10 source files
  ```

### 6. 評分上限規則（紅綠循環）

- [x] B1 有待確認時上限 80 -> verify: `uv run pytest tests/test_scoring.py -k unclear_caps_at_80 -q`

  ```text
  紅（commit e422487）：
  E       AttributeError: module 'app.features.matching.scoring' has no attribute 'apply_caps'
  1 failed in 0.04s
  綠（最少的程式：直接回傳 80）：
  1 passed in 0.01s
  ```
- [x] B2 有不符合時上限 20，而且優先於待確認 -> verify: `uv run pytest tests/test_scoring.py -k fail_caps_at_20 -q`

  ```text
  紅（commit b67264c）：
  E       AssertionError: assert 80 == 20
  1 failed, 1 deselected in 0.03s
  綠（有 fail 就回傳 20，否則 80）：
  1 passed, 1 deselected in 0.01s
  ```
- [x] B3 全部符合或沒有檢查項目時不變 -> verify: `uv run pytest tests/test_scoring.py -k all_pass_keeps_score -q`

  ```text
  紅（commit 0ef2354）：
  E       AssertionError: assert 80 == 95
  2 failed, 2 deselected in 0.04s
  綠（有 unclear 才回傳 80，否則回傳原分數）：
  2 passed, 2 deselected in 0.01s
  ```
- [ ] B4 分數低於上限時不被拉高 -> verify: `uv run pytest tests/test_scoring.py -k never_raises_score -q`

### 7. Gemini 抽取（需要金鑰）

- [ ] 金鑰是空的時，extract 停下來並提示設定 GOOGLE_API_KEY -> verify: `GOOGLE_API_KEY= uv run python -m app.features.scholarships.extract tests/fixtures/sample_call.txt`
- [ ] 範例簡章經 Gemini 3.5 Flash-Lite 抽成 ScholarshipDraft 並存進 scholarships（預期 taiwan_eligibility 是 yes、deadline 是 2027-01-15） -> verify: `uv run python -m app.features.scholarships.extract tests/fixtures/sample_call.txt && docker compose exec -T postgres psql -U scholar -d scholar -c "select id, name, countries, degrees, taiwan_eligibility, extracted->>'deadline' as deadline from scholarships order by id desc limit 1"`

### 8. 收尾

- [ ] 全部測試、ruff、mypy 通過 -> verify: `uv run pytest && uv run ruff check . && uv run mypy app`
- [ ] `docs/progress.md` 更新為第 1 天完成 -> verify: `cat ../docs/progress.md`
- [ ] 建 private repo、推 main 與 day-01、開 PR -> verify（根目錄）: `gh pr view day-01 --json url,state,baseRefName,headRefName`

## 第 2 天開始前要決定

#11 抓取工具、#15 來源設定的存放方式、#16 爬蟲禮儀與合規等級（依 `docs/decision-format.md` 說明後請使用者決定）。
