"""API 程序的入口（ADR-003：API 與背景 worker 是兩個程序）。

第 1 天只有健康檢查；第 6 天加上個人資料與評分結果的 API；第 9 天加上網頁用的獎學金、問答、通知歷史 API。
"""

from pathlib import Path

from fastapi import FastAPI

from app.features.matching.api import router as match_router
from app.features.notifications.api import router as event_router
from app.features.profiles.api import router as profile_router
from app.features.scholarships.api import router as scholarship_router
from app.features.search.api import router as ask_router

app = FastAPI(title="留學獎學金 Agent")
app.include_router(profile_router)
app.include_router(match_router)
app.include_router(scholarship_router)
app.include_router(ask_router)
app.include_router(event_router)


@app.get("/health")
def health() -> dict[str, str]:
    # 只回報「程序活著、能回應請求」
    return {"status": "ok"}


# 做好的網頁（第 9 天，ADR-066）：在 frontend/ 執行 npm run build 產生 dist，由 FastAPI 一起提供，
# 和 API 同一個網址；API 的路由優先。還沒建置時不檢查資料夾，FastAPI 照常啟動（只有 API）
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
app.frontend("/", directory=FRONTEND_DIST, check_dir=False)
