"""Đăng nhập, first-run setup, tài khoản, cài đặt, nhân viên (E-01, E-02, F00-A, F06-A)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (COOKIE, SETTING_DEFAULTS, Actor, audit, current_actor, get_config, get_setting, owner_only,
                    set_setting)
from ..models import Employee, ShiftType, User, PayRate, SessionToken
from ..security import (LOCK_MINUTES, MAX_FAILED, MIN_PASSWORD, expiry, hash_password, new_token, utcnow,
                        validate_password_strength, verify_password)

router = APIRouter(prefix="/api")


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class SetupBody(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


def _owner_exists(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "owner")) > 0


def _login_cookie(db: Session, response: Response, user: User) -> None:
    raw, h = new_token()
    cfg = get_config()
    db.add(SessionToken(token_hash=h, user_id=user.id, expires_at=expiry(cfg.session_hours)))
    response.set_cookie(COOKIE, raw, max_age=cfg.session_hours * 3600, httponly=True, samesite="lax", path="/")


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    cfg = get_config()
    return {"app_mode": cfg.app_mode, "is_live": cfg.is_live, "flags": cfg.flags,
            "needs_setup": cfg.flags.get("E02_AUTH", True) and not _owner_exists(db),
            "shop_name": get_setting(db, "shop_name"), "pos365_configured": bool(cfg.pos365_base_url),
            "quick_login_enabled": not cfg.is_live}


# C4: Đăng nhập nhanh Demo – server từ chối ở Live
class QuickLoginBody(BaseModel):
    username: str


@router.post("/auth/quick-login")
def quick_login(body: QuickLoginBody, response: Response, db: Session = Depends(get_db)):
    """C4: Chỉ chạy ở Demo. Live luôn từ chối 403."""
    cfg = get_config()
    if cfg.is_live:
        raise HTTPException(403, "Đăng nhập nhanh không có ở bản Live (dữ liệu thật).")
    user = db.scalar(select(User).where(User.username == body.username, User.is_active == True))
    if not user:
        raise HTTPException(404, f"Không tìm thấy tài khoản '{body.username}'")
    _login_cookie(db, response, user)
    db.commit()
    return {"id": user.id, "username": user.username, "display_name": user.display_name,
            "role": user.role, "employee_id": user.employee_id}


@router.post("/auth/setup")
def first_run_setup(body: SetupBody, response: Response, db: Session = Depends(get_db)):
    """First-run Setup: chỉ chạy được khi chưa có chủ quán nào."""
    if _owner_exists(db):
        raise HTTPException(409, "Đã có tài khoản chủ quán")
    if err := validate_password_strength(body.password):
        raise HTTPException(422, err)
    user = User(username=body.username, display_name=body.display_name, role="owner",
                password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    _login_cookie(db, response, user)
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/auth/login")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    bad = HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    if not user or not user.is_active:
        raise bad
    if user.locked_until and user.locked_until > utcnow():
        raise HTTPException(423, f"Tài khoản tạm khóa do nhập sai nhiều lần. Thử lại sau {LOCK_MINUTES} phút")
    if not verify_password(body.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED:
            user.locked_until = utcnow() + timedelta(minutes=LOCK_MINUTES)
            user.failed_attempts = 0
        db.commit()
        raise bad
    user.failed_attempts, user.locked_until = 0, None
    _login_cookie(db, response, user)
    db.commit()
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role,
            "employee_id": user.employee_id}


@router.post("/auth/logout")
def logout(response: Response, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if actor.id:
        for s in db.scalars(select(SessionToken).where(SessionToken.user_id == actor.id)):
            db.delete(s)
        db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(actor: Actor = Depends(current_actor)):
    return {"id": actor.id, "username": actor.username, "display_name": actor.display_name, "role": actor.role,
            "employee_id": actor.employee_id}


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/auth/change-password")
def change_password(body: ChangePassword, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = db.get(User, actor.id)
    if not user or not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Mật khẩu cũ không đúng")
    if err := validate_password_strength(body.new_password):
        raise HTTPException(422, err)
    user.password_hash = hash_password(body.new_password)
    audit(db, actor, "change_password", "user", user.id)
    db.commit()
    return {"ok": True}


# ---------- tài khoản (chủ quán) ----------
class NewUser(SetupBody):
    employee_id: int | None = None
    role: str = "staff"


@router.get("/users")
def list_users(actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    return [{"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role,
             "is_active": u.is_active, "employee_id": u.employee_id}
            for u in db.scalars(select(User).order_by(User.id))]


@router.post("/users")
def create_user(body: NewUser, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    if body.role not in ("owner", "staff"):
        raise HTTPException(422, "Vai trò Quản lý ca và Kế toán chưa được xây (chỉ owner, staff)")
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(409, "Tên đăng nhập đã tồn tại")
    if err := validate_password_strength(body.password):
        raise HTTPException(422, err)
    u = User(username=body.username, display_name=body.display_name, role=body.role, employee_id=body.employee_id,
             password_hash=hash_password(body.password))
    db.add(u)
    db.flush()
    audit(db, actor, "create", "user", u.id, None, {"username": u.username, "role": u.role})
    db.commit()
    return {"id": u.id}


class UserPatch(BaseModel):
    is_active: bool | None = None
    employee_id: int | None = None
    new_password: str | None = Field(default=None, min_length=MIN_PASSWORD, max_length=200)


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserPatch, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Không có tài khoản")
    if body.is_active is not None:
        if u.id == actor.id and body.is_active is False:
            raise HTTPException(400, "Không thể tự khóa tài khoản đang dùng")
        u.is_active = body.is_active
    if "employee_id" in body.model_fields_set:
        u.employee_id = body.employee_id
    if body.new_password:
        if err := validate_password_strength(body.new_password):
            raise HTTPException(422, err)
        u.password_hash = hash_password(body.new_password)
    audit(db, actor, "update", "user", u.id, None, body.model_dump(exclude={"new_password"}, exclude_unset=True))
    db.commit()
    return {"ok": True}


# ---------- nhân viên, ca, lương, cài đặt ----------
class EmployeeBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    is_active: bool = True


@router.get("/employees")
def list_employees(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return [{"id": e.id, "display_name": e.display_name, "is_active": e.is_active}
            for e in db.scalars(select(Employee).order_by(Employee.display_name))]


@router.post("/employees")
def create_employee(body: EmployeeBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    if db.scalar(select(Employee.id).where(func.lower(Employee.display_name) == body.display_name.lower())):
        raise HTTPException(409, "Nhân viên đã tồn tại")
    e = Employee(display_name=body.display_name.strip(), is_active=body.is_active)
    db.add(e)
    db.flush()
    audit(db, actor, "create", "employee", e.id, None, body.model_dump())
    db.commit()
    return {"id": e.id}


@router.put("/employees/{emp_id}")
def update_employee(emp_id: int, body: EmployeeBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    e = db.get(Employee, emp_id)
    if not e:
        raise HTTPException(404, "Không có nhân viên")
    e.display_name, e.is_active = body.display_name.strip(), body.is_active
    audit(db, actor, "update", "employee", e.id, None, body.model_dump())
    db.commit()
    return {"ok": True}


class ShiftBody(BaseModel):
    code: str
    name: str
    hours: float = Field(gt=0, le=24)
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    capacity: int = Field(default=1, ge=1, le=10)


@router.get("/shift-types")
def get_shift_types(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    order = {"sang": 0, "trua": 1, "toi": 2}
    rows = sorted(db.scalars(select(ShiftType)), key=lambda r: order.get(r.code, 9))
    return [{"code": r.code, "name": r.name, "hours": float(r.hours), "start_time": r.start_time,
             "end_time": r.end_time, "capacity": r.capacity} for r in rows]


@router.put("/shift-types")
def put_shift_types(body: list[ShiftBody], actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    parsed_shifts = []
    for b in body:
        if b.code not in ("sang", "trua", "toi"):
            raise HTTPException(422, "Mã ca chỉ gồm sang, trua, toi")
        if not b.start_time or not b.end_time:
            raise HTTPException(422, f"Ca {b.name} không được để trống giờ bắt đầu hoặc kết thúc")
        try:
            sh, sm = map(int, b.start_time.split(":"))
            eh, em = map(int, b.end_time.split(":"))
        except Exception:
            raise HTTPException(422, f"Giờ ca {b.name} sai định dạng HH:MM ({b.start_time} - {b.end_time})")
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        if start_min >= end_min:
            raise HTTPException(422, f"Giờ bắt đầu phải trước giờ kết thúc (Ca {b.name}: {b.start_time} - {b.end_time})")
        parsed_shifts.append((start_min, end_min, b))

    # Kiểm tra ca chồng lấn
    parsed_shifts.sort(key=lambda x: x[0])
    for i in range(len(parsed_shifts) - 1):
        curr_start, curr_end, curr_b = parsed_shifts[i]
        next_start, next_end, next_b = parsed_shifts[i + 1]
        if curr_end > next_start:
            raise HTTPException(422, f"Các ca không được chồng lấn thời gian (Ca {curr_b.name} kết thúc lúc {curr_b.end_time}, Ca {next_b.name} bắt đầu lúc {next_b.start_time})")

    for start_min, end_min, b in parsed_shifts:
        row = db.get(ShiftType, b.code)
        calc_hours = round((end_min - start_min) / 60.0, 2)
        if row is None:
            row = ShiftType(code=b.code, name=b.name, hours=calc_hours)
            db.add(row)
        row.name = b.name
        row.hours = calc_hours
        row.start_time = b.start_time
        row.end_time = b.end_time
        row.capacity = b.capacity

    audit(db, actor, "update", "shift_types", "", None, [b.model_dump() for b in body])
    db.commit()
    return {"ok": True}


class RateBody(BaseModel):
    rate_a: float = Field(ge=0)
    rate_b: float = Field(ge=0)


@router.get("/pay-rates")
def get_pay_rates(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    r = db.scalar(select(PayRate).order_by(PayRate.effective_from.desc(), PayRate.id.desc()))
    return {"rate_a": float(r.rate_a), "rate_b": float(r.rate_b)} if r else {"rate_a": 0, "rate_b": 0}


@router.put("/pay-rates")
@router.post("/pay-rates")
def put_pay_rates(body: RateBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    from datetime import date as _date
    from ..deps import today_vn
    # Lưu mức lương mới có hiệu lực ngay cho các tháng chưa chốt
    eff = min(today_vn().replace(day=1), _date(2026, 1, 1))
    db.add(PayRate(effective_from=eff, rate_a=body.rate_a, rate_b=body.rate_b))
    audit(db, actor, "update", "pay_rates", "", None, body.model_dump())
    db.commit()
    return {"ok": True, "rate_a": float(body.rate_a), "rate_b": float(body.rate_b)}


class SettingsBody(BaseModel):
    duty_require_schedule: bool | None = None
    cluster_fairness_slack: int | None = Field(default=None, ge=0, le=10)
    max_shifts_per_day: int | None = Field(default=None, ge=1, le=3)
    shop_name: str | None = Field(default=None, max_length=80)


@router.get("/settings")
def get_settings(actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    return {k: (get_setting(db, k).lower() in ("1", "true", "yes", "on") if k == "duty_require_schedule"
                else int(get_setting(db, k)) if k in ("cluster_fairness_slack", "max_shifts_per_day")
                else get_setting(db, k)) for k in SETTING_DEFAULTS}


@router.put("/settings")
def put_settings(body: SettingsBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in changes.items():
        old = get_setting(db, k)
        set_setting(db, k, str(v).lower() if isinstance(v, bool) else str(v))
        audit(db, actor, "update", "setting", k, old, v)
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def list_notifications(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    """Tổng hợp thông báo hoạt động mới nhất cho Nhân viên và Chủ quán."""
    from ..models import AttendanceLog, HandoverRow, Ingredient, IngredientStatusRow, PayrollMonth, SwapRow
    from ..services.timeutil import VN_TZ

    shift_label = {"sang": "Ca Sáng", "trua": "Ca Trưa", "toi": "Ca Tối"}
    method_label = {"qr": "Quét QR", "pin": "Mã PIN", "auto_close": "Tự đóng phiên"}
    names = {e.id: e.display_name for e in db.scalars(select(Employee))}
    items: list[dict] = []

    def _iso(dt):
        if dt is None:
            return ""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=VN_TZ).isoformat()
        return dt.astimezone(VN_TZ).isoformat()

    def _hm(dt):
        if dt is None:
            return ""
        d_vn = dt.replace(tzinfo=VN_TZ) if dt.tzinfo is None else dt.astimezone(VN_TZ)
        return d_vn.strftime("%H:%M %d/%m")

    # 1. Điểm danh vào / ra ca
    att_q = select(AttendanceLog).order_by(AttendanceLog.at.desc())
    if not actor.is_owner:
        if actor.employee_id:
            att_q = att_q.where(AttendanceLog.employee_id == actor.employee_id)
        else:
            att_q = att_q.where(AttendanceLog.id < 0)
    for a in db.scalars(att_q.limit(6)):
        emp_name = names.get(a.employee_id, "Nhân viên")
        act_str = "VÀO CA" if a.kind == "in" else "RA CA"
        m_str = method_label.get(a.method or "qr", a.method or "QR")
        items.append({
            "id": f"att-{a.id}",
            "kind": "warn" if a.out_of_schedule else "ok",
            "icon": "🟢" if a.kind == "in" else "🔵",
            "title": (f"Bạn đã điểm danh {act_str} lúc {_hm(a.at)}"
                      if not actor.is_owner else f"{emp_name} đã điểm danh {act_str} lúc {_hm(a.at)}"),
            "detail": f"Hình thức: {m_str}" + (" · Ngoài lịch phân công" if a.out_of_schedule else " · Đúng lịch ca"),
            "at": _iso(a.at),
            "link": "#/home" if not actor.is_owner else "#/attendance_logs",
        })

    # 2. Biên bản giao ca
    for h in db.scalars(select(HandoverRow).order_by(HandoverRow.id.desc()).limit(10)):
        sl = shift_label.get(h.shift_code, h.shift_code)
        d_str = h.business_date.strftime("%d/%m")
        is_mine = (h.giver_id == actor.id) or (h.giver_name == actor.display_name)
        if h.status == "confirmed" and h.confirmed_at:
            if actor.is_owner or is_mine or h.receiver_id == actor.id:
                items.append({
                    "id": f"ho-conf-{h.id}",
                    "kind": "ok",
                    "icon": "✅",
                    "title": f"Phiếu giao ca {sl} ({d_str}) đã được duyệt",
                    "detail": f"Người giao: {h.giver_name} · Người nhận: {h.receiver_name or 'Chủ quán'} ({_hm(h.confirmed_at)})",
                    "at": _iso(h.confirmed_at),
                    "link": "#/handover",
                })
        elif h.status == "draft" and h.unlocked_by_owner:
            if actor.is_owner or is_mine:
                ts = h.submitted_at or h.created_at
                items.append({
                    "id": f"ho-unlock-{h.id}",
                    "kind": "warn",
                    "icon": "🔓",
                    "title": f"Phiếu giao ca {sl} ({d_str}) đã được mở khóa",
                    "detail": "Vui lòng kiểm tra ghi chú, chỉnh sửa và ký gửi lại biên bản.",
                    "at": _iso(ts),
                    "link": "#/handover",
                })
        elif h.status == "submitted":
            if actor.is_owner or not is_mine:
                ts = h.submitted_at or h.created_at
                items.append({
                    "id": f"ho-sub-{h.id}",
                    "kind": "info",
                    "icon": "⇄",
                    "title": f"Phiếu giao ca {sl} ({d_str}) đang chờ xác nhận",
                    "detail": f"Người giao: {h.giver_name} · Thực giao: {int(h.cash_handed):,} đ".replace(",", "."),
                    "at": _iso(ts),
                    "link": "#/handover",
                })

    # 3. Đơn đổi ca / nhờ phụ giữa ca
    sw_q = select(SwapRow).order_by(SwapRow.id.desc())
    if not actor.is_owner:
        if actor.employee_id:
            sw_q = sw_q.where((SwapRow.from_employee_id == actor.employee_id) | (SwapRow.to_employee_id == actor.employee_id))
        else:
            sw_q = sw_q.where(SwapRow.id < 0)
    for s in db.scalars(sw_q.limit(8)):
        sl = shift_label.get(s.shift_code, s.shift_code)
        d_str = s.work_date.strftime("%d/%m")
        kind_str = "Đổi ca" if s.kind == "full_swap" else "Nhờ phụ giữa ca"
        from_n = names.get(s.from_employee_id, "NV")
        to_n = names.get(s.to_employee_id, "NV")
        if s.status == "approved":
            ts = s.decided_at or s.requested_at
            items.append({
                "id": f"sw-app-{s.id}",
                "kind": "ok",
                "icon": "✅",
                "title": f"Đã duyệt đơn {kind_str.lower()} ({sl} · {d_str})",
                "detail": f"{from_n} ↔ {to_n} · Duyệt lúc {_hm(ts)}",
                "at": _iso(ts),
                "link": "#/schedule",
            })
        elif s.status == "rejected":
            ts = s.decided_at or s.requested_at
            items.append({
                "id": f"sw-rej-{s.id}",
                "kind": "bad",
                "icon": "❌",
                "title": f"Đơn {kind_str.lower()} ({sl} · {d_str}) bị từ chối",
                "detail": s.decision_note or f"{from_n} → {to_n}",
                "at": _iso(ts),
                "link": "#/schedule",
            })
        elif s.status == "pending":
            items.append({
                "id": f"sw-pend-{s.id}",
                "kind": "info",
                "icon": "🕒",
                "title": f"Đơn {kind_str.lower()} ({sl} · {d_str}) đang chờ duyệt",
                "detail": f"{from_n} → {to_n}",
                "at": _iso(s.requested_at),
                "link": "#/schedule",
            })

    # 4. Chốt lương (Đã khóa)
    seen_months = set()
    pay_q = select(PayrollMonth).order_by(PayrollMonth.locked_at.desc())
    if not actor.is_owner and actor.employee_id:
        pay_q = pay_q.where(PayrollMonth.employee_id == actor.employee_id)
    for p in db.scalars(pay_q.limit(8)):
        if p.month in seen_months:
            continue
        seen_months.add(p.month)
        items.append({
            "id": f"pay-lock-{p.month}",
            "kind": "ok",
            "icon": "🔒",
            "title": f"Bảng lương tháng {p.month} đã được khóa",
            "detail": (f"Tổng lương của bạn: {int(p.amount):,} đ".replace(",", ".")
                       if not actor.is_owner else f"Đã chốt sổ và khóa đơn giá tháng {p.month}"),
            "at": _iso(p.locked_at),
            "link": "#/payroll",
        })

    # 5. Cảnh báo nguyên liệu đang mở (Sắp hết / Hết)
    ing_names = {i.id: i.name for i in db.scalars(select(Ingredient))}
    for r in db.scalars(
        select(IngredientStatusRow)
        .where(IngredientStatusRow.closed_at.is_(None), IngredientStatusRow.status.in_(("sap_het", "het")))
        .order_by(IngredientStatusRow.reported_at.desc())
        .limit(4)
    ):
        iname = ing_names.get(r.ingredient_id, f"NL #{r.ingredient_id}")
        st_str = "Hết hẳn" if r.status == "het" else "Sắp hết"
        items.append({
            "id": f"ing-{r.id}",
            "kind": "bad" if r.status == "het" else "warn",
            "icon": "⚠️" if r.status == "het" else "📦",
            "title": f"Nguyên liệu {iname}: {st_str}",
            "detail": f"Báo bởi {r.reported_by_name or 'Nhân viên'} lúc {_hm(r.reported_at)}",
            "at": _iso(r.reported_at),
            "link": "#/ingredients",
        })

    items.sort(key=lambda x: x.get("at") or "", reverse=True)
    return items[:20]
