"""scholarships how_to_apply and no_date_reason

Revision ID: b7e2c41d9a10
Revises: 9dfac427b991
Create Date: 2026-11-20 07:00:00

ADR-119：申請方式（取代意思不清的 requires_admission，它先留著，網頁改完再拿掉）與沒有申請期的原因。
手寫（不是自動產生）：每日檢查正在跑，worker 每件工作都讀硬碟上的新程式，所以先加欄位、再改資料表類別。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b7e2c41d9a10'
down_revision: str | Sequence[str] | None = '9dfac427b991'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('scholarships', sa.Column('how_to_apply', sa.String(length=16), nullable=True))
    op.add_column('scholarships', sa.Column('no_date_reason', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('scholarships', 'no_date_reason')
    op.drop_column('scholarships', 'how_to_apply')
