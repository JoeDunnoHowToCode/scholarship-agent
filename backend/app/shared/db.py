"""資料庫連線：Base、engine 與 Session（ADR-016 PostgreSQL、ADR-017 同步 Session）。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.shared.settings import settings


class Base(DeclarativeBase):
    """所有資料表類別的父類別；Alembic 從 Base.metadata 找出有哪些表。"""


# engine 管理到資料庫的連線；SessionLocal() 開出一個 Session，代表「一次工作」與它的交易
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(engine)
