#!/usr/bin/env bash
# 重新產生 docs/architecture/ 裡「由工具產生」的架構文件。本機和 CI 跑同一個腳本。
#
# 用法：
#   scripts/gen-docs.sh            全部
#   scripts/gen-docs.sh backend    API 端點（openapi.json）與資料表（db/）
#   scripts/gen-docs.sh frontend   前端模組依賴圖（frontend-deps.md）
#
# CI 跑完後檢查 docs/architecture/ 有沒有變動；有變動代表提交的文件過期。
# 說明在 docs/architecture/README.md。
set -euo pipefail  # 任何一步失敗就停（含管線中間的指令）

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/architecture"

# 視圖 2：API 端點。從 FastAPI 程式碼匯出 OpenAPI，不用啟動伺服器。
# 排版成多行並把鍵排序，git diff 才看得出改了哪個端點。
gen_openapi() {
  (cd "$ROOT/backend" && uv run python -m app.export_openapi) \
    | (cd "$ROOT/backend" && uv run python -m json.tool --sort-keys --no-ensure-ascii) \
    > "$OUT/openapi.json"
}

# 視圖 3：資料表與關係。tbls 連到已經跑完 alembic upgrade head 的 PostgreSQL，只讀結構。
# 預設連線是 docker-compose.yml 裡本機開發用的資料庫；CI 用 TBLS_DSN 指到它自己的資料庫。
gen_db() {
  (cd "$ROOT/backend" \
    && TBLS_DSN="${TBLS_DSN:-postgres://scholar:scholar@localhost:5432/scholar?sslmode=disable}" \
       tbls doc -c .tbls.yml --rm-dist)  # --rm-dist：資料表被刪掉時，連它的文件一起刪
  # 拿掉「Stored procedures and functions」那一段：裡面全是 pgvector 擴充功能自帶的函式，
  # 不是這個專案寫的；pgvector 一升級清單就變，會讓 CI 誤判成文件過期。
  awk '/^## Stored procedures and functions/{skip=1; next} /^## /{skip=0} !skip' \
    "$OUT/db/README.md" > "$OUT/db/README.md.tmp"
  mv "$OUT/db/README.md.tmp" "$OUT/db/README.md"
}

# 視圖 4：前端模組依賴圖。dependency-cruiser 讀 frontend/src 的 import，輸出 Mermaid。
# 兩張：按資料夾合併的總覽，和每個檔案的細節。node_modules（外部套件）不畫。
gen_frontend() {
  local f="$OUT/frontend-deps.md"
  cd "$ROOT/frontend"
  {
    echo "# 前端模組依賴圖"
    echo
    echo "由 dependency-cruiser 從 \`frontend/src\` 的 import 產生，不要手動修改。重新產生：\`scripts/gen-docs.sh frontend\`"
    echo
    echo "箭頭 A --> B 的意思是「A import 了 B」。"
    echo
    echo "## 按資料夾"
    echo
    echo '```mermaid'
    npx depcruise src --output-type mermaid --exclude "^node_modules" --collapse "^src/[^/]+"
    echo '```'
    echo
    echo "## 按檔案"
    echo
    echo '```mermaid'
    npx depcruise src --output-type mermaid --exclude "^node_modules"
    echo '```'
  } > "$f"
  cd "$ROOT"
}

case "${1:-all}" in
  backend) gen_openapi; gen_db ;;
  frontend) gen_frontend ;;
  all) gen_openapi; gen_db; gen_frontend ;;
  *) echo "用法：scripts/gen-docs.sh [backend|frontend]" >&2; exit 2 ;;
esac
