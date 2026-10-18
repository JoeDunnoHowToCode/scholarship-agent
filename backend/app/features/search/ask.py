"""路由問答（ADR-035、051、052）：AI 先判斷問題類型並抽出參數，再走固定路線，答案附出處。

用法：uv run python -m app.features.search.ask "教育部北歐國家有幾個名額？"

四條路線（「Claude 自行決定」第 10 點）：
- lookup：問某一筆獎學金的名額、文件、截止日 → 查資料表
- filter：依條件列出獎學金 → 條件轉 SQL，固定格式列出，不再呼叫 AI
- semantic：其他問題 → 向量搜尋原文段落
- document：針對某一份文件 → 整份交給 AI
找不到獎學金、或篩不到東西，就退回 semantic。只透過模型插座呼叫，不綁定 Gemini（ADR-052）。
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import any_, literal, select
from sqlalchemy.orm import Session, selectinload

from app.core.llm.base import Embedder, StructuredLLM
from app.core.llm.gemini import GeminiEmbedder, GeminiLLM, MissingApiKeyError
from app.features.scholarships.dedup import normalize_name
from app.features.scholarships.models import EMBEDDING_DIMENSIONS, Scholarship
from app.features.search import citations, filters
from app.features.search.index import Topic
from app.features.search.models import Chunk
from app.features.sources.models import Source
from app.shared.db import SessionLocal
from app.shared.settings import settings

ROUTE_VERSION = "route-1"  # 改提示詞就要改版本號
ANSWER_VERSION = "answer-1"
MATCH_THRESHOLD = 0.75  # 名稱對應的相似度門檻（「Claude 自行決定」第 11 點）
TOP_CHUNKS = 8  # 語意搜尋取幾段（第 13 點）

ROUTE_PROMPT = """你負責把使用者對留學獎學金資料庫的問題分類，並抽出參數。今天是 {today}。
- lookup：問「某一個」獎學金的名額、學位、要交的文件、截止日、金額等
- filter：要依條件「列出」多個獎學金（例如國籍、學位、國家、截止日範圍、現在能不能申請）
- document：明確要針對某一份簡章或網頁整份來回答（例如「整理這份簡章的評審標準」）
- semantic：其他問題，要在原文裡搜尋
scholarship 填問題裡提到的獎學金或學程名稱（照使用者的寫法）；沒提到就留空。
topic 填問題最相關的主題，不確定就留空。

問題：{question}
"""

ANSWER_PROMPT = """你是留學獎學金助理。只能根據下面的資料回答，資料沒寫的就說不知道，不要推測。
- 每句重點後面附上出處編號，例如 [F2]、[C3]；citations 列出用到的所有編號
- 標著「待確認」的資料，回答時也要說待確認
- 用繁體中文回答

問題：{question}

資料：
{context}
"""


class Route(BaseModel):
    route: Literal["lookup", "filter", "semantic", "document"]
    scholarship: str | None = Field(description="問題裡提到的獎學金或學程名稱；沒提到就留空")
    filters: filters.Filters
    topic: Topic | None = Field(description="問題最相關的主題；不確定就留空")


class Answer(BaseModel):
    answer: str = Field(description="回答，每句重點後面附出處編號")
    citations: list[str] = Field(description="用到的出處編號，例如 F2、C3")


@dataclass
class Evidence:
    """給 AI 的一筆資料：編號、內容、出處（網址與位置）。"""

    id: str
    text: str
    where: str


def resolve(
    session: Session, embedder: Embedder, name: str
) -> tuple[Scholarship | None, list[tuple[Scholarship, float]]]:
    """問題裡的名稱 → 哪一筆獎學金；對不到就回傳最像的幾筆讓使用者選，不硬猜。"""
    key = normalize_name(name)
    rows = session.scalars(select(Scholarship).where(Scholarship.duplicate_of.is_(None))).all()
    exact = [r for r in rows if key and key in normalize_name(r.name)]
    if len(exact) == 1:
        return exact[0], []
    distance = Scholarship.embedding.cosine_distance(embedder.embed_query(name))
    near = session.execute(
        select(Scholarship, distance)
        .where(Scholarship.duplicate_of.is_(None), Scholarship.embedding.is_not(None))
        .order_by(distance)
        .limit(3)
    ).all()
    ranked = [(row, 1 - float(gap)) for row, gap in near]
    if ranked and ranked[0][1] >= MATCH_THRESHOLD:
        return ranked[0][0], ranked
    return None, ranked


def facts_of(session: Session, row: Scholarship) -> list[Evidence]:
    """lookup 路線：把一筆獎學金在資料表裡的資料整理成編號資料（引用存好的原文）。"""
    row = session.scalars(
        select(Scholarship).where(Scholarship.id == row.id).options(selectinload(Scholarship.cycles))
    ).one()
    url = row.official_url or ""
    extracted = row.extracted
    verification = extracted.get("verification", {})
    items: list[str] = [
        f"名稱：{row.name}；提供單位：{row.provider}；金額：{row.amount}；補助內容：{row.coverage}",
        (
            f"國籍資格：{row.nationality_scope} {', '.join(row.nationalities)}"
            f"{'（待確認）' if verification.get('nationality') not in ('supported', 'empty') else ''}；"
            f"引用：{extracted.get('nationality_evidence')}"
        ),
    ]
    flagged = verification.get("categories", {})
    for c in extracted.get("categories", []):
        note = "（待確認）" if c["name"] in flagged else ""
        items.append(
            f"類別「{c['name']}」{note}：名額 {c.get('quota')}；學位 {', '.join(c.get('degrees', []))}；"
            f"學位條件：{c.get('degree_conditions')}；名額引用：{c.get('quota_evidence')}；學位引用：{c.get('degrees_evidence')}"
        )
    for r in extracted.get("requirements", []):
        items.append(
            f"文件 {r['doc_type']}：{r.get('details')}；份數 {r.get('count')}；必要 {r.get('required')}；引用：{r.get('evidence')}"
        )
    for c in sorted(row.cycles, key=lambda c: c.closes_at):
        if c.estimated:
            continue
        local = c.closes_at.astimezone(ZoneInfo(c.timezone)) if c.timezone and not c.timezone_assumed else c.closes_at
        note = "" if c.verification == "supported" else "（待確認）"
        items.append(
            f"截止日{note}：{local:%Y-%m-%d %H:%M} {c.timezone or 'UTC'}；狀態 {c.status}；"
            f"適用 {c.nationality_scope}（{len(c.nationalities)} 國）／{c.funding}；說明：{c.label}；引用：{c.evidence}"
        )
    return [Evidence(f"F{i}", text, url) for i, text in enumerate(items, 1)]


def chunks_for(
    session: Session, embedder: Embedder, question: str, source_id: int | None, topic: str | None
) -> list[Evidence]:
    """semantic 路線：最接近問句的段落；有指定獎學金就只在它的段落裡找，有主題就先篩主題。"""
    distance = Chunk.embedding.cosine_distance(embedder.embed_query(question))
    base = select(Chunk, Source.url).join(Source, Source.id == Chunk.source_id).order_by(distance)
    if source_id is not None:
        base = base.where(Chunk.source_id == source_id)
    with_topic = base.where(literal(topic) == any_(Chunk.topics)) if topic else None
    rows = session.execute(with_topic.limit(TOP_CHUNKS)).all() if with_topic is not None else []
    if len(rows) < 3:  # 篩完太少就不篩主題（第 13 點）
        rows = session.execute(base.limit(TOP_CHUNKS)).all()
    return [
        Evidence(f"C{i}", chunk.text, f"{url} §{' > '.join(chunk.heading_path)}")
        for i, (chunk, url) in enumerate(rows, 1)
    ]


def whole_document(session: Session, source_id: int, url: str) -> list[Evidence]:
    """document 路線：這筆獎學金的所有段落照順序（ADR-035 單一文件模式）。"""
    rows = session.scalars(select(Chunk).where(Chunk.source_id == source_id).order_by(Chunk.position)).all()
    return [Evidence(f"C{i}", c.text, f"{url} §{' > '.join(c.heading_path)}") for i, c in enumerate(rows, 1)]


def answer_with(llm: StructuredLLM, question: str, evidence: list[Evidence]) -> None:
    """請 AI 只根據資料回答，再用程式檢查出處編號（「Claude 自行決定」第 14 點）。"""
    context = "\n\n".join(f"[{e.id}] {e.text}" for e in evidence)
    result = llm.extract(ANSWER_PROMPT.format(question=question, context=context), Answer)
    kept, invalid = citations.valid_citations(result.citations, {e.id for e in evidence})
    print(result.answer)
    print("\n出處：")
    by_id = {e.id: e for e in evidence}
    for cid in kept:
        print(f"  [{cid}] {by_id[cid].where}")
    if invalid:
        print(f"  ⚠ 答案引用了不存在的編號，已略過：{', '.join(invalid)}")


def list_filtered(session: Session, chosen: filters.Filters) -> bool:
    """filter 路線：條件轉 SQL，用固定格式列出；篩不到回傳 False（之後退回 semantic）。"""
    rows = session.execute(filters.build_filter_query(chosen, datetime.now(UTC)).limit(30)).all()
    for scholarship, cycle in rows:
        unsure = "（國籍待確認）" if scholarship.nationality_scope == "unclear" else ""
        unverified = "（截止日待確認）" if cycle.verification != "supported" else ""
        print(f"- {scholarship.name}{unsure}｜截止 {cycle.closes_at:%Y-%m-%d}（{cycle.status}）{unverified}｜{cycle.label or ''}")
        print(f"    {scholarship.official_url}")
    return bool(rows)


def ask(session: Session, llm: StructuredLLM, embedder: Embedder, question: str) -> None:
    route = llm.extract(ROUTE_PROMPT.format(today=f"{datetime.now(UTC):%Y-%m-%d}", question=question), Route)
    print(f"路線：{route.route}；獎學金：{route.scholarship}；主題：{route.topic}\n")
    target: Scholarship | None = None
    if route.scholarship:
        target, candidates = resolve(session, embedder, route.scholarship)
        if target is None and route.route in ("lookup", "document"):
            print("找不到這個獎學金，最像的是：")
            for row, similarity in candidates:
                print(f"  {similarity:.2f} {row.name}")
            print("（改用原文搜尋回答）\n")
    if route.route == "lookup" and target:
        answer_with(llm, question, facts_of(session, target))
    elif route.route == "document" and target and target.source_id:
        answer_with(llm, question, whole_document(session, target.source_id, target.official_url or ""))
    elif route.route == "filter" and list_filtered(session, route.filters):
        pass
    else:
        if route.route == "filter":
            print("條件篩不到，改用原文搜尋回答\n")
        source_id = target.source_id if target else None
        answer_with(llm, question, chunks_for(session, embedder, question, source_id, route.topic))


def main() -> None:
    parser = argparse.ArgumentParser(description="問留學獎學金的問題，答案附出處")
    parser.add_argument("question")
    args = parser.parse_args()
    try:
        llm = GeminiLLM(settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute)
        embedder = GeminiEmbedder(
            settings.embedding_model, settings.google_api_key, EMBEDDING_DIMENSIONS,
            settings.llm_requests_per_minute,
        )
    except MissingApiKeyError as error:
        sys.exit(str(error))
    with SessionLocal() as session:
        ask(session, llm, embedder, args.question)
    print(f"\n{llm.usage_line()}")


if __name__ == "__main__":
    main()
