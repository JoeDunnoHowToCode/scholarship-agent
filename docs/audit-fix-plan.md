# 總檢查的修正：實作計畫（2026-11-18）

狀態：**你 11-19 核准；段 1–5、段 7 完成，段 6 的程式完成；段 8 全部重抽完成（11-20，NT$152.5）、重新檢查完成（11-21）；類別地區代號寫反已修（ADR-120）；段 9 標示改寫完成（11-21）。剩段 6 的資料步驟、段 10（刪除要你同意）**。

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
| A6 被排除的來源還在列表 | 排除只改來源；列表不看來源狀態 | 每天的 `refresh` 把「來源不是已加入且啟用」的獎學金封存，不喚回、不預估下一屆（11-19 改設計，見下面） | `scholarships/cycles.py` 的 `refresh` |
| A4 使用中的被標成封存那筆的重複 | 每組由最小的 id 當代表 | 先選使用中的，再選最小的 id | `scholarships/dedup.py` 的 `find_duplicates` |
| A3 同一個網站兩個來源 | 用網址字串比對 | 新增目錄學程前先正規化網址（`dedup.normalize_url`）再比對 | `sources/catalogue.py` 的 `upsert_programme` |
| C1 第 4 種 AI 補的年份被丟掉 | 年份不在引用裡就整筆不建 | 年份不在引用裡、但月日都在：丟掉 AI 的年份，改用程式推算（ADR-110），標「年份是推算的」 | `scholarships/extract.py` 的 `save_cycles` |
| D5 已封存的也每輪評分 | 評分只排除重複的 | 已封存的沿用上次的分數，不送 AI | `matching/score.py` |
| D5 重抽造成的變更紀錄 | 抽出來的文字不同就記一筆 | 套用和通知一樣的關卡（ADR-064）：官網原文沒變的欄位不記 | `scholarships/changes.py` |

邊界情況：
- A6：被排除的來源之後又被加入（例如你在設定頁打開），獎學金要喚回。用現有的 `refresh` 喚回規則。
- A6 改設計（11-19，寫測試時發現）：原本打算「排除時封存＋列表過濾來源狀態」。但只在排除時封存擋不住：隔天的 `refresh` 看到還有開放中的申請期，會把它喚回。改成全部交給 `refresh`：它每天跑，也涵蓋在設定頁停用、還沒決定的候選。列表本來就不列封存的，評分由 D5 處理，所以列表與評分不必另外過濾。代價：被排除到當天收尾之間（幾小時）還看得到。
- A3：現有的 6 組重複來源，程式修好後各停用一個（留還有使用中獎學金的那個）。**停用是改資料，核准這份計畫就算同意**；停用可以在設定頁恢復。

### 段 2：被擋的來源自動再試（ADR-116）

```
被擋 → 原因是什麼？
   ├─ 429 → 記下被擋的日期，7 天後再試（伺服器有給 Retry-After 就照它，但至少 1 天）
   ├─ 403 → 記下被擋的日期，30 天後再試
   └─ robots.txt 禁止、captcha → 和現在一樣標需人工，不再試
再試成功 → 清掉標記，回到每天檢查
```

- 資料表：`sources` 加 `retry_on`（哪天再試，台灣日期；空白代表等你處理），原因照舊放 `manual_reason`（11-19 實作時改：一個欄位就夠，排程只需要知道哪天再試）。現有 34 個標記，429 與 403 的遷移成「從 11-18 起算再試」
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
- [x] refresh 封存「來源不是已加入且啟用」的獎學金 -> verify: `uv run pytest tests/test_refresh_db.py`（red 7e6ca2c、green efbaa01）
  ```
  .                                                                        [100%]
  1 passed in 0.34s
  ```
- [ ] 現有 65 筆：重新整理後不在列表上 -> verify: SQL 數「列表上來自沒加入來源的筆數」，貼上 0
- [x] 去重代表先選使用中的 -> verify: `uv run pytest tests/test_dedup.py -k active`（red 180b438、green 18f3b41）
  ```
  ......                                                                   [100%]
  6 passed in 0.16s
  ```
  （跑的是 `tests/test_dedup.py tests/test_duplicates.py` 全部，含新測試）
- [x] 目錄網址正規化後比對 -> verify: `uv run pytest tests/test_catalogue_move_db.py tests/test_catalogue.py`（測試名稱是 `same_site`，不是計畫原本寫的 `normalize`；red a1dfa23、green e667803）
  ```
  .........                                                                [100%]
  9 passed in 0.42s
  ```
- [x] 6 組重複來源各停用一個 -> verify: SQL 列出 6 組，貼上各組的啟用狀態（11-19 06:25 台北時間；每組留下有使用中獎學金的那個）
  ```
   10344 | https://www.fipdes.eu/                         | f | 和來源 #83 是同一個網站
   10343 | https://www.infectious-diseases-one-health.eu/ | f | 和來源 #75 是同一個網站
    4156 | https://master-cne.eu/                         | f | 和來源 #144 是同一個網站
     136 | https://master-strains.eu/                     | f | 和來源 #10345 是同一個網站
    4158 | https://merconsortium.eu/                      | f | 和來源 #78 是同一個網站
   10482 | https://www.quanteem.eu/                       | f | 和來源 #204 是同一個網站
  （83、75、144、10345、78、204 都是 t）
  ```
- [x] AI 補的年份不在引用裡改用程式推算 -> verify: `uv run pytest tests/test_save_cycles_db.py tests/test_extract_build.py tests/test_rules_recheck_db.py`（測試名稱是 `a_year_the_ai_added`；red e5aebb2、green ac5f5cc；現有的 WOCC 那筆等段 8 重抽才套用，現在重建全部申請期會和正在跑的每日檢查搶資料）
  ```
  ..............                                                           [100%]
  14 passed in 0.53s
  ```
- [x] 已封存的不重新評分 -> verify: `uv run pytest tests/test_score_archived_db.py tests/test_matching_score.py tests/test_scoring.py tests/test_matching_checks.py`（新測試檔 `test_score_archived_db.py`：評分每筆都 commit，用 savepoint 包住才不會動到真的評分；red 5c06ee0、green d310664）
  ```
  ................                                                         [100%]
  16 passed in 1.85s
  ```
- [x] ~~原文沒變的欄位不記變更~~ **取消（11-19）**：查證後發現詳細頁的「變更紀錄」（`NOTIFIED_FIELDS`）和通知都只用截止日、國籍範圍、國家、學位這 4 個欄位，它們本來就有 ADR-064 的原文核對；雜訊（2,895 筆）全在其他欄位，只存在資料表裡，你看不到。要不要清掉這些列，併到段 10 問你。總檢查 D5 的說法已更正
- [x] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
  ```
  400 passed, 1 warning in 5.30s
  All checks passed!
  Success: no issues found in 126 source files
  ```

### 段 2：被擋再試
測試檔和計畫原本寫的不同：規則與抓取器放在新的 `tests/test_blocked.py`（不碰資料庫），記錄、排程、恢復、報告查詢放在新的 `tests/test_blocked_db.py`。設計細節的改變：不另外加 `blocked_at`，改成一個欄位 `sources.retry_on`（哪天再試），被擋的原因照舊放 `manual_reason`。

- [x] 429 七天後再試、有 Retry-After 照它（至少 1 天、最多 7 天）；403 三十天；robots.txt、captcha 不再試 -> verify: `uv run pytest tests/test_blocked.py`（red 3c33ca5／f1fab63／fb82017、green 9c3fd2b／3fc874d／d73b521）
  ```
  15 passed in 0.35s
  ```
  （這個檔也含下面的「還沒到期就不抓」與「翻頁間隔」）
- [x] 被擋時記下再試日期；到期才排進每日檢查；再試沒被擋就清掉標記；報告只列這一輪被擋的 -> verify: `uv run pytest tests/test_blocked_db.py`（red cc14840／d7e3816／754c0ae／d596292、green 2792e52／e034147／43a7173／0bb4cd9）
  ```
  4 passed in 0.82s
  ```
- [x] `process_source` 不再跳過到期的來源（`still_blocked`） -> verify: 同上 `tests/test_blocked.py`（red e0bc09a、green d0bedae）
- [x] 翻頁來源每頁間隔 15 秒 -> verify: 同上 `tests/test_blocked.py`（red 314a35b、green 230eeaa）
- [x] 遷移：現有 429、403 的標記改成再試 -> verify: `uv run alembic upgrade head`，SQL 貼上各原因的數量（54b7628；自動產生的部分只有加欄位，讀過再套用）
  ```
    manual_reason  |  retry_on  | count
   403             | 2026-12-18 |    22
   429             | 2026-11-25 |     5
   robots.txt 禁止 |            |     4
   captcha         |            |     3
  ```
- [x] 每日報告分開列 -> verify: `uv run pytest tests/test_pipeline_messages.py -k separates`（red 299fd3d、green 09d348b）
  ```
  1 passed, 12 deselected in 0.01s
  ```
- [x] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
  ```
  420 passed, 1 warning in 5.52s
  All checks passed!
  Success: no issues found in 126 source files
  ```

### 段 3：不提供就封存
- [x] offered=no 封存 -> verify: `uv run pytest tests/test_refresh_db.py`（測試放在 A6 的同一個檔；red 046d3fa、green 951c723）
  ```
  2 passed in 0.42s
  ```
- [x] 不再是 no 而且有開放中的申請期就喚回 -> 不另寫測試：`save_cycles` 建出開放中的申請期時會改回使用中，`refresh` 原本的喚回規則也照舊；新測試寫了會第一次就通過，證明不了什麼
- [ ] 現有 26 筆封存 -> verify: 今天這輪收尾跑 `refresh` 之後，SQL 貼上使用中且 offered=no 的筆數 0（11-19 06:38 還在跑：使用中 offered=no 26 筆、來自不在每日檢查裡的來源 103 筆）
- [x] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
  ```
  421 passed, 1 warning in 5.31s
  All checks passed!
  Success: no issues found in 126 source files
  ```

### 段 4：積壓暫停
- [x] 候選超過 50 個就暫停（`discovery_paused`） -> verify: `uv run pytest tests/test_discovery_run_db.py -k pauses`（red e31d92b、green f1b040f）
  ```
  1 passed, 7 deselected in 0.41s
  ```
- [x] 找新網址照跑 -> 沒有測試：`discover_today` 暫停時只把學校清空、搜尋設成不跑，找新網址的清單照原樣傳進去（f1b040f 的 diff）。`discover_today` 是背景工作，目前沒有它的測試
- [x] 每日報告寫出暫停 -> verify: `uv run pytest tests/test_pipeline_messages.py -k backlog`（red 95396fb、green d81e35b）
  ```
  1 passed, 13 deselected in 0.02s
  ```
- [x] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app`
  ```
  423 passed, 1 warning in 5.87s
  All checks passed!
  Success: no issues found in 126 source files
  ```

### 段 5：待你確認
- [x] 列出判斷不是獎學金但沒核對過的；停用；保留後不再列出 -> verify: `uv run pytest tests/test_settings_api.py -k "wait_for_you or disable_a_source or keep"`（測試名稱和計畫原本寫的不同；red 856073e／2cf1dbc／d57de74、green 63b00de／657d68e／508b0b4）
  ```
  3 passed, 9 deselected in 0.67s
  ```
- [x] 網頁 -> verify: `npm run gen:api && npm run build`，打開設定頁看到清單（不按停用或保留；e753494）。8000 埠被別的程式占用，改用預覽伺服器的 8001（新的 API 加上剛建置的網頁）。console 沒有錯誤，三個 API 都回 200；清單列出 4 個來源：NANOMED、IMSOGLO、Mbuild、Master of Fine Arts（另外 3 個在已排除的來源上，A6 會封存）
- [x] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app && cd ../frontend && npm run build`
  ```
  426 passed, 1 warning in 5.66s
  All checks passed!
  Success: no issues found in 126 source files
  ✓ built in 246ms
  ```

### 段 6：官網連結
- [x] 挑的子頁照順序存下來；目錄來的用第一個子頁、其他用來源網址 -> verify: `uv run pytest tests/test_picked_pages_db.py`（新測試檔，快照寫到暫存資料夾；red e4f2857／2392aa8、green 34c9c1f／73b84f9）
  ```
  2 passed in 0.58s
  ```
- [x] 遷移 `sources.picked_urls` -> verify: `uv run alembic upgrade head`（d3c9937；自動產生的只有加欄位，預設空清單；400 個來源都是空的）
- [ ] 目錄來的來源重新挑一次 -> verify: `fetch --repick`，SQL 貼上有 picked_urls 的來源數與首頁連結的數量（原本 184）。**等今天這輪每日檢查跑完再做**（11-19 06:48 還在跑；重挑會抓 200 多個網站的子頁，和每日檢查一起跑等於同一個網站被抓兩次）
- [ ] 現有獎學金的連結補成第一個子頁 -> verify: SQL 補值，貼上前後的首頁連結數。**新加的一步**：`save()` 只在重抽時更新連結，重挑後如果子頁內容沒變就不會重抽，所以要直接補值
- [x] 網頁寫出連到哪一頁 -> verify: `npm run build`，打開 MULTICOM 的詳細頁（0afbee4）。按鈕下面顯示 `multicom-em.eu`（還沒重挑，所以是首頁）；console 沒有錯誤。沒有截圖：詳細頁上有評分，改用文字確認
- [x] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app && cd ../frontend && npm run build`
  ```
  428 passed, 1 warning in 5.30s
  All checks passed!
  Success: no issues found in 126 source files
  ✓ built in 233ms
  ```

### 段 7：抽取改版

實作時改了三處設計（11-20），也記在「Claude 自行決定」：
- `requires_admission` 先不拿掉：網頁還在用，段 9 改標示時一起拿掉
- 「給 AI 現有名稱清單」沒做：改用程式比對前去掉通用字（A2），不用改提示詞的變數
- 地區名額的國籍放在抽取結果的類別裡（`nationality_groups`），評分本來就從那裡讀類別，不必改 `scholarship_categories` 資料表

查官方清單時發現：Erasmus+ 把台灣、日本、南韓列在「Region 5: Asia」的高所得國家與地區，不是另外一區。地區名額不一定給高所得的部分，所以評分算「待確認」並寫明原因。

- [x] schema 加申請方式與沒有日期時原文怎麼說；申請方式的引用核對 -> verify: `uv run pytest tests/test_verify.py -k how_to_apply`（red d5ea324、green 4ede978）
  ```
  1 passed, 8 deselected in 0.04s
  ```
- [x] 沒有申請期的原因，10 種的順序 -> verify: `uv run pytest tests/test_no_date.py`（red 4ee9740、green 906f78d）
  ```
  13 passed in 0.26s
  ```
- [x] refresh 存下原因；抽取存下申請方式 -> verify: `uv run pytest tests/test_no_date_db.py`（red c6c2700、green e462bf0／664ab4c）
  ```
  2 passed in 1.21s
  ```
- [x] 和入學一起審、頁面有入學截止日 → 建申請期 -> verify: `uv run pytest tests/test_save_cycles_db.py -k admission_deadline`（red 9326863、green 39cf092）
  ```
  1 passed, 3 deselected in 0.81s
  ```
- [x] 遷移：加 `scholarships.how_to_apply`、`no_date_reason`、`sources.picked_at` -> verify: 手寫遷移、先套用再改資料表類別，`uv run alembic check` 沒有差異（afb9ee3、0eae026）
- [x] 地區群組展開 -> verify: `uv run pytest tests/test_groups.py -k regions`（清單照 Erasmus+ 官方頁 2026-11-20 查證；red 7137dd0、green 3cc40e4）
  ```
  1 passed, 3 deselected in 0.02s
  ```
- [x] 地區名額類別用自己的地區評分（新加的一項） -> verify: `uv run pytest tests/test_matching_score.py -k regional`（red 7f42650、green 7d18fbb）
  ```
  1 passed, 1 deselected in 0.66s
  ```
- [x] 拆出來那筆的名稱比對去掉通用字 -> verify: `uv run pytest tests/test_multi_scholarship_db.py -k generic`（red 88c240b、green c3ed0f1）
  ```
  1 passed, 7 deselected in 0.82s
  ```
- [x] 漏抽偵測丟回重抽 -> verify: `uv run pytest tests/test_rules.py -k deadline_sentence` 與 `tests/test_retry.py -k missed`（red 6ee09d9／2f75cb4、green 34fce7d／b33086b）
  ```
  1 passed, 10 deselected in 0.05s
  1 passed, 2 deselected in 0.78s
  ```
- [x] 首頁沒變但沒有日期時重挑（30 天一次） -> verify: `uv run pytest tests/test_picked_pages_db.py -k repicked`（red 95b4271、green d60aeea）
  ```
  1 passed, 2 deselected in 0.80s
  ```
- [x] 提示詞升版：extract-18（地區名額寫成類別、申請方式、沒有日期時原文怎麼說、地區代號）；outline、section、focus 沒改 -> verify: `uv run pytest tests/test_prompts.py`（feccec1）
  ```
  15 passed in 0.77s
  ```
- [x] 完整檢查並推上 main；CI -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app && cd ../frontend && npm run build`
  ```
  451 passed, 1 warning in 12.24s
  All checks passed!
  Success: no issues found in 126 source files
  ✓ built in 1.42s
  GitHub CI（feccec1）：backend success、frontend success，451 passed
  ```

### 段 8：重抽
- [x] 備份資料庫 -> verify: 貼上備份檔名與大小
  ```
  backend/data/backups/scholar-2026-11-20-before-audit-trial.dump（77 MB，19 張表的資料）
  ```
  （11-20 你等不及每日檢查收尾，選 A：先停背景程式，手動跑 refresh 與去重：列表 392 → 244 筆，來自排除來源 117 → 0、今年不提供 34 → 0、沒有申請期 202 → 77，Europhotonics #2771 回到列表；做完再開回背景程式。被中斷的工作只有來源 116 那一件）
- [x] 先試 10 個來源 -> verify: `extract --force --source …（10 個） --max-cost 10`，貼上每筆的申請方式、沒有日期的原因、MULTICOM 的筆數與類別（先重抓 9 個；meta4.0 被 403 擋，只用現有網頁）
  ```
  完成 10、沒變 0、失敗 0；約 NT$7.1（extract-18），另外重抽 MULTICOM、WOCC 約 NT$2.0（extract-19）
  MULTICOM：使用中 7 → 1 筆；類別 9 個（一般名額 15，地區名額各附地區代號：撒哈拉以南非洲、拉丁美洲、亞洲、中亞、南地中海、中東、太平洋＋加勒比海、西巴爾幹）
  IMSOGLO：重挑子頁抓到 2 頁，找到截止日 2027-02-28
  Laurea：截止日 2027-01-21；WOCC：2027-03-21
  BIOPHAM：with_admission，原因 admission_date_elsewhere
  Coventry、Hope：自動給的獎學金 → no_application
  Copernicus、meta4.0：not_found（日期在第二層子頁／網站擋 403）
  Chevening：month_only
  試跑抓到的錯：MULTICOM、WOCC 原文是「錄取者自動列入評選」，AI 標成 automatic、核對也放行 → 改成 extract-19（7be22de），重抽後兩筆都是 with_admission
  地區名額的名額取上限（「5-6」存成 6），沒有存範圍
  Liverpool Hope 的獎學金頁現在回 404
  ```
- [x] 你看過試跑的結果，同意再全部重抽 -> verify: 你的回覆
  ```
  11-20：「全部重抽」
  ```
- [x] 全部重抽 -> verify: `extract --force --max-cost 200`，貼上完成／失敗數與費用（先停背景程式、再備份 `scholar-2026-11-20-before-full-reextract.dump` 77 MB；只傳 237 個已加入、啟用中的來源，不帶 `--source` 會連排除的也抽；跑完接著 refresh、去重、開回背景程式）
  ```
  start Fri Nov 20 22:37:16 CST 2026
  完成 237、沒變 0、失敗 0
  tokens：輸入 6,325,294、輸出 1,147,636，約 US$4.767（NT$152.5）
  申請期：開放中 210、即將開放 51、已截止 115、預估 14
  這次封存 3 筆、喚回 0 筆、新增預估申請期 22 筆；資料過舊 4 筆
  688 筆獎學金，其中 17 筆是重複
  local.scholarship-agent.worker：執行中；local.scholarship-agent.cron：執行中
  end Fri Nov 20 23:46:09 CST 2026
  ```
  重抽寫了 31 筆變更紀錄，用通知的規則（`describe_change`）檢查，0 筆會變成通知
- [x] 沒有申請期的原因各剩幾筆 -> verify: SQL 依 `no_date_reason` 分組，貼上（列表＝使用中、不是重複、有來源）
  ```
  列表 239 筆（重抽前 244）；沒有申請期 70 筆（重抽前 77，總檢查時 99）
   (有申請期)               | 169
   not_found                |  33   AI 在抓到的網頁裡沒找到日期
   admission_date_elsewhere |  12   隨入學一起審，入學日期在別頁
   not_announced            |   8   還沒公布
   no_application           |   7   不用申請
   unreachable              |   4   網站擋住
   month_only               |   3   只寫月份
   elsewhere                |   3   原文說日期在別的地方
  地區名額拆成多筆：0（剩下 2 筆名字有 region 的是法國的地區獎學金，不是名額）；83 個類別附地區代號，分在 39 筆
  國籍待確認 60 筆（重抽前 55）
  ```
- [x] 申請方式有多少筆知道（新加的一項） -> verify: SQL 依核對結果與 `how_to_apply` 分組
  ```
   supported       | with_admission  |  99
   not_supported   | unclear         |  74
   (AI 填 unclear) | unclear         |  34
   supported       | separate        |  12
   supported       | automatic       |   9
   quote_not_found | unclear         |   6
   supported       | after_offer     |   3
   supported       | after_enrolment |   2
  ```
  知道的 125 筆（52%）。追查被核對擋下的 74 筆（只呼叫核對的 AI，不寫資料庫）：
  - 約 13 筆的引用寫「自動列入評選」（automatically considered、postulent d'office），核對的 AI 對「和入學一起申請」大多說支持，所以被擋是抽取的 AI 填了別的（多半是 automatic）。extract-19 的規則 AI 沒有每次照做
  - 其他約 60 筆的引用沒寫怎麼申請（例如「Candidates are eligible for an Erasmus Mundus scholarship」），擋下改成 unclear 是對的
  - 核對的 AI 不穩：同一句問兩次，16 筆裡有 3 筆答案不同
  - 抽取的 AI 原本填什麼沒有存下來（沒通過就改成 unclear），所以只能推測；之後要診斷，得先存下原本的值
- [x] 重新檢查 11-17 的 158 筆 -> verify: 數字寫進 `docs/eval/`，和 11-17 比較（`docs/eval/2026-11-21-audit.md`；判 141 筆，另外 17 筆的來源已排除、沒重抽）
  ```
  judged 141 / 141; in 11-17 too: 141
  deadlines       11-17   88/118=75%   11-21   86/108=80%
  nationality     11-17  118/139=85%   11-21  106/140=76%   （不算新的地區名額規則：106/124=85%）
  degrees         11-17  133/139=96%   11-21  136/139=98%
  amounts         11-17   66/112=59%   11-21   72/112=64%
  offered         11-17  121/141=86%   11-21  123/137=90%
  how_to_apply    11-17            -   11-21   50/102=49%
  no_date_reason  11-17            -   11-21    38/58=66%
  ```
  「不能比 11-17 差」：截止日、金額、學位、offered 都變好；國籍照舊規則算一樣（85%），掉的 16 筆是新規則（地區名額寫成類別）AI 沒做到
- [x] 隨入學一起審、原文說日期還沒公布 → 原因是「還沒公布」（重新檢查發現，新加的一項） -> verify: `uv run pytest tests/test_no_date.py`（red d1038ca、green 614ded3）
  ```
  16 passed in 5.48s（含 test_no_date_db.py）
  ```
- [x] 類別的地區代號寫反（重新檢查發現，段 7 造成的）：整筆排除歐盟，唯一的類別卻附 EU、EEA，評分把非歐盟的人判成不符合；列表 15 筆，14 筆今天已被判國籍不符。你選 A（ADR-120）：存檔時程式拿掉 -> verify: `uv run pytest tests/test_groups.py tests/test_extract_build.py`（red 2838058／c797a1c、green 2ea4ac8／6faa004）
  ```
  12 passed in 1.00s
  ```
- [x] 現有資料修正並重新評分 -> verify: 一次性腳本先試跑再套用，再試跑一次應該是 0；`python -m app.features.matching.score --max-cost 10`；SQL 數這 15 筆的國籍不符
  ```
  修正 20 筆（使用中 15、封存 5）；再試跑：會修正 0 筆
  評分 318 筆（領域契合：AI 沿用 318、重算 0、失敗 0）；NT$0.0
  nat_failed 0 / 15
  ```
  第一次試跑寫「會修正 360 筆」：舊資料的類別沒有地區代號欄位，腳本補了空清單也算改變。改成只動有地區代號的類別後是 20 筆
- [ ] 學習卡、`docs/progress.md` -> verify: 檔案已更新

### 段 9：標示
- [x] 沒有申請期的原因換成一句話 -> verify: `uv run pytest tests/test_no_date.py`（red cd71c09、green e0d47bb）
- [x] 申請期那一行與評分的時間原因用白話（年份推估、截止日未核對、原文沒有截止日、資料過舊的 ADR 編號） -> verify: `uv run pytest tests/test_notification_rules.py tests/test_matching_score.py`（red e515767、green 0427965；兩個現有斷言只改了期望的文字）
- [x] API 給申請方式、那一句話、國籍群組的中文名稱；不再給 `requires_admission`（欄位留到段 10） -> verify: `uv run pytest tests/test_scholarship_labels_db.py`（red c1e4567、green fe5a081）
- [x] 瀏覽器檢查時發現：「官網抓不到，資料停在 2026-11-20」寫的是重抽那天，其實最後抓到是 10 月 → 改用最後一次的快照日期；評分查不到快照，就不寫日期 -> verify: 同上兩個測試檔（red 610902f、green 26262ea）；#93 現在是「資料停在 2026-10-11」
- [x] 第 2 節段 9 的表全部改完 -> verify: `npm run build`；`grep` 確認畫面上不再出現「要先錄取」「引用不支持」「年份推估」「上限 80」（3e131ca）
  ```
  ✓ built in 474ms
  labels.ts:1、ScholarshipDetail.tsx:1（都是程式碼註解）；其他頁 0
  ```
  網頁另外發現兩處並修正：同一期申請期把「年份是推算的」寫了兩次；核對沒通過而改成 unclear 的申請方式原本寫「官網沒寫怎麼申請」，其實官網有寫，改成「AI 讀不出確定的申請方式」並展開原文
- [x] 重算原因與評分的文字 -> verify: `python -m app.features.scholarships.cycles`、`python -m app.features.matching.score --max-cost 5`，SQL 數使用中的獎學金還有舊文字的評分
  ```
  原因：admission_date_elsewhere 12 → 4、not_announced 8 → 16（11-21 修的順序）
  評分 318 筆，NT$0.0；使用中的舊文字 0 筆（封存的 259 筆照段 1 D5 沿用上次的分數，喚回時才會換）
  ```
- [x] 詳細頁與列表檢查（不含評分理由與個人資料） -> verify: 用 JavaScript 只讀標示文字；詳細頁截圖（ITU 的資格頁）；console 沒有錯誤
  ```
  列表 240 張卡片：有日期 173；其他每張都寫原因，例如「下一屆的截止日還沒公布」16、「官網這幾頁都沒寫截止日，請看官網」32
  #72 有申請期但沒有適合你的那一輪，原本寫「官網沒寫」，改成評分的時間原因
  ```
- [x] 完整檢查並推上 main -> verify: `set -o pipefail; uv run pytest && uv run ruff check . && uv run mypy app && cd ../frontend && npm run build`
  ```
  471 passed, 1 warning in 13.42s
  All checks passed!
  Success: no issues found in 126 source files
  ✓ built in 474ms
  ```

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
9. 被擋的來源只加一個欄位 `retry_on`（哪天再試），原因照舊放 `manual_reason`；計畫原本寫 `blocked_at`（11-19 段 2）
10. A6 改成只由每天的 `refresh` 封存，排除當下不另外封存（11-19 段 1，理由見第 2 節段 1 的邊界情況）
11. 地區名額裡高所得的國家與地區（例如台灣在亞洲）評分算待確認，不算符合（11-20 段 7）
12. 漏抽偵測只看頁面主角，不看同一頁拆出來的其他獎學金（它們的日期常是別人的）（11-20 段 7）
13. 段 9 的白話文字（11-21）：核對沒通過一律寫「AI 讀的結果和官網原文對不上，請看下面的原文」，金額寫「AI 讀的金額和官網原文對不上，請看原文」；通過的不標
14. 「截止日未核對」不在段 9 的表裡，但也是內部用語，一起改成「截止日要再看官網確認」
15. 國籍寫成群組時先寫群組名稱（「除了歐盟、歐洲經濟區」），國家清單超過 5 個或有群組時收起來
16. `requires_admission` 只是不再送到網頁；刪資料表欄位是刪資料，留到段 10 等你同意
17. 列表卡片沒有日期也沒有原因時（有申請期但不適合你），寫評分的時間原因
