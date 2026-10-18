"""段落表（第 5 天 RAG，ADR-032、036、050）：原文切段後每段一列，連同向量。"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.features.scholarships.models import EMBEDDING_DIMENSIONS
from app.shared.db import Base


class Chunk(Base):
    """原文的一段；表格自成一段，向量用表格的一句說明算（ADR-036 A、B）。"""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sources.id", ondelete="CASCADE"))
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("snapshots.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)  # 在這份快照裡的順序
    heading_path: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    kind: Mapped[str] = mapped_column(String(8))  # text／table
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(Text)  # 表格的一句說明（ADR-036 B）
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")  # ADR-036 C
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embed_model: Mapped[str | None] = mapped_column(Text)  # 例如 gemini-embedding-2@1536
