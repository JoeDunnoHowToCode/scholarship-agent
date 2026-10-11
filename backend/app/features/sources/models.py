"""sources 與 snapshots 資料表（ADR-019、024、025、026）。"""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class SourceKind(enum.StrEnum):
    GOVERNMENT = "government"  # 政府
    INSTITUTION = "institution"  # 機構
    UNIVERSITY = "university"  # 大學
    AGGREGATOR = "aggregator"  # 彙整網站


class FetchMethod(enum.StrEnum):
    HTML = "html"
    PDF = "pdf"  # 之後需要 JavaScript 的網站再加 browser（ADR-027）


class Discovery(enum.StrEnum):
    SEED = "seed"  # 種子
    SEARCH = "search"  # 發掘 agent 搜尋到的
    CATALOGUE = "catalogue"  # 從目錄頁解析出來的（例如 EACEA 的學程網站）


class SourceStatus(enum.StrEnum):
    CANDIDATE = "candidate"  # 候選
    APPROVED = "approved"  # 已核准


def _text_enum(enum_cls: type[enum.Enum]) -> Enum:
    # 選項存成文字欄位，不用 PostgreSQL 原生 ENUM；資料庫存小寫的值，不是成員名稱
    return Enum(
        enum_cls,
        native_enum=False,
        values_callable=lambda cls: [member.value for member in cls],
        length=16,
    )


class Source(Base):
    """要定期檢查的網址（ADR-026：來源清單放資料庫）。"""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    # 從目錄解析出來的子來源指向目錄（例如學程網站指向 EACEA 目錄）；種子是空白
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sources.id"))
    # 唯一限制：同一個網址只會有一筆，seed 和發掘 agent 都靠它避免重複
    url: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[SourceKind] = mapped_column(_text_enum(SourceKind))
    country: Mapped[str | None] = mapped_column(Text)  # 英文名稱，例如 United Kingdom
    fetch_method: Mapped[FetchMethod] = mapped_column(
        _text_enum(FetchMethod), server_default=FetchMethod.HTML.value
    )
    follow_pagination: Mapped[bool] = mapped_column(server_default=text("false"))
    # 第 0 頁就是首頁：打開時 ?page=0 換成首頁網址，避免同一頁抓兩次（目前只有 EACEA）
    page_zero_is_first: Mapped[bool] = mapped_column(server_default=text("false"))
    # 上次完整抓取時成功檢查到的頁數；只記翻頁來源，用來發現翻頁失效（漏抓警示）
    last_page_count: Mapped[int | None]
    check_interval_hours: Mapped[int] = mapped_column(server_default=text("24"))  # 第 6 天排程用
    enabled: Mapped[bool] = mapped_column(server_default=text("true"))
    discovery: Mapped[Discovery] = mapped_column(
        _text_enum(Discovery), server_default=Discovery.SEED.value
    )
    status: Mapped[SourceStatus] = mapped_column(
        _text_enum(SourceStatus), server_default=SourceStatus.APPROVED.value
    )
    # 需人工的原因；空白代表自動抓取，有內容就跳過、等使用者處理（ADR-028）
    manual_reason: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Snapshot(Base):
    """一個網址某一版的原始檔；內容變了才新增一列（ADR-019）。"""

    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sources.id"))
    url: Mapped[str] = mapped_column(Text)  # 實際抓的網址；翻頁時每頁一個
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))  # 正規化文字的 SHA-256
    file_path: Mapped[str] = mapped_column(Text)  # 相對於 backend/data/snapshots/
    http_status: Mapped[int] = mapped_column(SmallInteger)
    # 下次條件式請求用：伺服器說「沒更新」就不必重新下載
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
