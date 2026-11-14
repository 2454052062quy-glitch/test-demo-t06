"""R03 Giao ca (F03-A/B/C). D01: chỉ lưu số nhân viên nhập + lý do, KHÔNG tự tính tiền két."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (Actor, audit, check_duty_access, current_actor, employee_names, month_days, owner_only,
                    today_vn, valid_month)
from ..models import Assignment, HandoverRow, PosOrder, ScheduleMonth, utcnow
from ..services import handover as ho

router = APIRouter(prefix="/api/handovers")


class HandoverBody(BaseModel):
    business_date: date
    shift_code: str
    pos_revenue_entered: int = Field(ge=0, default=0)
    transfer_total: int = Field(ge=0, default=0)
    shortage_refund: int = 0
    extra: int = 0
    cash_handed: int = Field(ge=0, default=0)
    note: str = Field(default="", max_length=1000)
    submit: bool = False


class ConfirmBody(BaseModel):
    action: str = "confirm"  # confirm | review
    note: str = Field(default="", max_length=500)


def _ref(db: Session, d: date, shift_code: str | None = None) -> int:
    """D3: Tổng doanh thu theo ngày, hoặc theo ca nếu có shift_code và giờ ca được cấu hình."""
    from ..models import ShiftType
    from ..services.timeutil import VN_TZ
    from datetime import datetime

    if d > today_vn():
        return 0
    if shift_code:
        st = db.get(ShiftType, shift_code)
        if st and st.start_time and st.end_time:
            # Lọc theo giờ tạo đơn (created_at theo giờ VN)
            start_h, start_m = map(int, st.start_time.split(":"))
            end_h, end_m = map(int, st.end_time.split(":"))
            start_dt = datetime(d.year, d.month, d.day, start_h, start_m, tzinfo=VN_TZ)
            end_dt = datetime(d.year, d.month, d.day, end_h, end_m, tzinfo=VN_TZ)
            # Đơn ngoài mọi ca: gán ca gần nhất (D3: chọn cách gán cho ca gần nhất theo giờ bắt đầu)
            return int(db.scalar(select(func.coalesce(func.sum(PosOrder.paid), 0))
                                 .where(PosOrder.business_date == d,
                                        PosOrder.created_at >= start_dt,
                                        PosOrder.created_at < end_dt)))
    return int(db.scalar(select(func.coalesce(func.sum(PosOrder.paid), 0)).where(PosOrder.business_date == d)))


def _expected_receiver_name(db: Session, d: date, shift_code: str, giver_name: str, names: dict[int, str] | None = None) -> str:
    """Xác định người nhận ca dự kiến theo lịch phân công để hiển thị rõ ràng khi chờ nhận."""
    if names is None:
        names = employee_names(db)
    next_shifts = {"sang": ["trua", "toi"], "trua": ["toi"], "toi": []}.get(shift_code, [])
    for ns in next_shifts:
        eids = list(db.scalars(select(Assignment.employee_id).where(Assignment.work_date == d, Assignment.shift_code == ns)))
        cand = [names.get(eid, "") for eid in eids if names.get(eid, "") and names.get(eid, "") != giver_name]
        if cand:
            return ", ".join(cand)
    return "Chủ quán"


def _out(r: HandoverRow, db: Session | None = None, names: dict[int, str] | None = None) -> dict:
    d = {c.name: (getattr(r, c.name).isoformat() if hasattr(getattr(r, c.name), "isoformat") else getattr(r, c.name))
         for c in r.__table__.columns}
    if db is not None:
        d["expected_receiver_name"] = r.receiver_name or _expected_receiver_name(db, r.business_date, r.shift_code, r.giver_name, names)
    else:
        d["expected_receiver_name"] = r.receiver_name or "Chủ quán"
    return d


def _domain(r: HandoverRow) -> ho.Handover:
    return ho.Handover(r.business_date, r.shift_code, r.giver_id, r.pos_revenue_entered, r.transfer_total,
                       r.shortage_refund, r.extra, r.cash_handed, r.note, r.pos_revenue_ref, r.status,
                       r.submitted_at, r.receiver_id, r.confirmed_at, r.unlocked_by_owner)


def _get(db: Session, hid: int) -> HandoverRow:
    r = db.get(HandoverRow, hid)
    if not r:
        raise HTTPException(404, "Không có biên bản")
    return r


@router.get("/ref")
def revenue_ref(date: date, shift: str | None = None, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    """D3: Tổng doanh thu ngày (hoặc ca) từ R01, để tham chiếu khi nhập biên bản."""
    return {"date": date.isoformat(), "pos_revenue_ref": _ref(db, date, shift),
            "shift": shift}


@router.get("")
def list_handovers(month: str, shift: str | None = None, has_variance: bool = False,
                   actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    valid_month(month)
    days = month_days(month)
    q = select(HandoverRow).where(HandoverRow.business_date.between(days[0], days[-1]))
    if shift:
        q = q.where(HandoverRow.shift_code == shift)
    if has_variance:
        q = q.where((HandoverRow.shortage_refund != 0) | (HandoverRow.extra != 0) | (HandoverRow.note != ""))
    names = employee_names(db)
    return [_out(r, db, names) for r in db.scalars(q.order_by(HandoverRow.business_date.desc(), HandoverRow.id.desc()))]


@router.post("")
def create(body: HandoverBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if body.shift_code not in ho.SHIFTS:
        raise HTTPException(422, "Ca không hợp lệ")
    if body.pos_revenue_entered <= 0 and body.transfer_total <= 0 and body.cash_handed <= 0 and not body.note.strip():
        raise HTTPException(422, "Vui lòng nhập số tiền giao ca (Doanh thu POS, Chuyển khoản hoặc Tiền mặt thực giao) trước khi tạo phiếu")
    if (body.shortage_refund != 0 or body.extra != 0) and not body.note.strip():
        raise HTTPException(422, "Có khoản thiếu/trả hoặc phát sinh thì bắt buộc phải ghi rõ lý do")

    access = check_duty_access(db, actor, "handover.write", body.business_date)

    # Kiểm tra lịch phân công của đúng ca đó để tránh người không đứng ca tạo phiếu giao ca thay
    if not actor.is_owner and actor.employee_id:
        assigned_eids = list(db.scalars(
            select(Assignment.employee_id).where(
                Assignment.work_date == body.business_date,
                Assignment.shift_code == body.shift_code
            )
        ))
        if assigned_eids and actor.employee_id not in assigned_eids:
            names = employee_names(db)
            who = ", ".join(names.get(eid, f"NV#{eid}") for eid in assigned_eids)
            raise HTTPException(
                422,
                f"Ca này theo lịch phân công là của {who}. Bạn không phụ trách ca này nên không thể lập biên bản giao ca."
            )

    dup = db.scalar(select(HandoverRow.id).where(HandoverRow.business_date == body.business_date,
                                                 HandoverRow.shift_code == body.shift_code))
    if dup:
        raise HTTPException(409, f"Ngày này đã có biên bản ca này (mã #{dup}). Vui lòng chọn sửa biên bản hiện có.")
    r = HandoverRow(business_date=body.business_date, shift_code=body.shift_code, giver_id=actor.id,
                    giver_name=actor.display_name, pos_revenue_ref=_ref(db, body.business_date, body.shift_code),
                    out_of_schedule=access.out_of_schedule,
                    **body.model_dump(include={"pos_revenue_entered", "transfer_total", "shortage_refund",
                                               "extra", "cash_handed", "note"}))
    db.add(r)
    db.flush()
    if body.submit:
        d = _domain(r)
        try:
            ho.submit(d, utcnow())
        except ho.HandoverError as exc:
            raise HTTPException(422, str(exc))
        r.status, r.submitted_at = d.status, d.submitted_at
    audit(db, actor, "create", "handover", r.id, None, _out(r, db))
    db.commit()
    return _out(r, db)


@router.put("/{hid}")
def update(hid: int, body: HandoverBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    r = _get(db, hid)
    if not actor.is_owner and r.giver_id != actor.id and r.giver_name != actor.display_name:
        raise HTTPException(403, "Chỉ người lập hoặc chủ quán được sửa")
    if body.pos_revenue_entered <= 0 and body.transfer_total <= 0 and body.cash_handed <= 0 and not body.note.strip():
        raise HTTPException(422, "Vui lòng nhập số tiền giao ca (Doanh thu POS, Chuyển khoản hoặc Tiền mặt thực giao)")
    if (body.shortage_refund != 0 or body.extra != 0) and not body.note.strip():
        raise HTTPException(422, "Có khoản thiếu/trả hoặc phát sinh thì bắt buộc phải ghi rõ lý do")
    old = _out(r, db)
    d = _domain(r)
    changes = body.model_dump(include={"pos_revenue_entered", "transfer_total", "shortage_refund", "extra",
                                       "cash_handed", "note"})
    try:
        ho.edit(d, **changes)
    except ho.HandoverError as exc:
        raise HTTPException(409, str(exc))
    for k, v in changes.items():
        setattr(r, k, v)
    r.pos_revenue_ref = _ref(db, r.business_date, r.shift_code)
    if body.submit:
        r.status = "draft"
        d2 = _domain(r)
        try:
            ho.submit(d2, utcnow())
        except ho.HandoverError as exc:
            raise HTTPException(422, str(exc))
        r.status, r.submitted_at, r.unlocked_by_owner = d2.status, d2.submitted_at, False
    audit(db, actor, "update", "handover", r.id, old, _out(r, db))
    db.commit()
    return _out(r, db)


@router.post("/{hid}/submit")
def submit(hid: int, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    r = _get(db, hid)
    if not actor.is_owner and r.giver_id != actor.id and r.giver_name != actor.display_name:
        raise HTTPException(403, "Chỉ người lập được gửi")
    # D3: tính lại số POS tham chiếu theo ca từ dữ liệu hiện tại khi gửi/gửi lại
    r.pos_revenue_ref = _ref(db, r.business_date, r.shift_code)
    if r.unlocked_by_owner and r.status != "draft":
        r.status = "draft"
    d = _domain(r)
    try:
        ho.submit(d, utcnow())
    except ho.HandoverError as exc:
        raise HTTPException(422, str(exc))
    r.status, r.submitted_at, r.unlocked_by_owner = d.status, d.submitted_at, False
    audit(db, actor, "submit", "handover", r.id)
    db.commit()
    return _out(r, db)


@router.post("/{hid}/confirm")
def confirm(hid: int, body: ConfirmBody | None = None, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    r = _get(db, hid)
    if not actor.is_owner:
        check_duty_access(db, actor, "handover.write", r.business_date)
    action = body.action if body else "confirm"
    review_note = (body.note or "").strip() if body else ""

    if action == "review":
        if not review_note:
            raise HTTPException(422, "Vui lòng nhập ghi chú lý do cần xem lại")
        if r.giver_id == actor.id and not actor.is_owner:
            raise HTTPException(409, "Người giao không thể tự đánh dấu xem lại")
        r.status = "draft"
        r.unlocked_by_owner = True
        r.receiver_id = None
        r.receiver_name = ""
        r.confirmed_at = None
        tag = f"[Yêu cầu xem lại - {actor.display_name}: {review_note}]"
        r.note = f"{r.note} | {tag}".strip(" |") if r.note else tag
        audit(db, actor, "review", "handover", r.id, None, {"note": review_note})
        db.commit()
        return _out(r, db)

    if r.giver_name == actor.display_name and not actor.is_owner:
        raise HTTPException(409, "Người giao không được tự xác nhận biên bản của chính mình")
    d = _domain(r)
    try:
        ho.confirm(d, actor.id, utcnow())
    except ho.HandoverError as exc:
        raise HTTPException(409, str(exc))
    r.status, r.receiver_id, r.receiver_name, r.confirmed_at = d.status, actor.id, actor.display_name, d.confirmed_at
    if review_note:
        tag = f"[Ghi chú nhận ca - {actor.display_name}: {review_note}]"
        r.note = f"{r.note} | {tag}".strip(" |") if r.note else tag
    audit(db, actor, "confirm", "handover", r.id)
    db.commit()
    return _out(r, db)


@router.post("/{hid}/unlock")
def unlock(hid: int, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    r = _get(db, hid)
    r.unlocked_by_owner = True
    r.status = "draft"
    r.receiver_id = None
    r.receiver_name = ""
    r.confirmed_at = None
    audit(db, actor, "unlock", "handover", r.id)
    db.commit()
    return _out(r, db)
