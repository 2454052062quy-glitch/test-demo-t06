"""Điểm vào FastAPI. Nginx (frontend) chuyển /api sang đây."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from .db import Base, SessionLocal, engine
from .deps import get_config
from . import models  # noqa: F401  (đăng ký bảng)
from .routers import attendance, auth, finance, handovers, payroll, pos, purchases, schedule, swaps
from .seed import ensure_defaults, seed_demo


def wait_for_db(tries: int = 40) -> None:
    for _ in range(tries):
        try:
            with engine.connect() as c:
                c.execute(text("select 1"))
            return
        except Exception:
            time.sleep(1.5)
    raise RuntimeError("Không kết nối được CSDL. Kiểm tra DB_HOST/DB_PASSWORD và container db.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cfg = get_config()
    wait_for_db()
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE attendance_logs ADD COLUMN IF NOT EXISTS method VARCHAR(20) DEFAULT 'qr'"))
        conn.execute(text("ALTER TABLE attendance_logs ADD COLUMN IF NOT EXISTS auto_closed BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE attendance_logs ADD COLUMN IF NOT EXISTS note TEXT DEFAULT ''"))
    with SessionLocal() as db:
        ensure_defaults(db, cfg)
        seed_demo(db, cfg)
    yield


app = FastAPI(title="T06 - Hệ thống quản lý Cửa hàng A", lifespan=lifespan)
for r in (auth, pos, handovers, purchases, schedule, swaps, payroll, finance, attendance):
    app.include_router(r.router)
