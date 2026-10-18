"""用一句話找獎學金（ADR-032）：問句變成向量，找意思最接近的獎學金。

用法：uv run python -m app.features.search.find "想去北歐讀永續相關的碩士" [--limit 10]
"""

import argparse
import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.llm.base import Embedder
from app.core.llm.gemini import GeminiEmbedder, MissingApiKeyError
from app.features.scholarships.models import EMBEDDING_DIMENSIONS, Cycle, Scholarship
from app.shared.db import SessionLocal
from app.shared.settings import settings


def next_deadline(cycles: list[Cycle]) -> datetime | None:
    """還能申請（開放中或即將開放）的申請期裡，最早的截止時間。"""
    open_ones = [c.closes_at for c in cycles if c.status in ("open", "upcoming")]
    return min(open_ones, default=None)


def find(session: Session, embedder: Embedder, sentence: str, limit: int) -> list[tuple[Scholarship, float]]:
    """回傳（獎學金, 相似度）；只看代表的那筆（「Claude 自行決定」第 9 點）。"""
    vector = embedder.embed_query(sentence)
    distance = Scholarship.embedding.cosine_distance(vector)
    rows = session.execute(
        select(Scholarship, distance)
        .where(Scholarship.duplicate_of.is_(None), Scholarship.embedding.is_not(None))
        .options(selectinload(Scholarship.cycles))
        .order_by(distance)
        .limit(limit)
    ).all()
    # 餘弦距離＝1−餘弦相似度
    return [(row, 1 - float(gap)) for row, gap in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="用一句話找獎學金")
    parser.add_argument("sentence", help="想找什麼樣的獎學金")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    try:
        embedder = GeminiEmbedder(
            settings.embedding_model, settings.google_api_key, EMBEDDING_DIMENSIONS,
            settings.llm_requests_per_minute,
        )
    except MissingApiKeyError as error:
        sys.exit(str(error))
    with SessionLocal() as session:
        for rank, (row, similarity) in enumerate(find(session, embedder, args.sentence, args.limit), 1):
            deadline = next_deadline(row.cycles)
            when = f"最早截止 {deadline:%Y-%m-%d}" if deadline else "目前沒有開放中的申請期"
            print(f"{rank:>2}. {similarity:.2f}  {row.name}｜{row.status.value}｜{when}")
            print(f"      {row.official_url}")


if __name__ == "__main__":
    main()
