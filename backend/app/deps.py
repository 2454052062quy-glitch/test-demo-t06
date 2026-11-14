"""Phụ thuộc dùng chung: cấu hình, người dùng hiện tại, quyền, cài đặt, nhật ký, tra cứu lịch."""
from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import AppConfig
from .db import get_db
from .models import Assignment, AuditLog, Employee, SessionToken, Setting, User
from .security import token_hash, utcnow
from .services.duty import evaluate_access
from .services.timeutil import VN_TZ

COOKIE = "t06_session"
SETTING_DEFAULTS = {
    "duty_require_schedule": "false",   # D23 (12/11): mặc định tắt ở cả Demo và Live
    "cluster_fairness_slack": "1",      # D24
    "max_shifts_per_day": "2",          # D24
    "shop_name": "Cửa hàng A",
}


@lru_cache
def get_config() -> AppConfig:
    return AppConfig.from_env()


def today_vn() -> date:
    return datetime.now(VN_TZ).date()


def month_of(d: date) -> str:
    return d.strftime("%Y-%m")


def valid_month(month: str) -> str:
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(422, "Tháng phải có dạng YYYY-MM")
    return month


def month_days(month: str) -> list[date]:
    y, m = int(month[:4]), int(month[5:7])
    return [date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]


# ---------- cài đặt ----------
def get_setting(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    return row.value if row else SETTING_DEFAULTS.get(key, "")


def get_bool_setting(db: Session, key: str) -> bool:
    return get_setting(db, key).strip().lower() in ("1", "true", "yes", "on")


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


# ---------- người dùng ----------
@dataclass
class Actor:
    id: int
    username: str
    display_name: str
    role: str
    employee_id: int | None

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


VIRTUAL_OWNER = Actor(0, "demo", "Chế độ Demo (tắt đăng nhập)", "owner", None)


def current_actor(db: Session = Depends(get_db), t06_session: str | None = Cookie(default=None)) -> Actor:
    cfg = get_config()
    if not cfg.flags.get("E02_AUTH", True):
        return VIRTUAL_OWNER  # chỉ có thể xảy ra ở Demo (Live luôn bật, D17)
    if not t06_session:
        raise HTTPException(401, "Chưa đăng nhập")
    sess = db.get(SessionToken, token_hash(t06_session))
    if not sess or sess.expires_at < utcnow():
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Tài khoản không còn hiệu lực")
    return Actor(user.id, user.username, user.display_name, user.role, user.employee_id)


def owner_only(actor: Actor = Depends(current_actor)) -> Actor:
    if not get_config().flags.get("E01_ROLES", True):
        return actor
    if not actor.is_owner:
        raise HTTPException(403, "Chỉ chủ quán được thực hiện thao tác này")
    return actor


def assigned_on(db: Session, employee_id: int | None, work_date: date) -> bool:
    if employee_id is None:
        return False
    return db.scalar(select(Assignment.id).where(Assignment.work_date == work_date,
                                                 Assignment.employee_id == employee_id).limit(1)) is not None


@dataclass
class Access:
    out_of_schedule: bool
    shift_code: str | None


def check_duty_access(db: Session, actor: Actor, permission: str, work_date: date) -> Access:
    """Áp dụng quy tắc 'đang đứng ca' (D23). Mặc định KHÔNG chặn: lưu và gắn cờ out_of_schedule."""
    if not get_config().flags.get("E01_ROLES", True):
        return Access(False, None)
    strict = get_bool_setting(db, "duty_require_schedule")
    assigned = assigned_on(db, actor.employee_id, work_date)
    decision = evaluate_access(actor.role, permission, assigned, strict)
    if not decision.allowed:
        raise HTTPException(403, "Bạn không có phân công ca trong ngày này (chủ quán đang bật chế độ nghiêm ngặt)"
                            if actor.role == "staff" else "Không đủ quyền")
    shift = None
    if get_config().flags.get("E04_SHIFT_TAG", True) and actor.employee_id:
        rows = db.scalars(select(Assignment.shift_code).where(Assignment.work_date == work_date,
                                                              Assignment.employee_id == actor.employee_id)).all()
        shift = rows[0] if len(set(rows)) == 1 else None  # chỉ gắn ca khi xác định được duy nhất
    return Access(decision.out_of_schedule, shift)


def staff_or_owner(actor: Actor = Depends(current_actor)) -> Actor:
    return actor


# ---------- nhật ký ----------
def audit(db: Session, actor: Actor, action: str, entity: str, entity_id="", old=None, new=None) -> None:
    if not get_config().flags.get("E03_AUDIT", True):
        return
    db.add(AuditLog(user_id=actor.id or None, username=actor.username, action=action, entity=entity,
                    entity_id=str(entity_id), old_value=_jsonable(old), new_value=_jsonable(new)))


def _jsonable(v):
    if v is None:
        return None
    return json.loads(json.dumps(v, default=str, ensure_ascii=False))


def employee_names(db: Session) -> dict[int, str]:
    return {e.id: e.display_name for e in db.scalars(select(Employee))}
