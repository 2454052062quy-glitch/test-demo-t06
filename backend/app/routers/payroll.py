"""R06 Giờ công và lương tháng (F06-G). Lương tính theo LỊCH CA ĐÃ DUYỆT, không từ chấm công QR."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Actor, audit, current_actor, employee_names, month_days, owner_only, valid_month
from ..models import Assignment, PayRate, PayrollMonth, ScheduleMonth, ShiftType, SwapRow
from ..services.payroll import DEFAULT_HOURS, compute_payroll

router = APIRouter(prefix="/api/payroll")


def month_payroll(db: Session, month: str) -> dict:
    """Trả {'rows': [...], 'locked': bool, 'rate_a': float, 'rate_b': float, ...}. Dùng chung cho màn hình lương và báo cáo lãi/lỗ."""
    days = month_days(month)
    rate = db.scalar(select(PayRate).where(PayRate.effective_from <= days[-1])
                     .order_by(PayRate.effective_from.desc(), PayRate.id.desc())) or \
        db.scalar(select(PayRate).order_by(PayRate.effective_from.desc(), PayRate.id.desc()))
    a, b = (int(float(rate.rate_a)), int(float(rate.rate_b))) if rate else (0, 0)
    locked = list(db.scalars(select(PayrollMonth).where(PayrollMonth.month == month)))
    if locked:
        # E1: lấy đơn giá đã lưu khi chốt (nếu có), ngược lại dùng rate hiện tại
        rate_a_at_lock = locked[0].rate_a_at_lock if locked[0].rate_a_at_lock is not None else a
        rate_b_at_lock = locked[0].rate_b_at_lock if locked[0].rate_b_at_lock is not None else b
        locked_at = locked[0].locked_at.isoformat() if getattr(locked[0], "locked_at", None) else None
        return {"locked": True, "locked_at": locked_at,
                "rate_a": a, "rate_b": b,
                "rate_a_at_lock": rate_a_at_lock, "rate_b_at_lock": rate_b_at_lock,
                "rate_configured": rate is not None or (rate_a_at_lock > 0 or rate_b_at_lock > 0),
                "rows": [{"employee_id": r.employee_id, "n_sang": r.n_sang, "n_trua": r.n_trua,
                          "n_toi": r.n_toi, "amount": r.amount,
                          "rate_a_at_lock": r.rate_a_at_lock if r.rate_a_at_lock is not None else rate_a_at_lock,
                          "rate_b_at_lock": r.rate_b_at_lock if r.rate_b_at_lock is not None else rate_b_at_lock}
                         for r in locked]}
    hours = {r.code: r.hours for r in db.scalars(select(ShiftType))}
    hours = {k: hours.get(k, v) for k, v in DEFAULT_HOURS.items()}
    assigns = [(x.work_date, x.shift_code, x.employee_id) for x in
               db.scalars(select(Assignment).where(Assignment.month == month))]
    res = compute_payroll(assigns, a, b, hours)
    return {"locked": False, "locked_at": None,
            "rate_a": a, "rate_b": b,
            "rate_a_at_lock": None, "rate_b_at_lock": None,
            "rate_configured": rate is not None and (a > 0 or b > 0),
            "rows": [{"employee_id": e, "n_sang": v["n_sang"], "n_trua": v["n_trua"], "n_toi": v["n_toi"],
                      "amount": int(v["amount"])} for e, v in res.items()]}


def month_flags(db: Session, month: str) -> list[dict]:
    """Cờ "phụ giữa ca / vắng nửa ca" đã duyệt trong tháng. Chỉ để chủ quán tự cộng/trừ tay (D25): không có trường tiền."""
    names = employee_names(db)
    out = []
    for r in db.scalars(select(SwapRow).where(SwapRow.kind == "partial_cover", SwapRow.status == "approved")
                        .order_by(SwapRow.work_date, SwapRow.shift_code)):
        if r.work_date.strftime("%Y-%m") != month:
            continue
        out.append({"work_date": r.work_date.isoformat(), "shift_code": r.shift_code,
                    "from_employee_id": r.from_employee_id, "from_name": names.get(r.from_employee_id, "?"),
                    "cover_employee_id": r.to_employee_id, "cover_name": names.get(r.to_employee_id, "?"),
                    "from_time": r.from_time, "to_time": r.to_time, "reason": r.reason})
    return out


@router.get("/{month}")
def get_payroll(month: str, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    valid_month(month)
    sm = db.get(ScheduleMonth, month)
    data = month_payroll(db, month)
    names = employee_names(db)
    rows = [dict(r, name=names.get(r["employee_id"], "?")) for r in data["rows"]]
    flags = month_flags(db, month)
    base_meta = {
        "month": month,
        "locked": data["locked"],
        "locked_at": data.get("locked_at"),
        "rate_a": data.get("rate_a", 0),
        "rate_b": data.get("rate_b", 0),
        "rate_a_at_lock": data.get("rate_a_at_lock"),
        "rate_b_at_lock": data.get("rate_b_at_lock"),
        "rate_configured": data.get("rate_configured", True),
    }
    if not actor.is_owner:
        if not actor.employee_id:
            raise HTTPException(400, "Tài khoản chưa gắn với nhân viên. Nhờ chủ quán liên kết.")
        if not data["locked"] and not (sm and sm.status == "published"):
            return {**base_meta, "rows": [], "total": 0, "flags": [], "note": "Lịch tháng chưa công bố"}
        rows = [r for r in rows if r["employee_id"] == actor.employee_id]  # D16: chỉ xem lương của mình
        flags = [f for f in flags if actor.employee_id in (f["from_employee_id"], f["cover_employee_id"])]
    return {**base_meta, "rows": sorted(rows, key=lambda r: r["name"]),
            "total": sum(r["amount"] for r in rows), "flags": flags}


@router.post("/{month}/lock")
def lock(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    data = month_payroll(db, month)
    if data["locked"]:
        raise HTTPException(409, "Tháng này đã chốt")
    if not data["rows"]:
        raise HTTPException(422, "Chưa có ca nào trong tháng để chốt lương")
    # E1: lưu hai đơn giá tại thời điểm chốt
    rate = db.scalar(select(PayRate).where(PayRate.effective_from <= date.today())
                     .order_by(PayRate.effective_from.desc(), PayRate.id.desc())) or \
        db.scalar(select(PayRate).order_by(PayRate.effective_from.asc(), PayRate.id.asc()))
    rate_a = int(float(rate.rate_a)) if rate else 0
    rate_b = int(float(rate.rate_b)) if rate else 0
    for r in data["rows"]:
        db.add(PayrollMonth(month=month, employee_id=r["employee_id"], n_sang=r["n_sang"], n_trua=r["n_trua"],
                            n_toi=r["n_toi"], amount=r["amount"], locked_by=actor.id or None,
                            rate_a_at_lock=rate_a, rate_b_at_lock=rate_b))
    audit(db, actor, "lock", "payroll", month, None, {"total": sum(r["amount"] for r in data["rows"]),
                                                       "rate_a": rate_a, "rate_b": rate_b})
    db.commit()
    return {"ok": True}


@router.delete("/{month}/lock")
def unlock(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    db.execute(delete(PayrollMonth).where(PayrollMonth.month == month))
    audit(db, actor, "unlock", "payroll", month)
    db.commit()
    return {"ok": True}
