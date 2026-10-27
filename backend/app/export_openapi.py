"""印出 API 的 OpenAPI 文件（第 9 天，ADR-067）：前端用它產生 TypeScript 型別，不用啟動伺服器。

用法：uv run python -m app.export_openapi > openapi.json（前端的 npm run gen:api 會自動執行）
"""

import json

from app.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), ensure_ascii=False))
