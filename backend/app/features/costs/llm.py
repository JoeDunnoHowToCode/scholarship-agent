"""建立 Gemini 的唯一入口（ADR-089）：每次呼叫都記錄費用，並受每月上限約束。

功能程式都用 gemini()，不直接 GeminiLLM(...)，才不會有漏記、不受上限管的呼叫。
"""

from app.core.llm.gemini import GeminiLLM
from app.features.costs.recorder import CostRecorder
from app.shared.settings import settings


def gemini(source_id: int | None = None, run_id: int | None = None) -> GeminiLLM:
    """source_id、run_id 是這些呼叫屬於哪個來源、哪一天的檢查（知道的話）；紀錄頁用來分。"""
    return GeminiLLM(
        settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute,
        hook=CostRecorder(settings.monthly_cap_ntd, source_id, run_id),
    )
