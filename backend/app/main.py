"""API 程序的入口（ADR-003：API 與背景 worker 是兩個程序）。

第 1 天只有健康檢查；第 6 天加上個人資料與評分結果的 API。
"""

from fastapi import FastAPI

from app.features.matching.api import router as match_router
from app.features.profiles.api import router as profile_router

app = FastAPI(title="留學獎學金 Agent")
app.include_router(profile_router)
app.include_router(match_router)


@app.get("/health")
def health() -> dict[str, str]:
    # 只回報「程序活著、能回應請求」
    return {"status": "ok"}
