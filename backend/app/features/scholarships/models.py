"""scholarships 資料表（ADR-018 篩選欄位＋JSONB、ADR-024、ADR-025 整數主鍵）。"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, Identity, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class TaiwanEligibility(enum.StrEnum):
    """台灣籍能否申請。原文沒提到台灣一律是 UNCLEAR，絕不推定可以。"""

    YES = "yes"
    NO = "no"
    UNCLEAR = "unclear"


class ScholarshipStatus(enum.StrEnum):
    ACTIVE = "active"  # 使用中
    ARCHIVED = "archived"  # 已封存（截止後）


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    # 讓資料庫存小寫的值（yes），而不是成員名稱（YES）
    return [member.value for member in enum_cls]


class Scholarship(Base):
    __tablename__ = "scholarships"

    # ADR-025：整數自動遞增的主鍵
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)  # 原文名稱
    name_zh: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    # 篩選用欄位（ADR-018）：一筆獎學金可能有多個國家、學位、領域，所以用陣列
    countries: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    degrees: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    fields: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    coverage: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[str | None] = mapped_column(Text)  # 保留原文，例如「每月 GBP 1,400」
    # 選項存成文字欄位，不用 PostgreSQL 原生 ENUM（改選項時不必手寫遷移）
    taiwan_eligibility: Mapped[TaiwanEligibility] = mapped_column(
        Enum(TaiwanEligibility, native_enum=False, values_callable=_enum_values, length=16),
        server_default=TaiwanEligibility.UNCLEAR.value,
    )
    taiwan_conditions: Mapped[str | None] = mapped_column(Text)
    language_requirements: Mapped[str | None] = mapped_column(Text)
    other_eligibility: Mapped[str | None] = mapped_column(Text)
    requires_admission: Mapped[bool | None]  # 是否需先錄取；不知道就留空
    official_url: Mapped[str | None] = mapped_column(Text)
    # 最後驗證時間（UTC）；第 3 天由驗證者寫入
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ScholarshipStatus] = mapped_column(
        Enum(ScholarshipStatus, native_enum=False, values_callable=_enum_values, length=16),
        server_default=ScholarshipStatus.ACTIVE.value,
    )
    # 完整抽取結果（ADR-018）。修改時要整個重新指定，不要原地改字典
    extracted: Mapped[dict[str, Any]] = mapped_column(JSONB)
