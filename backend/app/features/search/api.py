"""問答 API（第 9 天）：網頁的問答頁呼叫這個端點；每題約 NT$0–0.3（第 5 天實測）。

問題放在 JSON 內容裡（POST）：問題可能很長，不適合放網址；也剛好受到 FastAPI 只解析 JSON 的保護（ADR-072）。
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.llm.gemini import GeminiEmbedder, GeminiLLM, LLMError, MissingApiKeyError
from app.features.pipeline import breaker
from app.features.scholarships.models import EMBEDDING_DIMENSIONS
from app.features.search import ask
from app.shared.db import get_session
from app.shared.settings import settings

DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api/ask", tags=["問答"])


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500, description="要問的問題")


class CitationOut(BaseModel):
    id: str  # 答案裡的編號，例如 F2、C3
    where: str  # 出處網址與位置


class ListedOut(BaseModel):
    """filter 路線篩到的一個申請期。"""

    id: int
    name: str
    closes_at: datetime
    status: str
    label: str | None
    nationality_unclear: bool  # 獎學金沒寫國籍資格（ADR-043）
    deadline_unverified: bool  # 截止日沒核對過
    official_url: str | None


class CandidateOut(BaseModel):
    id: int
    name: str
    similarity: float


class AskOut(BaseModel):
    route: str  # 實際走的路線：lookup、filter、semantic、document
    notes: list[str]  # 改走其他路線的說明
    answer: str | None
    citations: list[CitationOut]
    invalid: list[str]  # 答案引用了、但不存在的編號（已略過）
    listed: list[ListedOut]
    candidates: list[CandidateOut]  # 名稱對不到時，最像的幾筆


@router.post("")
def ask_question(data: AskIn, session: DbSession) -> AskOut:
    if breaker.is_open(session):
        raise HTTPException(status_code=503, detail="斷路器打開中，AI 步驟暫停（ADR-056）")
    try:
        llm = GeminiLLM(settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute)
        embedder = GeminiEmbedder(
            settings.embedding_model, settings.google_api_key, EMBEDDING_DIMENSIONS,
            settings.llm_requests_per_minute,
        )
        result = ask.ask(session, llm, embedder, data.question)
    except MissingApiKeyError:
        raise HTTPException(status_code=503, detail="backend/.env 還沒有 Gemini 金鑰") from None
    except LLMError:
        # 不把原始錯誤內容傳給瀏覽器（第 8 天：錯誤訊息可能帶出設定值）
        raise HTTPException(status_code=503, detail="AI 暫時不能用（網路或額度問題），請稍後再試") from None
    answered = result.answered
    return AskOut(
        route=result.route,
        notes=result.notes,
        answer=answered.answer if answered else None,
        citations=[CitationOut(id=e.id, where=e.where) for e in answered.citations] if answered else [],
        invalid=answered.invalid if answered else [],
        listed=[
            ListedOut(
                id=scholarship.id,
                name=scholarship.name,
                closes_at=cycle.closes_at,
                status=cycle.status,
                label=cycle.label,
                nationality_unclear=scholarship.nationality_scope == "unclear",
                deadline_unverified=cycle.verification != "supported",
                official_url=scholarship.official_url,
            )
            for scholarship, cycle in result.listed
        ],
        candidates=[CandidateOut(id=row.id, name=row.name, similarity=similarity) for row, similarity in result.candidates],
    )
