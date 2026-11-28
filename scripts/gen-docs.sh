#!/usr/bin/env bash
# 重新產生 docs/architecture/ 裡「由工具產生」的架構文件。本機和 CI 跑同一個腳本。
#
# 用法：
#   scripts/gen-docs.sh            全部
#   scripts/gen-docs.sh backend    API 端點（openapi.json）與資料表（db/）
#   scripts/gen-docs.sh frontend   前端模組依賴圖（frontend-deps.md）
#   scripts/gen-docs.sh c4         整體大地圖（c4.md，需要 Docker）
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

# 視圖 1：整體大地圖。來源是手寫的 docs/architecture/workspace.dsl（Structurizr DSL）。
# 先 validate（DSL 寫錯就在這裡失敗），再匯出成 Mermaid，包進 c4.md。需要 Docker。
# 映像用 digest 固定版本（2026.10.26-noble），和 CI 的 actions 固定到 commit 是同一個道理。
STRUCTURIZR_IMAGE="structurizr/structurizr@sha256:1081d615e7a539aee8b8360e36a58f42ff6412dd8f0e1b053134cb2c76ab2303"
structurizr() {
  # --user：讓容器用目前的使用者寫檔，產生的檔案才不會變成 root 的
  docker run --rm --user "$(id -u):$(id -g)" \
    -v "$OUT:/usr/local/structurizr" "$STRUCTURIZR_IMAGE" "$@"
}
# Structurizr 匯出的標籤是 HTML（<div style=...>）；GitHub 顯示 Mermaid 時不允許 HTML，
# 所以改成純文字：每一段之間換行（<br/>），其餘標籤拿掉。
c4_view() {
  sed -E -e "s#<div[^>]*></div>##g" -e "s#</div><div[^>]*>#<br/>#g" \
         -e "s#<div[^>]*>##g" -e "s#</div>##g" -e "s#<br />#<br/>#g" "$1"
}
gen_c4() {
  local tmp="$OUT/.c4-export" f="$OUT/c4.md"
  rm -rf "$tmp"
  structurizr validate -workspace workspace.dsl
  structurizr export -workspace workspace.dsl -format mermaid -output .c4-export
  {
    echo "# 整體大地圖（C4 第 1、2 層）"
    echo
    echo "由 Structurizr 從 \`workspace.dsl\` 匯出，不要手動修改這個檔案。要改圖請改 \`workspace.dsl\`，再跑 \`scripts/gen-docs.sh c4\`。"
    echo
    echo "## 第 1 層：系統情境"
    echo
    echo "這個系統、使用它的人、它依賴的外部服務。"
    echo
    echo '```mermaid'
    c4_view "$tmp/structurizr-SystemContext.mmd"
    echo '```'
    echo
    echo "## 第 2 層：容器"
    echo
    echo "系統裡各自獨立執行的幾大塊。這裡的「容器」是 C4 的用詞，意思是「一個獨立執行的程式或資料庫」，不是 Docker 容器。"
    echo
    echo '```mermaid'
    c4_view "$tmp/structurizr-Containers.mmd"
    echo '```'
  } > "$f"
  rm -rf "$tmp"
}

case "${1:-all}" in
  backend) gen_openapi; gen_db ;;
  frontend) gen_frontend ;;
  c4) gen_c4 ;;
  all) gen_openapi; gen_db; gen_frontend; gen_c4 ;;
  *) echo "用法：scripts/gen-docs.sh [backend|frontend|c4]" >&2; exit 2 ;;
esac
