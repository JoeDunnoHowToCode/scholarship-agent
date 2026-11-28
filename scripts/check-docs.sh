#!/usr/bin/env bash
# 檢查 docs/architecture/ 裡由工具產生的文件有沒有過期：重新產生一次，再看有沒有變動。
# CI 用這個腳本；本機也可以跑。參數和 scripts/gen-docs.sh 一樣（backend、frontend、c4，或不給＝全部）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

scripts/gen-docs.sh "$@"

# --porcelain 同時列出「被改過的檔案」和「新出現、還沒提交的檔案」；沒有輸出就是沒有變動
changed="$(git status --porcelain -- docs/architecture)"
if [ -n "$changed" ]; then
  echo "架構文件過期了：重新產生後和提交的內容不同。" >&2
  echo "$changed" >&2
  git --no-pager diff --stat -- docs/architecture >&2
  echo "修法：在本機跑 scripts/gen-docs.sh ${*:-}，把 docs/architecture/ 的變動提交。" >&2
  exit 1
fi
echo "架構文件是最新的。"
