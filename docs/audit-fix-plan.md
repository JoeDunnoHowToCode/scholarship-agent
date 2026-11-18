# 總檢查的修正：實作計畫（2026-11-18）

狀態：**你 11-19 核准，進行中（段 1）**。

- 問題：`docs/audit-2026-11-18.md`
- 決定：ADR-112–119（你 11-18 的選擇）
- 不在這份計畫：ADR-118（每日檢查搬機器）要先選哪一台機器，選好另外寫計畫

## 0. 一句話

先修 6 個 bug，讓列表只剩該出現的資料；再依你的決定改流程；最後改抽取（地區名額、申請方式、沒有日期的原因），全部重抽一次，再把網頁上看不懂的標示改寫。

## 1. 分段與順序

| 段 | 內容 | 決定 | 類型 | 要不要花 AI 費用 |
| --- | --- | --- | --- | --- |
| 1 | 6 個 bug：A6、A4、A3、C1 第 4 種、D5 兩項 | — | Bug fix（紅綠） | 不用 |
| 2 | 被擋的來源自動再試 | ADR-116 | 新規則 | 不用 |
| 3 | 原文寫明不提供就封存 | ADR-114 | 新規則 | 不用 |
| 4 | 候選積壓就暫停 agent | ADR-117 | 新規則 | 不用（省錢） |
| 5 | 設定頁「待你確認」清單 | ADR-115 | API＋網頁 | 不用 |
| 6 | 官網連結指向第一個申請頁 | ADR-113 | 資料表＋抓取 | 重新挑子頁，約 NT$5 |
| 7 | 抽取改版：地區名額、申請方式、沒有日期的原因、漏抽偵測、子頁重挑 | ADR-112、119 | 提示詞＋schema＋遷移 | 先試 10 個來源，約 NT$5 |
| 8 | 全部重抽一次，重新檢查 | ADR-112、119 | 執行 | 上限 NT$200 |
| 9 | 網頁標示改寫 | ADR-119 | 網頁 | 不用 |
| 10 | 清理資料（刪除要你另外同意） | E1 | 資料 | 不用 |

順序的理由：段 1–5 不花錢、互不相依，修完列表就少了 65 筆不該出現的；段 7 的提示詞一次改完，段 8 只重抽一次；段 9 要等段 7 有了「申請方式」與「沒有日期的原因」才能寫；段 10 要等段 8 重抽完，才知道哪些封存的資料真的沒用了。

## 2. 設計草圖

### 段 1：6 個 bug

| 問題 | 現在 | 改成 | 位置 |
| --- | --- | --- | --- |
| A6 被排除的來源還在列表 | 排除只改來源；列表不看來源狀態 | 排除、停用來源時一起封存它的獎學金；列表、評分只看已加入且啟用的來源 | `discovery/intake.py`、`scholarships/api.py`、`matching/score.py` |
| A4 使用中的被標成封存那筆的重複 | 每組由最小的 id 當代表 | 先選使用中的，再選最小的 id | `scholarships/dedup.py` 的 `find_duplicates` |
| A3 同一個網站兩個來源 | 用網址字串比對 | 新增目錄學程前先正規化網址（`dedup.normalize_url`）再比對 | `sources/catalogue.py` 的 `upsert_programme` |
| C1 第 4 種 AI 補的年份被丟掉 | 年份不在引用裡就整筆不建 | 年份不在引用裡、但月日都在：丟掉 AI 的年份，改用程式推算（ADR-110），標「年份是推算的」 | `scholarships/extract.py` 的 `save_cycles` |
| D5 已封存的也每輪評分 | 評分只排除重複的 | 已封存的沿用上次的分數，不送 AI | `matching/score.py` |
| D5 重抽造成的變更紀錄 | 抽出來的文字不同就記一筆 | 套用和通知一樣的關卡（ADR-064）：官網原文沒變的欄位不記 | `scholarships/changes.py` |

邊界情況：
- A6：被排除的來源之後又被加入（例如你在設定頁打開），獎學金要喚回。用現有的 `refresh` 喚回規則。
- A3：現有的 6 組重複來源，程式修好後各停用一個（留還有使用中獎學金的那個）。**停用是改資料，核准這份計畫就算同意**；停用可以在設定頁恢復。

### 段 2：被擋的來源自動再試（ADR-116）

```
被擋 → 原因是什麼？
   ├─ 429 → 記下被擋的日期，7 天後再試（伺服器有給 Retry-After 就照它，但至少 1 天）
   ├─ 403 → 記下被擋的日期，30 天後再試
   └─ robots.txt 禁止、captcha → 和現在一樣標需人工，不再試
再試成功 → 清掉標記，回到每天檢查
```

- 資料表：`sources` 加 `blocked_at`（被擋的日期）；`manual_reason` 只留給 robots.txt 與 captcha。現有 34 個標記，429 與 403 的遷移成「從 11-18 起算再試」
- EACEA 目錄這類翻頁來源，頁與頁之間改成等 15 秒（現在 5 秒；11-18 在 5 秒時被 429）
- 每日報告分開列「暫時被擋（幾天後再試）」與「需人工」

### 段 3：原文寫明不提供就封存（ADR-114）

- `refresh`（每天更新申請期狀態的地方）：`offered = no` 的封存；不是 `no` 了、而且有還能申請的申請期，就照現在的規則喚回
- 封存後檢查頻率照 ADR-058（每 7 天），官網改口時最晚 7 天發現

### 段 4：候選積壓就暫停 agent（ADR-117）

- 還沒決定的候選（不含需人工的）超過 **50 個**（每週能決定的數量），逐校找與搜尋補漏先不跑；找新網址照跑（它修的是已加入的來源）
- 每日報告寫「候選積壓 N 個，agent 暫停」

### 段 5：設定頁「待你確認」（ADR-115）

- 條件：AI 判斷「不是獎學金」、但引用沒核對過（`not_scholarship = true` 且核對不是 supported），而且你沒按過保留
- 每一個顯示：來源名稱、連結、AI 的理由、引用、[停用] [保留]
- 停用：和 ADR-107 A2 的自動停用一樣（停用來源、封存獎學金）；保留：記在 `sources.review_note`，同一個來源之後不再列出
- API：`GET /api/settings/review`、`POST /api/settings/review/{source_id}`（`action: disable | keep`）

### 段 6：官網連結指向第一個申請頁（ADR-113）

- 資料表：`sources` 加 `picked_urls`（AI 挑的子頁，照挑的順序）
- 抓取：每次挑完就存下來
- 存獎學金時：來源是目錄來的、而且有挑到子頁 → 官網連結用第一個；其他照舊用來源網址
- 現有資料：對目錄來的來源重新挑一次（`fetch --repick`），每個一次便宜的 AI 呼叫
- 網頁：連結旁邊寫出連到哪一頁（例如「官網：multicom-em.eu/admission-criteria」），讓你看得出不是首頁

### 段 7：抽取改版（ADR-112、119）

**schema 加兩個欄位（取代 `requires_admission`）**

| 欄位 | 值 | 畫面上的意思 |
| --- | --- | --- |
| `how_to_apply` | `separate` | 另外申請獎學金，不用先錄取 |
| | `after_offer` | 先拿到入學許可，再另外申請獎學金 |
| | `with_admission` | 和入學申請一起送，不用另外申請獎學金 |
| | `automatic` | 不用申請，符合條件就自動給 |
| | `after_enrolment` | 入學後才申請（例如依第一年成績） |
| | `unclear` | 官網沒寫怎麼申請 |
| `how_to_apply_evidence` | 原文逐字引用 | 程式核對引用真的在原文裡 |
| `no_date_reason` | `not_announced`／`rolling`／`elsewhere`／`none` | 沒有截止日時，原文怎麼說（還沒公布／隨時可申請／說在別的網頁／完全沒提） |
| `no_date_evidence` | 原文逐字引用 | 同上 |

**沒有申請期的原因：由程式決定（不是 AI 直接給）**

依序判斷，第一個符合的就是原因：

| 順序 | 條件 | 原因代碼 | 網頁上寫 |
| --- | --- | --- | --- |
| 1 | `offered = no` | — | 封存（段 3） |
| 2 | 來源最近 10 天抓不到 | `unreachable` | 官網最近抓不到，資料停在 YYYY-MM-DD |
| 3 | `how_to_apply` 是 `automatic` 或 `after_enrolment` | `no_application` | 不用另外申請：<原文的意思> |
| 4 | `how_to_apply = with_admission`，頁面有入學截止日 | — | 入學截止日就是獎學金截止日：建申請期（不再算「只有入學」） |
| 5 | `how_to_apply = with_admission`，頁面沒有入學截止日 | `admission_date_elsewhere` | 跟著入學申請一起審，入學截止日官網這幾頁沒寫 |
| 6 | 有獎學金窗口、只有開放日或「即將開放」 | `not_announced` | 下一屆的截止日還沒公布（YYYY-MM-DD 開放） |
| 7 | 有獎學金窗口、只寫到月份 | `month_only` | 官網寫 2026 年 10 月截止，沒寫哪一天 |
| 8 | `no_date_reason = rolling` | `rolling` | 隨時可以申請，額滿為止 |
| 9 | `no_date_reason = elsewhere` | `elsewhere` | 官網說日期在另一頁：<連結或原文> |
| 10 | 其他 | `not_found` | 我們抓的 N 個網頁都沒寫截止日：<列出網頁> |

存在 `scholarships.no_date_reason`（代碼）與 `extracted.no_date`（細節與引用）。月份那種**不建假的申請期**，所以不會有截止提醒；畫面照實寫。

**地區名額存成類別（ADR-112）**

- 提示詞：「同一個獎學金另外保留給某些地區或國家的名額，寫進 categories（名稱、名額、適用國家），不要列在 other_scholarships」
- 國家群組（ADR-109）加 Erasmus+ 的地區：Sub-Saharan Africa、Latin America、Asia、Central Asia、Neighbourhood South、Middle East、Pacific、Caribbean、Western Balkans。清單照 Erasmus+ Programme Guide 的 eligible countries，附出處與查證日期
- 重抽後，舊的地區筆在頁面上不再是「其他獎學金」，現有的 `archive_gone` 會封存它們

**拆出來的那筆怎麼認（A2）**

- 給 AI 的「列出同一頁其他獎學金」提示詞附上這個來源現有的名稱清單，請它沿用同一個名稱
- 程式比對前去掉通用字（scholarship(s)、top up、grant(s)、award(s)），再算相似度（門檻照舊 0.9）

**漏抽偵測（擴充 ADR-111）**

- 程式在原文找「截止」字樣（deadline、apply by、application period、applications close…）旁邊 150 字內的日期
- 找到日期、但抽取沒有任何獎學金或入學窗口 → 算一個沒過的欄位，丟回 AI 重抽，錯誤訊息附那句原文
- 誤判（例如「last update = 10/30/2025」）會多一次 AI 呼叫，但不會改壞資料（重抽比較好才採用）

**子頁重挑**

- 現在只在首頁內容變了才挑。改成：首頁變了，**或**上次抽取沒有任何日期，就重挑（每個來源最多每 30 天一次，避免每天花錢）
- 一次性：對 13 個從頭到尾只抓過首頁的來源重挑

**提示詞版本**：extract-18、focus-2、outline-13、section-17、retry-2（每個改了的都升版，CLAUDE.md 規範）

### 段 8：全部重抽

- 先備份資料庫（和 11-14、11-17 一樣）
- 先試 10 個來源（MULTICOM、IMSOGLO、BIOPHAM、Chevening、WOCC、meta4.0、Laurea、Coventry、Hope、Copernicus），看結果對不對，再決定要不要全部重抽
- 全部：已加入、啟用中的來源約 270 個，`extract --force --max-cost 200`
- 量效果：沒有申請期的 99 筆，各種原因各剩幾筆；用 11-17 的 158 筆重新檢查，截止日、國籍、金額的正確率不能比 11-17 差

### 段 9：網頁標示改寫

原則：**標示要說「這代表什麼、你要做什麼」；正常的狀態不標。**

| 現在 | 問題 | 改成 |
| --- | --- | --- |
| 要先錄取：要（194 筆）／原文沒說（65 筆） | 從來沒有「不用」，看不出要做什麼 | 申請方式：和入學申請一起送，不用另外申請獎學金（等，見段 7 的表） |
| 已核對（徽章） | 內部流程，正常的不用標 | 不顯示 |
| 引用不支持／引用不在原文／沒附引用／沒抽到 | 內部核對用語 | 統一成「AI 讀的結果和官網原文對不上，請看下面的原文」，原文預設展開 |
| 年份推估 | 不知道是誰推的、可不可信 | 官網沒寫年份，依日期推算是 2027 年 |
| 日期不齊全 | 不知道缺什麼 | 依段 7 的原因寫，例如「官網寫 2026 年 10 月截止，沒寫哪一天」 |
| 原文沒有截止日 | 沒說為什麼 | 依段 7 的原因寫 |
| 時間待確認：沒有可用的申請日期（列表分組） | 不知道為什麼 | 分組保留，卡片上那一行寫原因（例如「不用另外申請」） |
| 上限 80 | 評分的內部機制 | 因為國籍（或其他條件）還不確定，分數最多算到 80 |
| 其他時程（不是申請獎學金的日期）／只有入學申請 | 讀起來像「只有入學、沒有獎學金」 | 學校的其他日期（入學申請、繳費等），不是獎學金的截止日 |
| 申請獎學金／自費／不限（申請期那一行） | 看不出是在說誰 | 給申請獎學金的人／給自費生；「不限」不顯示 |
| 列出的國家以外都可以（27 國） | 要自己數是哪 27 國 | 除了歐盟等 27 國，其他國籍都可以（點開看清單） |
| 學位不在引用裡、名額不在原文、類別名稱不在原文 | 內部核對用語 | 官網原文沒寫到「碩士」，可能不能讀；官網沒寫名額 |
| 依 EACEA 目錄頁 | 縮寫 | 依歐盟 Erasmus Mundus 目錄 |
| 資料過舊 | 不知道多舊 | 最近一次截止日在兩年前，官網可能沒更新 |
| 金額的「數字不在引用裡」「期間和引用不合」「幣別代碼不對」 | 內部核對用語 | 統一成「AI 讀的金額和官網原文對不上，請看原文」 |

這一段屬於 ADR-106（體驗類由 Claude 決定），但因為你提出來，所以列給你看；改完截圖給你看（不截評分理由與個人資料）。

### 段 10：清理資料

要你另外同意才做（刪除不能復原）：已封存且標成 `gone` 的拆出資料（段 8 之後重算數量）、測試資料 #1。舊快照與備份留多久，到時候另外問。

## 3. 不在範圍內

- ADR-118 搬機器（等你選機器）
- 評分規則不改：沒有申請期的獎學金，時間判斷照舊是「待確認」，只是理由寫清楚
- 第二層子頁（例如 Copernicus 的 `/calls/`）不追：段 7 的重挑只挑首頁的連結；追第二層等段 8 量完再看還剩幾筆
- 舊快照與備份的保留規則
- C2 的國籍「核對沒過」約 60 筆：段 8 重抽後重新算，再決定要不要另外處理
- C5 中文名稱、C6 屆別格式：段 9 之後另外做（不影響這次的決定）

## 4. 測試對象

| 行為 | 測試檔 |
| --- | --- |
| 排除來源時封存獎學金；列表不列沒加入的來源 | `tests/test_candidates_db.py`、`tests/test_list_archived_db.py` |
| 去重代表先選使用中的 | `tests/test_dedup.py` |
| 目錄的網址正規化後比對 | `tests/test_catalogue_move_db.py` |
| AI 補的年份不在引用裡 → 程式推算 | `tests/test_save_cycles_db.py` |
| 已封存的不重新評分 | `tests/test_scoring.py`（新增 db 測試） |
| 原文沒變的欄位不記變更 | `tests/test_changes.py` |
| 429 七天、403 三十天、robots 與 captcha 不再試 | `tests/test_pipeline_due.py`、`tests/test_fetch_gone.py` |
| 翻頁來源每頁間隔 15 秒 | `tests/test_ratelimit.py` |
| offered=no 封存、改口喚回 | `tests/test_cycles.py` |
| 候選超過 50 個就不跑逐校找與搜尋補漏 | `tests/test_discovery_run_db.py` |
| 待你確認清單、停用、保留 | `tests/test_settings_api.py` |
| 挑的子頁存順序；官網連結用第一個 | `tests/test_links.py`、`tests/test_extract_build.py` |
| 申請方式欄位與引用核對 | `tests/test_schemas.py`、`tests/test_verify.py` |
| 沒有申請期的原因（10 種順序） | 新增 `tests/test_no_date.py` |
| 漏抽偵測 | `tests/test_retry.py` |
| 地區群組展開 | `tests/test_groups.py` |
| 拆出來那筆的名稱比對 | `tests/test_multi_scholarship_db.py` |
| 首頁沒變但沒有日期時重挑子頁 | `tests/test_fetch_seen_db.py` |
| 提示詞升版 | `tests/test_prompts.py` |

## 5. 檢查表

所有指令在 `backend/` 執行；完整檢查是 `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`。

### 段 1：bug
- [ ] 排除來源時封存它的獎學金 -> verify: `uv run pytest tests/test_candidates_db.py -k archive`
- [ ] 列表與評分只看已加入且啟用的來源 -> verify: `uv run pytest tests/test_list_archived_db.py -k source_status`
- [ ] 現有 65 筆：重新整理後不在列表上 -> verify: SQL 數「列表上來自沒加入來源的筆數」，貼上 0
- [ ] 去重代表先選使用中的 -> verify: `uv run pytest tests/test_dedup.py -k active`
- [ ] 目錄網址正規化後比對 -> verify: `uv run pytest tests/test_catalogue_move_db.py -k normalize`
- [ ] 6 組重複來源各停用一個 -> verify: SQL 列出 6 組，貼上各組的啟用狀態
- [ ] AI 補的年份不在引用裡改用程式推算 -> verify: `uv run pytest tests/test_save_cycles_db.py -k year_not_in_quote`
- [ ] 已封存的不重新評分 -> verify: `uv run pytest tests/test_scoring.py -k archived`
- [ ] 原文沒變的欄位不記變更 -> verify: `uv run pytest tests/test_changes.py -k unchanged_source`
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`

### 段 2：被擋再試
- [ ] 429 七天後再試、有 Retry-After 照它 -> verify: `uv run pytest tests/test_pipeline_due.py -k blocked_429`
- [ ] 403 三十天後再試 -> verify: `uv run pytest tests/test_pipeline_due.py -k blocked_403`
- [ ] robots.txt、captcha 照舊需人工 -> verify: `uv run pytest tests/test_pipeline_due.py -k manual`
- [ ] 再試成功就清掉標記 -> verify: `uv run pytest tests/test_fetch_gone.py -k unblocked`
- [ ] 翻頁來源每頁間隔 15 秒 -> verify: `uv run pytest tests/test_ratelimit.py -k pagination`
- [ ] 遷移：現有 429、403 的標記改成再試 -> verify: `uv run alembic upgrade head`，SQL 貼上各原因的數量
- [ ] 每日報告分開列 -> verify: `uv run pytest tests/test_pipeline_messages.py -k blocked`
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`

### 段 3：不提供就封存
- [ ] offered=no 封存 -> verify: `uv run pytest tests/test_cycles.py -k not_offered`
- [ ] 不再是 no 而且有開放中的申請期就喚回 -> verify: `uv run pytest tests/test_cycles.py -k recall_offered`
- [ ] 現有 26 筆封存 -> verify: 跑一次 `refresh`，SQL 貼上使用中且 offered=no 的筆數 0
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`

### 段 4：積壓暫停
- [ ] 候選超過 50 個不跑逐校找與搜尋補漏 -> verify: `uv run pytest tests/test_discovery_run_db.py -k backlog`
- [ ] 找新網址照跑 -> verify: `uv run pytest tests/test_discovery_run_db.py -k new_url_runs`
- [ ] 每日報告寫出暫停 -> verify: `uv run pytest tests/test_pipeline_messages.py -k backlog`
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`

### 段 5：待你確認
- [ ] 列出判斷不是獎學金但沒核對過的 -> verify: `uv run pytest tests/test_settings_api.py -k review_list`
- [ ] 停用 -> verify: `uv run pytest tests/test_settings_api.py -k review_disable`
- [ ] 保留後不再列出 -> verify: `uv run pytest tests/test_settings_api.py -k review_keep`
- [ ] 網頁 -> verify: `npm run gen:api && npm run build`，打開設定頁看到清單（不按停用或保留）
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`

### 段 6：官網連結
- [ ] 挑的子頁照順序存下來 -> verify: `uv run pytest tests/test_links.py -k picked_order`
- [ ] 目錄來的用第一個子頁、其他用來源網址 -> verify: `uv run pytest tests/test_extract_build.py -k official_url`
- [ ] 遷移 `sources.picked_urls` -> verify: `uv run alembic upgrade head`
- [ ] 目錄來的來源重新挑一次 -> verify: `fetch --repick`，SQL 貼上有 picked_urls 的來源數與首頁連結的數量（原本 184）
- [ ] 網頁寫出連到哪一頁 -> verify: `npm run build`，打開 MULTICOM 的詳細頁截圖
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app && cd ../frontend && npm run build`

### 段 7：抽取改版
- [ ] schema 加申請方式與沒有日期的原因 -> verify: `uv run pytest tests/test_schemas.py -k how_to_apply`
- [ ] 申請方式的引用核對 -> verify: `uv run pytest tests/test_verify.py -k how_to_apply`
- [ ] 沒有申請期的原因，10 種的順序 -> verify: `uv run pytest tests/test_no_date.py`
- [ ] 和入學一起審、頁面有入學截止日 → 建申請期 -> verify: `uv run pytest tests/test_save_cycles_db.py -k with_admission`
- [ ] 遷移：加 `how_to_apply`、`no_date_reason`，拿掉 `requires_admission` -> verify: 讀過自動產生的遷移，`uv run alembic upgrade head`
- [ ] 地區群組展開 -> verify: `uv run pytest tests/test_groups.py -k erasmus_regions`
- [ ] 地區名額寫進類別、不拆筆（提示詞） -> verify: `uv run pytest tests/test_prompts.py`
- [ ] 拆出來那筆的名稱比對去掉通用字 -> verify: `uv run pytest tests/test_multi_scholarship_db.py -k generic_words`
- [ ] 漏抽偵測丟回重抽 -> verify: `uv run pytest tests/test_retry.py -k missed_date`
- [ ] 首頁沒變但沒有日期時重挑（30 天一次） -> verify: `uv run pytest tests/test_fetch_seen_db.py -k repick_no_date`
- [ ] 提示詞升版 -> verify: `uv run pytest tests/test_prompts.py`
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`

### 段 8：重抽
- [ ] 備份資料庫 -> verify: 貼上備份檔名與大小
- [ ] 先試 10 個來源 -> verify: `extract --force --source …（10 個） --max-cost 10`，貼上每筆的申請方式、沒有日期的原因、MULTICOM 的筆數與類別
- [ ] 你看過試跑的結果，同意再全部重抽 -> verify: 你的回覆
- [ ] 全部重抽 -> verify: `extract --force --max-cost 200`，貼上完成／失敗數與費用
- [ ] 沒有申請期的原因各剩幾筆 -> verify: SQL 依 `no_date_reason` 分組，貼上
- [ ] 重新檢查 11-17 的 158 筆 -> verify: 數字寫進 `docs/eval/`，和 11-17 比較
- [ ] 學習卡、`docs/progress.md` -> verify: 檔案已更新

### 段 9：標示
- [ ] 第 2 節段 9 的表全部改完 -> verify: `npm run build`；`grep` 確認畫面上不再出現「要先錄取」「引用不支持」「年份推估」「上限 80」
- [ ] 詳細頁與列表截圖（不含評分理由與個人資料） -> verify: 截圖給你看
- [ ] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app && cd ../frontend && npm run build`

### 段 10：清理
- [ ] 列出要刪的資料與數量，等你同意 -> verify: 你的回覆
- [ ] 刪除 -> verify: SQL 貼上刪除前後的數量

## 6. 費用

| 段 | 估計 | 依據 |
| --- | --- | --- |
| 6 重新挑子頁 | 約 NT$5 | 這個月「找子頁」285 次 US$0.20 |
| 8 試 10 個來源 | 約 NT$5 | 11-14 全部重抽 249 個來源 NT$73.7 |
| 8 全部重抽 | 約 NT$100–150，上限 NT$200 | 同上，加上拆筆與重試；11-17 那輪 NT$268 含好幾次補抽 |

這個月目前約 US$21.5（約 NT$690），上限 NT$7,000。

## 7. Claude 自行決定（小問題，請事後檢查）

1. 候選積壓的上限 50 個（等於每週能決定的數量）
2. 翻頁來源每頁間隔 15 秒（11-18 在 5 秒時被 429）
3. 429 有 Retry-After 就照它，但至少 1 天、最多 7 天
4. 沒有日期時重挑子頁，每個來源最多每 30 天一次
5. 漏抽偵測：「截止」字樣前後 150 字內有日期才算
6. 拆出來那筆比對時去掉的通用字：scholarship(s)、top up、grant(s)、award(s)
7. 段 8 先試的 10 個來源（每一種原因至少一個）
8. 列表上「時間待確認」的分組保留，原因寫在卡片上（不另外加分組）
