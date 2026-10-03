from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_schema() -> None:
    """create_all 之外的轻量补列：老库没有 sellable_days 时自动加上。"""
    insp = inspect(engine)
    if "lanes" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("lanes")}
    if "sellable_days" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lanes ADD COLUMN sellable_days INTEGER"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
