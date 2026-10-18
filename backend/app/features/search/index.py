"""建索引指令（第 5 天 RAG）：原文切段、表格說明、主題標籤、段落向量、獎學金向量；只算有變的。

用法：uv run python -m app.features.search.index [--source ID] [--shard K/N] [--max-cost NT$]
"""

import argparse
import json
import sys
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.fetch.text import content_hash, decode_snapshot
from app.core.llm.gemini import GeminiEmbedder, GeminiLLM, LLMError, MissingApiKeyError
from app.features.documents.chunking import Chunk as Piece
from app.features.documents.chunking import chunk_html, chunk_transcript
from app.features.documents.transcribe import cache_path
from app.features.scholarships.extract import documents
from app.features.scholarships.models import EMBEDDING_DIMENSIONS, Scholarship
from app.features.search import plan, text
from app.features.search.models import Chunk
from app.features.sources.fetch import SNAPSHOT_DIR, in_shard
from app.features.sources.models import Source
from app.shared.db import SessionLocal
from app.shared.settings import settings

TABLE_VERSION = "table-1"  # 改提示詞就要改版本號
TOPIC_VERSION = "topics-1"
TABLES_PER_CALL = 10  # 表格說明一次最多送幾個（「Claude 自行決定」第 6 點）
CHUNKS_PER_CALL = 25  # 主題標籤一次最多送幾段

# 主題代號（ADR-036 C，「Claude 自行決定」第 7 點）
Topic = Literal[
    "eligibility", "nationality", "deadline", "documents", "amount",
    "quota", "degree", "application", "programme", "other",
]

TABLE_PROMPT = """下面是從獎學金原文擷取的幾個表格，每個前面有編號。
替每個表格寫一句中文說明，講清楚這個表格在列什麼（例如「各名額類別的名額與可去的國家」），
讓人看說明就知道要不要打開整個表格。

{tables}
"""

TOPIC_PROMPT = """下面是獎學金原文的幾個段落，每段前面有編號。替每一段標上它談到的主題（可以多個）：
eligibility 申請資格、nationality 國籍限制、deadline 日期與截止、documents 要交的文件、amount 補助金額、
quota 名額、degree 學位、application 申請方式與流程、programme 課程內容、other 其他（選單、聯絡方式等）。

{chunks}
"""


class TableSummary(BaseModel):
    index: int = Field(description="表格編號，照抄")
    summary: str = Field(description="一句中文說明")


class TableSummaries(BaseModel):
    items: list[TableSummary]


class ChunkTopics(BaseModel):
    index: int = Field(description="段落編號，照抄")
    topics: list[Topic] = Field(description="這一段談到的主題")


class TopicLabels(BaseModel):
    items: list[ChunkTopics]


def pieces_of(session: Session, source: Source) -> list[tuple[int, Piece]]:
    """這個來源每份快照切出來的段落：（快照 id, 段落）。PDF 用第 3 天的轉錄稿。"""
    found: list[tuple[int, Piece]] = []
    for snapshot in documents(session, source):
        path = SNAPSHOT_DIR / snapshot.file_path
        if path.suffix == ".pdf":
            cache = cache_path(path)
            if not cache.exists():
                print(f"skip       沒有轉錄稿：{snapshot.url}")
                continue
            pieces = chunk_transcript("\n\n".join(json.loads(cache.read_text(encoding="utf-8"))))
        else:
            pieces = chunk_html(decode_snapshot(path.read_bytes()))
        found += [(snapshot.id, piece) for piece in pieces]
    return found


def summarize_tables(llm: GeminiLLM, tables: dict[int, str]) -> dict[int, str]:
    """表格的一句說明（ADR-036 B）；一次送最多 TABLES_PER_CALL 個。"""
    found: dict[int, str] = {}
    keys = list(tables)
    for start in range(0, len(keys), TABLES_PER_CALL):
        batch = keys[start : start + TABLES_PER_CALL]
        listing = "\n\n".join(f"[{i}]\n{tables[i]}" for i in batch)
        result = llm.extract(TABLE_PROMPT.format(tables=listing), TableSummaries)
        found |= {item.index: item.summary for item in result.items if item.index in batch}
    return found


def label_topics(llm: GeminiLLM, chunks: dict[int, str]) -> dict[int, list[str]]:
    """每段的主題（ADR-036 C）；一次送最多 CHUNKS_PER_CALL 段，AI 漏掉的段落標 other。"""
    found: dict[int, list[str]] = {}
    keys = list(chunks)
    for start in range(0, len(keys), CHUNKS_PER_CALL):
        batch = keys[start : start + CHUNKS_PER_CALL]
        listing = "\n\n".join(f"[{i}]\n{chunks[i][:1500]}" for i in batch)
        result = llm.extract(TOPIC_PROMPT.format(chunks=listing), TopicLabels)
        found |= {item.index: list(dict.fromkeys(item.topics)) for item in result.items if item.index in batch}
    return {i: found.get(i, ["other"]) for i in keys}


def index_source(
    session: Session, llm: GeminiLLM, embedder: GeminiEmbedder, source: Source
) -> Counter[str]:
    """重建一個來源的段落；內容和模型都沒變的段落沿用舊的向量、說明與主題（「Claude 自行決定」第 5 點）。"""
    counts: Counter[str] = Counter()
    pieces = pieces_of(session, source)
    hashes = [content_hash(piece.text) for _, piece in pieces]
    old = {
        (row.content_hash, row.embed_model or ""): plan.Reusable(
            list(row.embedding) if row.embedding is not None else [], row.summary, list(row.topics)
        )
        for row in session.scalars(select(Chunk).where(Chunk.source_id == source.id))
        if row.embedding is not None
    }
    reused, to_compute = plan.reuse_plan(old, hashes, embedder.model_id)
    tables = {i: pieces[i][1].text for i in to_compute if pieces[i][1].kind == "table"}
    summaries = summarize_tables(llm, tables) if tables else {}
    topics = label_topics(llm, {i: pieces[i][1].text for i in to_compute}) if to_compute else {}
    # 表格用一句說明算向量（ADR-036 B）；命中時回傳的是整個表格
    items = [
        (text.chunk_title(list(pieces[i][1].heading_path)), summaries.get(i) or pieces[i][1].text)
        for i in to_compute
    ]
    vectors = dict(zip(to_compute, embedder.embed_documents(items), strict=True)) if items else {}

    session.execute(delete(Chunk).where(Chunk.source_id == source.id))
    for i, (snapshot_id, piece) in enumerate(pieces):
        kept = reused.get(i)
        session.add(
            Chunk(
                source_id=source.id,
                snapshot_id=snapshot_id,
                position=i,
                heading_path=list(piece.heading_path),
                kind=piece.kind,
                text=piece.text,
                content_hash=hashes[i],
                summary=kept.summary if kept else summaries.get(i),
                topics=kept.topics if kept else topics[i],
                embedding=kept.embedding if kept else vectors[i],
                embed_model=embedder.model_id,
            )
        )
    counts["reused"] += len(reused)
    counts["computed"] += len(to_compute)
    counts["tables"] += sum(1 for _, piece in pieces if piece.kind == "table")
    return counts


def index_scholarship(session: Session, embedder: GeminiEmbedder, source: Source) -> bool:
    """獎學金向量（ADR-032）：組成的文字或模型變了才重算；回傳有沒有重算。"""
    row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).first()
    if row is None:
        return False
    profile = text.scholarship_profile(
        {
            "name": row.name, "provider": row.provider, "countries": row.countries,
            "degrees": row.degrees, "fields": row.fields, "coverage": row.coverage,
            "amount": row.amount, "other_eligibility": row.other_eligibility,
            "language_requirements": row.language_requirements,
        }
    )
    digest = content_hash(profile)
    if row.embed_hash == digest and row.embed_model == embedder.model_id:
        return False
    row.embedding = embedder.embed_documents([(row.name, profile)])[0]
    row.embed_hash = digest
    row.embed_model = embedder.model_id
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="建立段落與獎學金的向量索引")
    parser.add_argument("--source", type=int, help="只處理這個來源 id")
    parser.add_argument("--shard", help="K/N：只處理第 K 份（共 N 份），讓 N 個程序平行跑")
    parser.add_argument("--max-cost", type=float, help="這次執行的 AI 費用上限（新台幣）")
    args = parser.parse_args()
    try:
        llm = GeminiLLM(settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute)
        embedder = GeminiEmbedder(
            settings.embedding_model, settings.google_api_key, EMBEDDING_DIMENSIONS,
            settings.llm_requests_per_minute,
        )
    except MissingApiKeyError as error:
        sys.exit(str(error))

    query = (
        select(Source)
        .join(Scholarship, Scholarship.source_id == Source.id)
        .order_by(Source.id)
    )
    if args.source:
        query = query.where(Source.id == args.source)
    totals: Counter[str] = Counter()
    with SessionLocal() as session:
        for source in session.scalars(query).all():
            if args.shard and not in_shard(source.url, args.shard):
                continue
            if args.max_cost and llm.cost_usd() * 32 > args.max_cost:
                print(f"已超過這次的費用上限 NT${args.max_cost}，停下")
                break
            try:
                counts = index_source(session, llm, embedder, source)
                counts["scholarship_vectors"] += index_scholarship(session, embedder, source)
                session.commit()  # 每個來源各自一個交易
            except LLMError as error:
                session.rollback()
                totals["failed"] += 1
                print(f"failed     {source.id} {source.name}：{error}")
                continue
            totals += counts
            print(f"{source.id:>4} {source.name[:40]}｜沿用 {counts['reused']}、重算 {counts['computed']}、表格 {counts['tables']}")
    print(
        f"段落：沿用 {totals['reused']}、重算 {totals['computed']}；表格 {totals['tables']}；"
        f"獎學金向量重算 {totals['scholarship_vectors']}；失敗 {totals['failed']}"
    )
    print(llm.usage_line())
    print(f"嵌入：送出約 {embedder.characters:,} 字元")


if __name__ == "__main__":
    main()
