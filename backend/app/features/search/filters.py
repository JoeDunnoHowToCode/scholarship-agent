"""條件篩選（ADR-051）：AI 只填篩選條件表格，程式把它轉成 SQL；AI 不直接寫 SQL。

這樣 AI 就算填錯，也只是篩錯，不會改到資料或查到不該查的東西。
"""

from datetime import UTC, date, datetime, time, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    any_,
    false,
    literal,
    not_,
    or_,
    select,
)
from sqlalchemy.orm import InstrumentedAttribute

from app.features.scholarships.models import Cycle, Scholarship
from app.features.scholarships.schemas import Degree


class Filters(BaseModel):
    """路由問答時，AI 從問題裡抽出的篩選條件；沒提到的留空。"""

    nationality: str | None = Field(description="申請人的國籍，ISO 3166-1 兩碼國碼，例如台灣 TW；沒提到就留空")
    degree: Degree | None = Field(description="想讀的學位；沒提到就留空")
    country: str | None = Field(description="想去的國家，ISO 3166-1 兩碼國碼，例如法國 FR；沒提到就留空")
    deadline_after: date | None = Field(description="截止日不早於這天，YYYY-MM-DD；沒提到就留空")
    deadline_before: date | None = Field(description="截止日不晚於這天，YYYY-MM-DD；沒提到就留空")
    open_only: bool = Field(description="只要現在還能申請的（開放中或即將開放）就填 true")


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=UTC)


def _nationality_ok(
    scope: InstrumentedAttribute[str], countries: InstrumentedAttribute[list[str]], nationality: str
) -> ColumnElement[bool]:
    """國籍範圍的判斷：全部可以；列出的要包含；排除的不能包含（ADR-043、047）。"""
    listed = literal(nationality) == any_(countries)
    return or_(
        scope == "all",
        and_(scope == "listed", listed),
        and_(scope == "excluded", not_(listed)),
    )


def build_filter_query(filters: Filters, now: datetime) -> Select[tuple[Scholarship, Cycle]]:
    """篩出符合條件的（獎學金, 申請期）；每個申請期一列，依截止時間排序。"""
    query = (
        select(Scholarship, Cycle)
        .join(Cycle, Cycle.scholarship_id == Scholarship.id)
        # 只看代表的那筆（ADR-048）；預估的申請期不是真的日期
        .where(Scholarship.duplicate_of.is_(None), Cycle.estimated.is_(false()))
        .order_by(Cycle.closes_at)
    )
    if filters.nationality:
        # 獎學金沒寫國籍資格（unclear）的也列出來，回答時標待確認
        query = query.where(
            or_(
                Scholarship.nationality_scope == "unclear",
                _nationality_ok(Scholarship.nationality_scope, Scholarship.nationalities, filters.nationality),
            ),
            _nationality_ok(Cycle.nationality_scope, Cycle.nationalities, filters.nationality),
        )
    if filters.degree:
        query = query.where(literal(filters.degree) == any_(Scholarship.degrees))
    if filters.country:
        query = query.where(literal(filters.country) == any_(Scholarship.countries))
    if filters.deadline_after:
        query = query.where(Cycle.closes_at >= _start_of(filters.deadline_after))
    if filters.deadline_before:
        # 截止日當天也算：上限是隔天 0 點
        query = query.where(Cycle.closes_at < _start_of(filters.deadline_before + timedelta(days=1)))
    if filters.open_only:
        query = query.where(Cycle.status.in_(["open", "upcoming"]))
    return query
