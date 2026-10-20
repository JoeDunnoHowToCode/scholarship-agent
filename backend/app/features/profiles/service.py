"""個人資料的讀寫（ADR-021、055）：所有函式都要 user_id，第一版固定為 1。"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.profiles.models import Profile
from app.features.scholarships import countries
from app.features.scholarships.schemas import Degree

CURRENT_USER_ID = 1  # ADR-021：第一版只有使用者本人


class ProfileIn(BaseModel):
    """API 與指令收到的個人資料；國籍、想讀的學位必填，其他選填（ADR-055）。"""

    nationality: str = Field(description="國籍，ISO 3166-1 兩碼國碼，例如 TW")
    target_degree: Degree = Field(description="想讀的學位")
    current_major: str | None = Field(default=None, description="目前科系（選填）")
    target_fields: list[str] = Field(default_factory=list, description="想讀的領域（選填）")
    target_countries: list[str] = Field(default_factory=list, description="想去的國家國碼（選填）")

    @field_validator("nationality")
    @classmethod
    def _nationality_is_a_code(cls, value: str) -> str:
        code = countries.valid_code(value)
        if code is None:
            raise ValueError(f"{value} 不是 ISO 3166-1 兩碼國碼（例如台灣是 TW）")
        return code

    @field_validator("target_countries")
    @classmethod
    def _countries_are_codes(cls, value: list[str]) -> list[str]:
        valid, invalid = countries.clean_codes(value)
        if invalid:
            raise ValueError(f"不是國碼：{', '.join(invalid)}")
        return valid


class ProfileOut(ProfileIn):
    """API 回傳的個人資料：多了版本號與更新時間。資料表物件不直接回傳（CLAUDE.md）。"""

    version: int
    updated_at: datetime


def get_profile(session: Session, user_id: int) -> Profile | None:
    return session.scalars(select(Profile).where(Profile.user_id == user_id)).first()


def to_out(row: Profile) -> ProfileOut:
    return ProfileOut(
        nationality=row.nationality,
        target_degree=row.target_degree,
        current_major=row.current_major,
        target_fields=list(row.target_fields),
        target_countries=list(row.target_countries),
        version=row.version,
        updated_at=row.updated_at,
    )


def save_profile(session: Session, user_id: int, data: ProfileIn) -> Profile:
    """新增或更新；內容真的變了，版本號才加一（評分會依版本號判斷要不要重算）。"""
    row = get_profile(session, user_id)
    values = data.model_dump()
    if row is None:
        row = Profile(user_id=user_id, version=1, updated_at=datetime.now(UTC), **values)
        session.add(row)
    elif any(getattr(row, key) != value for key, value in values.items()):
        for key, value in values.items():
            setattr(row, key, value)
        row.version += 1
        row.updated_at = datetime.now(UTC)
    session.flush()
    return row
