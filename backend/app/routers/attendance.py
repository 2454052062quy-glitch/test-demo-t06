"""E-09 Chấm công máy quầy: QR one-time + PIN dự phòng + phiên kiosk + auto-close."""
from __future__ import annotations

import io
import json
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    COOKIE, Actor, assigned_on, audit, current_actor, get_config,
    get_setting, month_days, owner_only, set_setting, today_vn, valid_month,
)
from ..models import AttendanceLog, Employee, KioskQrToken, PosKioskSession, SessionToken, User
from ..security import expiry, new_token, utcnow
from ..services.attendance import (
    QR_TTL_SECONDS, auto_close_hours, hash_pin, is_token_expired, make_qr_token, next_kind,
    qr_expires_at, should_auto_close, valid_pin, verify_pin,
)

router = APIRouter(prefix="/api/attendance")

AUTO_CLOSE_HOURS = auto_close_hours()


def _enabled() -> None:
    if not get_config().flags.get("E09_QR_ATTENDANCE", False):
        raise HTTPException(404, "Chấm công QR đang tắt (E09_QR_ATTENDANCE)")


def _kiosk_registered(kiosk_id: str, db: Session) -> bool:
    raw = get_setting(db, "registered_kiosk_ids")
    ids = [x.strip() for x in raw.split(",") if x.strip()]
    return kiosk_id in ids


def _register_kiosk(kiosk_id: str, db: Session) -> None:
    raw = get_setting(db, "registered_kiosk_ids")
    ids = [x.strip() for x in raw.split(",") if x.strip()]
    if kiosk_id not in ids:
        ids.append(kiosk_id)
        set_setting(db, "registered_kiosk_ids", ",".join(ids))


def _login_kiosk_cookie(db: Session, response: Response, user: User) -> None:
    raw, h = new_token()
    cfg = get_config()
    db.add(SessionToken(token_hash=h, user_id=user.id, expires_at=expiry(cfg.session_hours)))
    response.set_cookie(COOKIE, raw, max_age=cfg.session_hours * 3600, httponly=True, samesite="lax", path="/")


def _get_active_session(kiosk_id: str, db: Session) -> PosKioskSession | None:
    return db.scalar(
        select(PosKioskSession)
        .where(PosKioskSession.kiosk_id == kiosk_id, PosKioskSession.closed_at.is_(None))
        .order_by(PosKioskSession.id.desc())
    )


def _auto_close_session_if_needed(session: PosKioskSession, reason: str, db: Session, now: datetime) -> AttendanceLog | None:
    session.closed_at = now
    session.close_reason = reason
    d = now.astimezone(timezone.utc).date()
    off = not assigned_on(db, session.employee_id, d)
    log = AttendanceLog(
        employee_id=session.employee_id,
        work_date=d,
        kind="out",
        at=now,
        out_of_schedule=off,
        method="auto_close",
        auto_closed=True,
        note="Tự động đóng phiên",
    )
    db.add(log)
    db.flush()
    session.attendance_out_id = log.id
    return log


# ─── 1. Đăng ký & kiểm tra máy quầy ───

class RegisterKioskBody(BaseModel):
    kiosk_id: str = Field(min_length=4, max_length=80)
    label: str = Field(default="Máy quầy", max_length=80)


@router.post("/kiosk/register")
def register_kiosk(body: RegisterKioskBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    _enabled()
    _register_kiosk(body.kiosk_id, db)
    raw_labels = get_setting(db, "kiosk_labels")
    labels = {}
    try:
        labels = json.loads(raw_labels) if raw_labels else {}
    except Exception:
        pass
    labels[body.kiosk_id] = body.label
    set_setting(db, "kiosk_labels", json.dumps(labels, ensure_ascii=False))
    audit(db, actor, "create", "kiosk", body.kiosk_id, None, {"label": body.label})
    db.commit()
    return {"ok": True, "kiosk_id": body.kiosk_id}


@router.get("/kiosk/list")
def list_kiosks(actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    _enabled()
    raw = get_setting(db, "registered_kiosk_ids")
    ids = [x.strip() for x in raw.split(",") if x.strip()]
    raw_labels = get_setting(db, "kiosk_labels")
    labels = {}
    try:
        labels = json.loads(raw_labels) if raw_labels else {}
    except Exception:
        pass
    return [{"kiosk_id": k, "label": labels.get(k, k)} for k in ids]


@router.post("/kiosk/auto-register-demo")
def auto_register_demo(body: RegisterKioskBody, db: Session = Depends(get_db)):
    """Chỉ ở bản Demo: tự động đăng ký kiosk khi bật nhanh chế độ máy quầy."""
    _enabled()
    cfg = get_config()
    if cfg.is_live:
        raise HTTPException(403, "Chỉ khả dụng ở chế độ Demo")
    _register_kiosk(body.kiosk_id, db)
    db.commit()
    return {"ok": True, "kiosk_id": body.kiosk_id}


@router.get("/kiosk/employees")
def list_kiosk_employees(db: Session = Depends(get_db)):
    """Danh sách nhân viên hiển thị tại màn hình chọn tên nhập PIN trên Kiosk."""
    _enabled()
    rows = db.scalars(
        select(User)
        .where(User.is_active == True, User.employee_id.is_not(None))
        .order_by(User.display_name.asc())
    )
    return [{"id": u.id, "display_name": u.display_name, "employee_id": u.employee_id} for u in rows]


def _qr_purpose(token: str) -> str | None:
    if token.startswith("in_"):
        return "in"
    if token.startswith("out_"):
        return "out"
    return None


# ─── 2. Tạo mã QR tại máy quầy ───

class CreateQrBody(BaseModel):
    kiosk_id: str = Field(min_length=4, max_length=80)
    base_url: str = Field(default="", max_length=200)
    purpose: str = Field(default="auto", pattern="^(auto|in|out)$")


@router.post("/kiosk/qr")
def create_kiosk_qr(body: CreateQrBody, db: Session = Depends(get_db)):
    _enabled()
    cfg = get_config()
    # Ở Live: bắt buộc kiosk phải được chủ quán đăng ký trước
    if cfg.is_live and not _kiosk_registered(body.kiosk_id, db):
        raise HTTPException(403, "Trình duyệt này chưa được đăng ký làm Máy quầy. Hãy đăng ký ở trang Cài đặt.")

    now = utcnow()
    raw = make_qr_token()
    token = f"{body.purpose}_{raw[:44]}" if body.purpose in ("in", "out") else raw[:48]
    expires_at = qr_expires_at(now)

    db.add(KioskQrToken(token=token, kiosk_id=body.kiosk_id, created_at=now, expires_at=expires_at))
    db.commit()

    client_base = (body.base_url or "").strip().rstrip("/")
    is_local = (not client_base) or ("localhost" in client_base) or ("127.0.0.1" in client_base)
    if cfg.qr_base_url and is_local:
        base = cfg.qr_base_url.rstrip("/")
    elif client_base:
        base = client_base
    else:
        base = cfg.qr_base_url or "http://localhost:3000"
    url = f"{base}/attendance/scan?t={token}"

    svg = ""
    try:
        import segno
        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2)
        svg = buf.getvalue().decode("utf-8")
    except Exception:
        pass

    return {
        "token": token,
        "url": url,
        "svg": svg,
        "expires_in": QR_TTL_SECONDS,
        "kiosk_id": body.kiosk_id,
    }


# ─── 3. Máy quầy poll trạng thái QR ───

@router.get("/kiosk/qr/status")
def get_qr_status(token: str, kiosk_id: str, db: Session = Depends(get_db)):
    _enabled()
    row = db.scalar(select(KioskQrToken).where(KioskQrToken.token == token))
    if not row:
        raise HTTPException(404, "Token không tồn tại")
    if row.kiosk_id != kiosk_id:
        raise HTTPException(403, "Token không thuộc kiosk này")

    now = utcnow()
    if is_token_expired(row.expires_at, now) and not row.confirmed_by:
        return {"confirmed": False, "expired": True}

    if not row.confirmed_by:
        return {"confirmed": False, "expired": False}

    user = db.get(User, row.confirmed_by)
    emp = db.get(Employee, user.employee_id) if user and user.employee_id else None
    return {
        "confirmed": True,
        "expired": False,
        "kind": row.confirmed_kind,
        "user_id": user.id if user else None,
        "username": user.username if user else "",
        "display_name": user.display_name if user else "",
        "employee_name": emp.display_name if emp else (user.display_name if user else ""),
        "employee_id": user.employee_id if user else None,
    }


# ─── 4. Xem trước & Xác nhận trên điện thoại ───

@router.get("/mobile/preview")
def mobile_preview(token: str, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    """Điện thoại kiểm tra QR token trước khi hiện màn hình xác nhận."""
    _enabled()
    if not actor.employee_id:
        raise HTTPException(400, "Tài khoản của bạn chưa được gắn với hồ sơ nhân viên.")

    now = utcnow()
    row = db.scalar(select(KioskQrToken).where(KioskQrToken.token == token))
    if not row:
        raise HTTPException(404, "Mã QR không tồn tại hoặc đã bị hủy.")
    if row.used:
        raise HTTPException(422, "Mã QR này đã được sử dụng. Hãy quét mã mới trên màn hình máy quầy.")
    if is_token_expired(row.expires_at, now):
        raise HTTPException(422, "Mã QR đã hết hạn (quá 2 phút). Hãy quét mã mới trên màn hình máy quầy.")

    d = today_vn()
    forced = _qr_purpose(row.token)
    if forced:
        kind = forced
    else:
        last = db.scalar(
            select(AttendanceLog)
            .where(AttendanceLog.employee_id == actor.employee_id, AttendanceLog.work_date == d)
            .order_by(AttendanceLog.id.desc())
        )
        kind = next_kind(last.kind if last else None)
    off = not assigned_on(db, actor.employee_id, d)
    emp = db.get(Employee, actor.employee_id)

    action_text = "đăng nhập vào máy quầy" if kind == "in" else "tan ca"
    return {
        "valid": True,
        "kind": kind,
        "employee_name": emp.display_name if emp else actor.display_name,
        "action_text": action_text,
        "out_of_schedule": off,
    }


class MobileConfirmBody(BaseModel):
    token: str


@router.post("/mobile/confirm")
def mobile_confirm(body: MobileConfirmBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    _enabled()
    if not actor.employee_id:
        raise HTTPException(400, "Tài khoản của bạn chưa được gắn với hồ sơ nhân viên.")

    now = utcnow()
    row = db.scalar(select(KioskQrToken).where(KioskQrToken.token == body.token))
    if not row:
        raise HTTPException(404, "Mã QR không hợp lệ.")
    if row.used:
        raise HTTPException(422, "Mã QR này đã được sử dụng. Hãy quét mã mới trên máy quầy.")
    if is_token_expired(row.expires_at, now):
        raise HTTPException(422, "Mã QR đã hết hạn (quá 2 phút). Hãy quét mã mới trên máy quầy.")

    d = today_vn()
    forced = _qr_purpose(row.token)
    if forced:
        kind = forced
    else:
        last = db.scalar(
            select(AttendanceLog)
            .where(AttendanceLog.employee_id == actor.employee_id, AttendanceLog.work_date == d)
            .order_by(AttendanceLog.id.desc())
        )
        kind = next_kind(last.kind if last else None)
    off = not assigned_on(db, actor.employee_id, d)

    log = AttendanceLog(
        employee_id=actor.employee_id,
        work_date=d,
        kind=kind,
        at=now,
        out_of_schedule=off,
        method="qr",
        auto_closed=False,
    )
    db.add(log)
    db.flush()

    if kind == "out":
        active_sess = db.scalar(
            select(PosKioskSession).where(
                PosKioskSession.kiosk_id == row.kiosk_id,
                PosKioskSession.user_id == actor.id,
                PosKioskSession.closed_at.is_(None),
            )
        )
        if active_sess:
            active_sess.closed_at = now
            active_sess.close_reason = "manual"
            active_sess.attendance_out_id = log.id

    row.used = True
    row.confirmed_by = actor.id
    row.confirmed_at = now
    row.confirmed_kind = kind

    audit(db, actor, "scan", "attendance", actor.employee_id, None, {"kind": kind, "method": "qr"})
    db.commit()

    emp = db.get(Employee, actor.employee_id)
    return {
        "kind": kind,
        "out_of_schedule": off,
        "employee_name": emp.display_name if emp else actor.display_name,
        "log_id": log.id,
    }


# ─── 5. Mở phiên trên máy quầy (tự động đăng nhập vào giao diện nhân viên) ───

class OpenKioskSessionBody(BaseModel):
    kiosk_id: str
    token: str


@router.post("/kiosk/session/open")
def open_kiosk_session(body: OpenKioskSessionBody, response: Response, db: Session = Depends(get_db)):
    _enabled()
    row = db.scalar(select(KioskQrToken).where(KioskQrToken.token == body.token))
    if not row or not row.confirmed_by:
        raise HTTPException(422, "Mã QR chưa được xác nhận trên điện thoại.")
    if row.kiosk_id != body.kiosk_id:
        raise HTTPException(403, "Mã QR không khớp với máy quầy này.")

    user = db.get(User, row.confirmed_by)
    if not user or not user.is_active or not user.employee_id:
        raise HTTPException(400, "Tài khoản nhân viên không hợp lệ.")

    now = utcnow()

    # Xử lý: Nếu phiên trước chưa đóng (hoặc quá 8 tiếng): tự động đóng phiên của người trước
    old_sess = _get_active_session(body.kiosk_id, db)
    if old_sess:
        reason = "next_shift" if old_sess.user_id != user.id else "auto_timeout"
        _auto_close_session_if_needed(old_sess, reason, db, now)

    # Nếu lượt quét là vào ca (in): mở phiên mới & set login cookie để máy quầy đăng nhập
    if row.confirmed_kind == "in":
        att_in = db.scalar(
            select(AttendanceLog)
            .where(AttendanceLog.employee_id == user.employee_id, AttendanceLog.kind == "in")
            .order_by(AttendanceLog.id.desc())
        )
        sess = PosKioskSession(
            kiosk_id=body.kiosk_id,
            user_id=user.id,
            employee_id=user.employee_id,
            opened_at=now,
            attendance_in_id=att_in.id if att_in else None,
        )
        db.add(sess)
        _login_kiosk_cookie(db, response, user)
        db.commit()

        emp = db.get(Employee, user.employee_id)
        return {
            "kind": "in",
            "session_id": sess.id,
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "employee_name": emp.display_name if emp else user.display_name,
            "role": user.role,
            "opened_at": sess.opened_at.isoformat(),
        }
    else:
        # Nếu là tan ca (out): đảm bảo đóng phiên của chính nhân viên này và xóa cookie
        if old_sess and old_sess.user_id == user.id:
            old_sess.closed_at = now
            old_sess.close_reason = "manual"
        response.delete_cookie(COOKIE, path="/")
        db.commit()

        emp = db.get(Employee, user.employee_id)
        return {
            "kind": "out",
            "employee_name": emp.display_name if emp else user.display_name,
        }


# ─── 6. Kiểm tra phiên và đóng ca từ máy quầy ───

@router.get("/kiosk/session")
def get_kiosk_session(kiosk_id: str, db: Session = Depends(get_db)):
    _enabled()
    sess = _get_active_session(kiosk_id, db)
    if not sess:
        return {"active": False}

    now = utcnow()
    if should_auto_close(sess.opened_at, now):
        _auto_close_session_if_needed(sess, "auto_timeout", db, now)
        db.commit()
        return {"active": False, "auto_closed": True}

    user = db.get(User, sess.user_id)
    emp = db.get(Employee, sess.employee_id) if sess.employee_id else None
    return {
        "active": True,
        "session_id": sess.id,
        "user_id": sess.user_id,
        "username": user.username if user else "",
        "display_name": user.display_name if user else "",
        "employee_name": emp.display_name if emp else "",
        "opened_at": sess.opened_at.isoformat(),
        "minutes_active": int((now - sess.opened_at).total_seconds() / 60),
    }


class EndShiftKioskBody(BaseModel):
    kiosk_id: str
    pin: str | None = None  # nếu ra ca nhanh bằng PIN


@router.post("/kiosk/end-shift")
def end_shift_kiosk(body: EndShiftKioskBody, response: Response, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    """Nút Kết thúc ca trên header nhân viên."""
    _enabled()
    sess = _get_active_session(body.kiosk_id, db)
    user_id = sess.user_id if sess else actor.id
    user = db.get(User, user_id)
    if not user or not user.employee_id:
        raise HTTPException(400, "Không tìm thấy phiên làm việc hợp lệ.")

    # Nếu xác nhận bằng PIN
    if body.pin:
        pin_hash = get_setting(db, f"pin_hash_{user.id}")
        if not pin_hash or not verify_pin(body.pin, pin_hash):
            raise HTTPException(401, "Mã PIN không đúng.")

    now = utcnow()
    d = today_vn()
    off = not assigned_on(db, user.employee_id, d)
    method = "pin" if body.pin else "qr"

    log = AttendanceLog(
        employee_id=user.employee_id,
        work_date=d,
        kind="out",
        at=now,
        out_of_schedule=off,
        method=method,
        auto_closed=False,
    )
    db.add(log)
    db.flush()

    if sess:
        sess.closed_at = now
        sess.close_reason = "manual"
        sess.attendance_out_id = log.id

    # Xóa token session đăng nhập của user này
    for s in db.scalars(select(SessionToken).where(SessionToken.user_id == user.id)):
        db.delete(s)
    response.delete_cookie(COOKIE, path="/")

    audit(db, actor, "scan", "attendance", user.employee_id, None, {"kind": "out", "method": method})
    db.commit()

    emp = db.get(Employee, user.employee_id)
    return {
        "ok": True,
        "kind": "out",
        "employee_name": emp.display_name if emp else user.display_name,
    }


# ─── 7. Đăng nhập / Ra ca bằng mã PIN trên máy quầy ───

class PinLoginBody(BaseModel):
    kiosk_id: str
    user_id: int
    pin: str = Field(min_length=4, max_length=6)


@router.post("/kiosk/pin-login")
def kiosk_pin_login(body: PinLoginBody, response: Response, db: Session = Depends(get_db)):
    _enabled()
    cfg = get_config()
    if cfg.is_live and not _kiosk_registered(body.kiosk_id, db):
        raise HTTPException(403, "Trình duyệt này chưa được đăng ký làm Máy quầy.")

    user = db.get(User, body.user_id)
    if not user or not user.is_active or not user.employee_id:
        raise HTTPException(404, "Tài khoản nhân viên không hợp lệ.")

    pin_hash = get_setting(db, f"pin_hash_{user.id}")
    if not pin_hash:
        raise HTTPException(422, f"Nhân viên {user.display_name} chưa được cài mã PIN. Hãy liên hệ chủ quán.")
    if not verify_pin(body.pin, pin_hash):
        raise HTTPException(401, "Mã PIN không đúng.")

    now = utcnow()
    d = today_vn()

    # Kiểm tra phiên cũ trên kiosk
    old_sess = _get_active_session(body.kiosk_id, db)

    # Xác định kind: nếu đang có phiên mở của chính người này thì là "out", ngược lại là "in"
    if old_sess and old_sess.user_id == user.id:
        kind = "out"
    else:
        # Nếu phiên cũ là của người khác: tự động đóng phiên người trước
        if old_sess:
            _auto_close_session_if_needed(old_sess, "next_shift", db, now)
        kind = "in"

    off = not assigned_on(db, user.employee_id, d)
    log = AttendanceLog(
        employee_id=user.employee_id,
        work_date=d,
        kind=kind,
        at=now,
        out_of_schedule=off,
        method="pin",
        auto_closed=False,
    )
    db.add(log)
    db.flush()

    if kind == "in":
        sess = PosKioskSession(
            kiosk_id=body.kiosk_id,
            user_id=user.id,
            employee_id=user.employee_id,
            opened_at=now,
            attendance_in_id=log.id,
        )
        db.add(sess)
        _login_kiosk_cookie(db, response, user)
    else:
        if old_sess:
            old_sess.closed_at = now
            old_sess.close_reason = "manual"
            old_sess.attendance_out_id = log.id
        response.delete_cookie(COOKIE, path="/")

    emp = db.get(Employee, user.employee_id)
    fake_actor = Actor(user.id, user.username, user.display_name, user.role, user.employee_id)
    audit(db, fake_actor, "scan", "attendance", user.employee_id, None, {"kind": kind, "method": "pin"})
    db.commit()

    return {
        "kind": kind,
        "out_of_schedule": off,
        "employee_name": emp.display_name if emp else user.display_name,
        "user_id": user.id,
        "role": user.role,
        "log_id": log.id,
        "opened_at": now.isoformat(),
    }


# ─── 8. Cài đặt PIN cho nhân viên (Chủ quán) ───

class SetPinBody(BaseModel):
    pin: str = Field(min_length=4, max_length=6)


@router.put("/pin/{user_id}")
def set_employee_pin(user_id: int, body: SetPinBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    _enabled()
    if not valid_pin(body.pin):
        raise HTTPException(422, "Mã PIN phải từ 4 đến 6 chữ số.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng.")
    set_setting(db, f"pin_hash_{user_id}", hash_pin(body.pin))
    audit(db, actor, "update", "user", user_id, None, {"pin_updated": True})
    db.commit()
    return {"ok": True}


@router.get("/pin/list")
def list_employee_pins(actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    _enabled()
    users = db.scalars(select(User).where(User.is_active == True).order_by(User.id)).all()
    return [
        {
            "user_id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "employee_id": u.employee_id,
            "has_pin": bool(get_setting(db, f"pin_hash_{u.id}")),
        }
        for u in users
    ]


# ─── 9. Nhật ký chấm công (Chủ quán) ───

@router.get("")
def list_logs(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    _enabled()
    valid_month(month)
    d = month_days(month)
    names = {e.id: e.display_name for e in db.scalars(select(Employee))}
    rows = db.scalars(
        select(AttendanceLog)
        .where(AttendanceLog.work_date.between(d[0], d[-1]))
        .order_by(AttendanceLog.at.desc())
        .limit(1000)
    )
    METHOD_LABEL = {
        "qr": "Quét QR",
        "pin": "Mã PIN",
        "auto_close": "Tự động đóng ca",
    }
    return [
        {
            "id": r.id,
            "employee": names.get(r.employee_id, "?"),
            "work_date": r.work_date.isoformat(),
            "kind": r.kind,
            "at": r.at.isoformat(),
            "out_of_schedule": r.out_of_schedule,
            "method": METHOD_LABEL.get(r.method, r.method or "Quét QR"),
            "auto_closed": r.auto_closed,
            "note": getattr(r, "note", "") or ("Tự động đóng phiên" if r.auto_closed else ""),
        }
        for r in rows
    ]


# ─── 10. Legacy endpoint để tương thích ngược ───

@router.get("/qr")
def qr_legacy(base: str = "", actor: Actor = Depends(owner_only)):
    _enabled()
    cfg = get_config()
    secret = os.environ.get("ATTENDANCE_QR_SECRET", "")
    if len(secret) < 16:
        raise HTTPException(500, "Chưa đặt ATTENDANCE_QR_SECRET (tối thiểu 16 ký tự)")

    final_base = cfg.qr_base_url or base.rstrip("/") or ("http://localhost:3001" if cfg.is_live else "http://localhost:3000")
    from ..services.attendance import make_token
    token = make_token(secret, datetime.now(timezone.utc))
    url = f"{final_base}/attendance/scan?t={token}"

    import segno
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2)
    return {
        "token": token,
        "url": url,
        "svg": buf.getvalue().decode("utf-8"),
        "refresh_seconds": 50,
        "base_url": final_base,
    }


class ScanBody(BaseModel):
    token: str


@router.post("/scan")
def scan_legacy(body: ScanBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    _enabled()
    if not actor.employee_id:
        raise HTTPException(400, "Tài khoản chưa gắn với nhân viên")
    secret = os.environ.get("ATTENDANCE_QR_SECRET", "")
    if len(secret) < 16:
        raise HTTPException(500, "Chưa đặt ATTENDANCE_QR_SECRET")
    from ..services.attendance import verify_token
    if not verify_token(secret, body.token, datetime.now(timezone.utc)):
        raise HTTPException(422, "Mã QR đã hết hạn. Quét lại mã đang hiển thị ở quầy.")
    d = today_vn()
    last = db.scalar(select(AttendanceLog).where(AttendanceLog.employee_id == actor.employee_id,
                                                 AttendanceLog.work_date == d).order_by(AttendanceLog.id.desc()))
    kind = next_kind(last.kind if last else None)
    off = not assigned_on(db, actor.employee_id, d)
    db.add(AttendanceLog(employee_id=actor.employee_id, work_date=d, kind=kind, out_of_schedule=off, method="qr"))
    audit(db, actor, "scan", "attendance", actor.employee_id, None, {"kind": kind})
    db.commit()
    emp = db.get(Employee, actor.employee_id)
    return {"kind": kind, "out_of_schedule": off, "employee_name": emp.display_name if emp else ""}
