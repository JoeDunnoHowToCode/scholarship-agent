"""sources picked_at

Revision ID: c3a9d58e2f41
Revises: b7e2c41d9a10
Create Date: 2026-11-20 07:05:00

ADR-119：AI 上次從首頁挑子頁的時間。沒找到日期時重挑子頁，每個來源最多 30 天一次。
手寫：每日檢查正在跑，先加欄位、再改資料表類別。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3a9d58e2f41'
down_revision: str | Sequence[str] | None = 'b7e2c41d9a10'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('picked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('sources', 'picked_at')
