// 整體大地圖的來源（架構文件視圖 1）。這個檔案是手寫的：加減方塊或箭頭時改這裡，
// 再跑 scripts/gen-docs.sh c4 重新產生 c4.md。
//
// 用的是 C4 模型的前兩層：
//   第 1 層（系統情境）：這個系統、使用它的人、它依賴的外部服務。
//   第 2 層（容器）：系統裡各自獨立執行的幾大塊（網頁、API、worker、資料庫、佇列）。
// 方塊裡面的細節（端點、資料表、模組依賴）由其他視圖自動產生，不畫在這裡。
workspace "留學獎學金 Agent" "自動收集歐洲留學獎學金，依使用者條件評分並通知。" {

    model {
        user = person "使用者" "準備到歐洲留學、在找獎學金的人（第一版只有本人）。"

        agent = softwareSystem "留學獎學金 Agent" "收集獎學金、抽取條件、依個人條件評分、通知、回答問題。跑在使用者自己的電腦上。" {
            web = container "網頁前端" "列出獎學金與所需文件、編輯個人條件、提問、看紀錄與費用。" "React、TypeScript、Vite"
            api = container "後端 API" "提供 /api 給前端；建置過的前端網頁也由它一起提供。" "Python、FastAPI"
            worker = container "背景 worker 與排程" "每天抓網頁、抽取獎學金資料、評分、找新來源、送通知。" "Python、RQ、launchd"
            db = container "資料庫" "獎學金、來源、快照、個人條件、評分、AI 呼叫紀錄；文件片段的向量。" "PostgreSQL 17、pgvector" "Database"
            queue = container "工作佇列" "排隊等 worker 執行的工作。" "Redis 7" "Queue"
        }

        sites = softwareSystem "獎學金網站" "大學與基金會公布獎學金的網頁與 PDF。" "External"
        gemini = softwareSystem "Gemini" "Google 的 AI 模型：抽取、評分、問答、產生向量。" "External"
        tavily = softwareSystem "Tavily" "網頁搜尋服務：找新的獎學金來源。" "External"
        telegram = softwareSystem "Telegram" "把通知送到使用者手機。" "External"

        // 第 1 層的箭頭
        user -> agent "看獎學金、填個人條件、提問"
        agent -> sites "抓網頁與 PDF"
        agent -> gemini "抽取、評分、問答（不送可識別個人的資料）"
        agent -> tavily "搜尋新來源"
        agent -> telegram "送通知"
        telegram -> user "通知訊息"

        // 第 2 層的箭頭
        user -> web "用瀏覽器操作"
        web -> api "呼叫 /api" "HTTP、JSON"
        api -> db "讀寫" "SQLAlchemy"
        api -> queue "放入工作" "RQ"
        api -> gemini "問答" "HTTPS"
        queue -> worker "交付工作" "RQ"
        worker -> db "讀寫" "SQLAlchemy"
        worker -> sites "抓網頁與 PDF" "HTTPS"
        worker -> gemini "抽取、評分、產生向量" "HTTPS"
        worker -> tavily "搜尋新來源" "HTTPS"
        worker -> telegram "送通知" "HTTPS"
    }

    views {
        systemContext agent "SystemContext" "第 1 層：系統、使用者與外部服務" {
            include *
            autoLayout lr
        }

        container agent "Containers" "第 2 層：系統裡各自執行的幾大塊" {
            include *
            autoLayout lr
        }
    }
}
