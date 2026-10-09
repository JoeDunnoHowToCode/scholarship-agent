"""API 程序的入口（ADR-003：API 與背景 worker 是兩個程序）。

第 1 天只有健康檢查，用來確認骨架跑得起來。
"""

from fastapi import FastAPI

app = FastAPI(title="留學獎學金 Agent")


@app.get("/health")
def health() -> dict[str, str]:
    # 只回報「程序活著、能回應請求」
    return {"status": "ok"}
