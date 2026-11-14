"""R06 Đường 2: yêu cầu đổi ca / nhờ làm phụ giữa ca và duyệt (F06-F). Căn cứ: CĐ-GV, NC-01 C2, CQ05."""
from __future__ import annotations

from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Actor, audit, current_actor, employee_names, month_of, owner_only, today_vn
from ..models import Assignment, Employee, ShiftType, SwapRow, utcnow
from ..services import swaps as sw
from .schedule import payroll_locked

router = APIRouter(prefix="/api/swap-requests")


class SwapBody(BaseModel):
    kind: str
    work_date: date
    shift_code: str
    to_employee_id: int
    reason: str = Field(default="", max_length=500)
    counter_date: date | None = None
    counter_shift: str | None = None
    from_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    to_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class DecisionBody(BaseModel):
    note: str = Field(default="", max_length=500)


def _schedule(db: Session, dates: set[date]) -> dict:
    sch: dict = {}
    for a in db.scalars(select(Assignment).where(Assignment.work_date.in_(dates))):
        sch.setdefault((a.work_date, a.shift_code), []).append(a.employee_id)
    return sch


def _t(s: str | None):
    return time.fromisoformat(s) if s else None


def _domain(r: SwapRow) -> sw.SwapRequest:
    return sw.SwapRequest(r.id, r.kind, r.work_date, r.shift_code, r.from_employee_id, r.to_employee_id, r.reason,
                          r.counter_date, r.counter_shift, _t(r.from_time), _t(r.to_time), r.status, r.decided_by,
                          r.decided_at, r.decision_note)


def _out(r: SwapRow, names: dict) -> dict:
    return {"id": r.id, "kind": r.kind, "work_date": r.work_date.isoformat(), "shift_code": r.shift_code,
            "from_employee_id": r.from_employee_id, "from_name": names.get(r.from_employee_id, "?"),
            "to_employee_id": r.to_employee_id, "to_name": names.get(r.to_employee_id, "?"),
            "counter_date": r.counter_date.isoformat() if r.counter_date else None, "counter_shift": r.counter_shift,
            "from_time": r.from_time, "to_time": r.to_time, "reason": r.reason, "status": r.status,
            "requested_at": r.requested_at.isoformat(), "decision_note": r.decision_note,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None}


@router.get("")
def list_requests(status: str | None = None, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    q = select(SwapRow).order_by(SwapRow.id.desc()).limit(300)
    if status:
        q = q.where(SwapRow.status == status)
    if not actor.is_owner:
        if not actor.employee_id:
            return []
        q = q.where(or_(SwapRow.from_employee_id == actor.employee_id, SwapRow.to_employee_id == actor.employee_id))
    names = employee_names(db)
    return [_out(r, names) for r in db.scalars(q)]


@router.post("")
def create_request(body: SwapBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if not actor.employee_id:
        raise HTTPException(400, "Tài khoản chưa gắn với nhân viên. Nhờ chủ quán liên kết.")
    today = today_vn()
    if body.kind == "full_swap" and body.work_date < today:
        raise HTTPException(422, "Chỉ đổi được ca từ hôm nay trở đi")
    if body.kind == "partial_cover":
        if body.work_date > today:
            raise HTTPException(422, "Khai báo nhờ phụ / vắng giữa ca không được chọn ngày trong tương lai")
        if body.work_date < today - timedelta(days=31):
            raise HTTPException(422, "Chỉ khai báo vắng/phụ giữa ca trong 31 ngày gần nhất")
    to_emp = db.get(Employee, body.to_employee_id)
    if not to_emp or not to_emp.is_active:
        raise HTTPException(422, "Người nhận không hợp lệ")
    dates = {body.work_date} | ({body.counter_date} if body.counter_date else set())
    sch = _schedule(db, dates)
    if db.scalar(select(SwapRow.id).where(SwapRow.status == "pending", SwapRow.work_date == body.work_date,
                                          SwapRow.shift_code == body.shift_code,
                                          SwapRow.from_employee_id == actor.employee_id)):
        raise HTTPException(409, "Đã có yêu cầu đang chờ duyệt cho ca này")
    DEFAULT_PARTIAL_HOURS = {
        "sang": ("09:00", "11:00"),
        "trua": ("13:30", "15:00"),
        "toi": ("18:30", "20:00"),
    }
    from_time = body.from_time
    to_time = body.to_time
    if body.kind == "partial_cover":
        if not (from_time and to_time):
            def_start, def_end = DEFAULT_PARTIAL_HOURS.get(body.shift_code, ("09:00", "11:00"))
            from_time = from_time or def_start
            to_time = to_time or def_end
        t_from, t_to = _t(from_time), _t(to_time)
        if not t_from or not t_to or t_from >= t_to:
            raise HTTPException(422, "Giờ bắt đầu phải trước giờ kết thúc")
        st = db.get(ShiftType, body.shift_code)
        if st and st.start_time and st.end_time:
            st_start, st_end = _t(st.start_time), _t(st.end_time)
            if st_start and st_end and (t_from < st_start or t_to > st_end):
                raise HTTPException(
                    422,
                    f"Khung giờ làm phụ ({from_time}–{to_time}) phải nằm trong khung giờ của {st.name} ({st.start_time}–{st.end_time})"
                )

    try:
        sw.create_request(0, sch, actor.employee_id, body.kind, body.work_date, body.shift_code, body.to_employee_id,
                          body.reason, counter_date=body.counter_date, counter_shift=body.counter_shift,
                          from_time=_t(from_time), to_time=_t(to_time))
    except sw.SwapError as exc:
        raise HTTPException(422, str(exc))
    row = SwapRow(kind=body.kind, work_date=body.work_date, shift_code=body.shift_code,
                  from_employee_id=actor.employee_id, to_employee_id=body.to_employee_id,
                  counter_date=body.counter_date, counter_shift=body.counter_shift,
                  from_time=from_time, to_time=to_time, reason=body.reason)
    db.add(row)
    db.flush()
    audit(db, actor, "create", "swap_request", row.id, None, body.model_dump())
    db.commit()
    return _out(row, employee_names(db))


@router.post("/{rid}/approve")
def approve(rid: int, body: DecisionBody = DecisionBody(), actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    row = db.get(SwapRow, rid, with_for_update=True)  # khóa dòng: hai lần duyệt đồng thời chỉ một lần có hiệu lực
    if not row:
        raise HTTPException(404, "Không có yêu cầu")
    if payroll_locked(db, month_of(row.work_date)):
        raise HTTPException(409, "Lương tháng này đã chốt. Mở khóa lương trước khi duyệt.")
    dates = {row.work_date} | ({row.counter_date} if row.counter_date else set())
    before = _schedule(db, dates)
    after = {k: list(v) for k, v in before.items()}
    req = _domain(row)
    try:
        sw.approve(req, after, actor.id, utcnow(), body.note)
    except sw.SwapError as exc:
        raise HTTPException(409, str(exc))
    if row.kind == "full_swap":  # partial_cover: KHÔNG đổi lịch, KHÔNG đổi lương (D15, D25)
        for key in set(before) | set(after):
            old, new = before.get(key, []), after.get(key, [])
            for emp in set(old) - set(new):
                db.execute(delete(Assignment).where(Assignment.work_date == key[0], Assignment.shift_code == key[1],
                                                    Assignment.employee_id == emp))
            for emp in set(new) - set(old):
                db.add(Assignment(month=month_of(key[0]), work_date=key[0], shift_code=key[1], employee_id=emp, source="swap"))
    row.status, row.decided_by, row.decided_at, row.decision_note = "approved", actor.id or None, req.decided_at, body.note
    audit(db, actor, "approve", "swap_request", row.id, {"status": "pending"}, {"status": "approved", "kind": row.kind})
    db.commit()
    return _out(row, employee_names(db))


@router.post("/{rid}/reject")
def reject(rid: int, body: DecisionBody = DecisionBody(), actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    row = db.get(SwapRow, rid, with_for_update=True)
    if not row:
        raise HTTPException(404, "Không có yêu cầu")
    req = _domain(row)
    try:
        sw.reject(req, actor.id, utcnow(), body.note)
    except sw.SwapError as exc:
        raise HTTPException(409, str(exc))
    row.status, row.decided_by, row.decided_at, row.decision_note = "rejected", actor.id or None, req.decided_at, body.note
    audit(db, actor, "reject", "swap_request", row.id)
    db.commit()
    return _out(row, employee_names(db))


@router.post("/{rid}/cancel")
def cancel(rid: int, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    row = db.get(SwapRow, rid, with_for_update=True)
    if not row:
        raise HTTPException(404, "Không có yêu cầu")
    try:
        sw.cancel(_domain(row), actor.employee_id or -1)
    except sw.SwapError as exc:
        raise HTTPException(409, str(exc))
    row.status = "cancelled"
    audit(db, actor, "cancel", "swap_request", row.id)
    db.commit()
    return _out(row, employee_names(db))
