# 第 10 天學習卡：網頁 UI/UX 修正（11-08）

每張卡分六段：問題、設計、概念、程式碼導讀、你可以怎麼講、自我檢查。計畫與驗證輸出在 `docs/ui-review.md`。

## 1. 篩選條件放在網址裡

**問題**：在列表打開「只看開放中的」（剩 56 筆），點進一筆再按上一頁，開關變回關閉，又是 191 筆。每看一筆就要重設一次篩選。

**設計**
- 篩選條件從 React 的 `useState` 改成網址參數：`/?open=1&degree=master`。畫面每次都從網址讀出篩選。
- 預設值不寫進網址，網址保持乾淨；改篩選時用 `replace`，不多留一筆瀏覽紀錄，上一頁會直接回到前一個頁面。
- 「← 回列表」：從列表點進來的就執行「上一頁」，這樣篩選和捲動位置都還在；直接打開網址的才連到首頁。
- 放棄的做法：存在 `localStorage`。重新整理保得住，但網址不能分享，而且開兩個分頁會互相蓋掉。

**概念**
- **狀態放在哪裡（state location）**：同一份資料可以放在元件裡、網址裡或瀏覽器儲存裡，放的位置決定它能活多久。例子：放在元件裡，離開頁面就消失；放在網址裡，上一頁、重新整理、分享都還在。
- **單一資料來源（single source of truth）**：篩選只存在一個地方（網址），畫面從那裡算出來，不會出現兩份資料不一致。

**程式碼導讀**
- `frontend/src/pages/ScholarshipList.tsx` 的 `filtersFrom`、`paramsFrom`：網址參數和篩選條件互相轉換。
- 同一檔的 `update`：`setParams(..., { replace: true })`。
- `frontend/src/pages/ScholarshipDetail.tsx` 的 `BackToList`：看 `location.state.fromList` 決定要「上一頁」還是連到首頁。

## 2. 整張卡片可點、換頁從頁首開始

**問題**：卡片能點的只有 18px 高的標題。點進詳細頁時，頁面停在列表的捲動位置（實測 1067px），看不到標題。

**設計**
- 第一版用「延伸連結」：標題連結的 `::after` 蓋住整張卡片。實測點內文沒有反應。原因是 `CardHeader` 有 `container-type`（CSS 容器查詢），它會變成 `::after` 定位的基準，`::after` 只蓋住標題那一塊。
- 改用卡片的 `onClick` 換頁。鍵盤和螢幕閱讀器仍然只用標題連結，Tab 經過一張卡片只停一次；正在選取文字時不換頁。
- 換頁捲動：新頁面（PUSH）捲到頁首；上一頁、下一頁（POP）不動，讓瀏覽器回到原本的位置。

**概念**
- **包含區塊（containing block）**：`position: absolute` 的元素，以最近的「定位祖先」為基準。`relative`、`transform`、`container-type` 都會產生這種祖先。例子：`CardHeader` 的容器查詢把 `::after` 關在標題裡。
- **導航類型（navigation type）**：PUSH 是點連結，POP 是上一頁或下一頁。例子：`App.tsx` 的 `ScrollToTop` 只在不是 POP 時捲到頁首。

**程式碼導讀**
- `frontend/src/pages/ScholarshipList.tsx` 的 `ScholarshipCard`：`onClick` 裡用 `navigate`；標題連結的 `stopPropagation` 避免換頁兩次。
- `frontend/src/App.tsx` 的 `ScrollToTop`。

## 3. 詳細頁：頁首摘要、頁籤、主要按鈕（ADR-090）

**問題**：「官方網站」是一行小字；要往下捲過評分理由，才看得到什麼時候申請、拿多少錢。

**設計**
- 頁首左邊是名稱，右邊同一列是「前往官方網站」主要按鈕；窄螢幕時按鈕換到名稱下方、佔滿整行（按鈕位置是你指定的）。
- 摘要列寫申請日期、補助、分數，和列表卡片用同一個後端函式算，測試確認兩邊一樣。
- 其餘內容分成四個頁籤：申請／資格／評分／紀錄。選到的頁籤記在 `?tab=`。
- 頁籤內容只在選到時才畫。原因是 Base UI 會等離場動畫跑完才移除舊面板，瀏覽器分頁在背景時動畫不會跑，實測兩個面板同時出現。

**概念**
- **視覺層級（visual hierarchy）**：最重要的下一步要最顯眼。例子：官方網站從文字連結改成主要按鈕。
- **漸進揭露（progressive disclosure）**：先給重點，細節收起來，要的時候才打開。代價是：沒選到的頁籤內容不在頁面上，⌘F 找不到。

**程式碼導讀**
- `frontend/src/pages/ScholarshipDetail.tsx` 的 `Summary`、`TABS`，以及每個 `TabsPanel` 裡的 `tab === "..." &&`。
- `backend/app/features/scholarships/api.py` 的 `read_scholarship`：`deadline_line`、`amount_headline`。
- `backend/tests/test_detail_summary_db.py`：前 20 筆的摘要和列表卡片一字不差。

## 4. 國家選單與「Enter 會送出表單」（ADR-091）

**問題**：國籍和想去的國家要打國碼，打錯要存檔後才知道。

**設計**
- 後端新增 `GET /api/profile/countries`，回傳 250 個國碼和中文名稱。中文名稱的排序交給瀏覽器（`localeCompare`），因為 Python 沒有內建中文排序。
- 前端用 Base UI 的 Combobox：可以打中文名稱或國碼搜尋。國籍是單選，想去的國家是多選，選到的國家用小標籤列出。
- 實測發現，在搜尋框按 Enter 會直接存檔。改成第一個符合的選項自動反白，按 Enter 就選它；Enter 不再往上傳到表單。

**概念**
- **隱含送出（implicit submission）**：表單裡的輸入框按 Enter，瀏覽器會自動按下送出鈕。例子：國家搜尋框沒有反白的選項時，Enter 交給了表單，於是存檔。
- **可搜尋的下拉選單（combobox）**：輸入框加上選項清單。選項很多（250 國）時，比一般下拉選單好找。

**程式碼導讀**
- `frontend/src/components/country-picker.tsx`：`matches`（可搜中文名稱或國碼）、`autoHighlight`、`keepEnterInside`。
- `backend/app/features/profiles/api.py` 的 `list_countries`；`backend/app/features/scholarships/countries.py` 的 `all_codes`。

## 5. 驗證時的意外：攔不住的存檔

**問題**：我想看看存檔時送出的內容，所以在瀏覽器把 `window.fetch` 換成假的，再按「存檔」。結果真的存了：你的「想去的國家」變成瑞典，背景也重新評分了一次。我馬上改回原本的值；兩次重新評分共 11 次 AI 呼叫，約 US$0.002。

**為什麼攔不住**：API 用戶端（openapi-fetch）在網頁載入時就記住了當時的 `fetch`，之後再換掉 `window.fetch`，它不會知道。

**概念**
- **參照在建立時就綁定**：模組載入時拿到的函式參照，之後替換全域變數，不會影響它。
- **驗證不能有副作用**：檢查功能的動作不應該改到真實資料。之後的做法：驗證時不按任何會寫入資料的按鈕，送出的內容改用程式碼或測試確認。

## 你可以怎麼講

「我用 UI/UX 設計師的角度，把網頁從頭走過一遍，找出 18 個問題，排好優先順序，寫成計畫。最大的三個是：上一頁篩選會消失、卡片只有標題能點、官方網站的連結太小。我把篩選改存在網址裡，整張卡片都能點，詳細頁改成摘要加頁籤。國家改成可以搜尋的選單，通知也能點回獎學金。每一項都用瀏覽器實際操作驗證過。」

講的時候分清楚：要修哪些問題、頁籤加摘要（選丙）、按鈕放在標題右邊、國家用選單、通知要能點回去，是你的決定（ADR-090 到 092）。延伸連結改成 `onClick`、頁籤只畫選到的內容、Enter 的處理方式，是 AI 依實測結果做的實作決定。

## 自我檢查

1. 篩選條件為什麼放在網址，而不是 `localStorage`？說出一個網址做得到、`localStorage` 做不到的情境。
2. 「延伸連結」為什麼在這個專案失敗？如果把 `CardHeader` 的 `container-type` 拿掉，會發生什麼事？
3. 頁籤的代價是什麼？如果要讓 ⌘F 也找得到評分理由，你會怎麼改？
