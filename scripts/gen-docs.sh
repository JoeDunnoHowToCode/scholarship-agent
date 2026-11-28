#!/usr/bin/env bash
# 重新產生 docs/architecture/ 裡「由工具產生」的架構文件。本機和 CI 跑同一個腳本。
#
# 用法：
#   scripts/gen-docs.sh            全部
#   scripts/gen-docs.sh backend    API 端點（openapi.json）與資料表（db/）
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

case "${1:-all}" in
  backend) gen_openapi ;;
  all) gen_openapi ;;
  *) echo "用法：scripts/gen-docs.sh [backend]" >&2; exit 2 ;;
esac
