"""Kết nối CSDL PostgreSQL. Trong Docker: DB_HOST=db, cổng nội bộ 5432 (cổng ngoài là DB_PORT)."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    user, pw = os.environ.get("DB_USER", "t06"), os.environ.get("DB_PASSWORD", "")
    host, name = os.environ.get("DB_HOST", "db"), os.environ.get("DB_NAME", "t06_pos_db")
    port = os.environ.get("DB_INTERNAL_PORT", "5432")
    return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{name}"


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
