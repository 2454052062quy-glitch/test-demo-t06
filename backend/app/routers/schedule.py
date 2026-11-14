"""R06 Lịch ca: xem, xếp, công bố, nạp file (2 định dạng), khai báo lịch rảnh, gợi ý nháp (F06-B…F, E-13)."""
from __future__ import annotations

import hashlib
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (Actor, audit, current_actor, get_config, get_setting, month_days, month_of, owner_only,
                    valid_month)
from ..models import (Assignment, Availability, Employee, ImportBatch, PayrollMonth, ScheduleMonth, ShiftType, utcnow)
from ..services import schedule_import as si
from ..services.schedule_template import template_bytes
from ..services.scheduler import auto_draft

router = APIRouter(prefix="/api")
MAX_UPLOAD = 5 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHIFTS = ("sang", "trua", "toi")


def payroll_locked(db: Session, month: str) -> bool:
    return db.scalar(select(PayrollMonth.month).where(PayrollMonth.month == month).limit(1)) is not None


def _month_row(db: Session, month: str) -> ScheduleMonth:
    row = db.get(ScheduleMonth, month)
    if row is None:
        row = ScheduleMonth(month=month, status="draft")
        db.add(row)
        db.flush()
    return row


def _capacity(db: Session) -> dict:
    cap = {r.code: r.capacity for r in db.scalars(select(ShiftType))}
    return {s: cap.get(s, 1) for s in SHIFTS}


def _guard_edit(db: Session, month: str) -> None:
    if payroll_locked(db, month):
        raise HTTPException(409, f"Lương tháng {month} đã chốt. Mở khóa lương trước khi sửa lịch.")


@router.get("/schedules/template.xlsx")
def download_template(kind: str = "grid", month: str = "2026-11", actor: Actor = Depends(current_actor)):
    valid_month(month)
    try:
        data = template_bytes(kind, month)
    except ValueError:
        raise HTTPException(422, "kind chỉ nhận grid hoặc flat")
    name = f"mau_lich_ca_{'luoi' if kind == 'grid' else 'phang'}_{month}.xlsx"
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/schedules/{month}")
def get_schedule(month: str, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    valid_month(month)
    sm = db.get(ScheduleMonth, month)
    status = sm.status if sm else "draft"
    names = {e.id: e.display_name for e in db.scalars(select(Employee))}
    rows = []
    if actor.is_owner or status == "published":
        rows = list(db.scalars(select(Assignment).where(Assignment.month == month)
                               .order_by(Assignment.work_date, Assignment.shift_code, Assignment.id)))
    shifts = [{"code": r.code, "name": r.name, "hours": float(r.hours), "start_time": r.start_time,
               "end_time": r.end_time, "capacity": r.capacity} for r in db.scalars(select(ShiftType))]
    shifts.sort(key=lambda s: SHIFTS.index(s["code"]) if s["code"] in SHIFTS else 9)
    return {"month": month, "status": status, "my_employee_id": actor.employee_id, "shift_types": shifts,
            "employees": [{"id": i, "display_name": n} for i, n in names.items()],
            "assignments": [{"id": a.id, "work_date": a.work_date.isoformat(), "shift_code": a.shift_code,
                             "employee_id": a.employee_id, "employee_name": names.get(a.employee_id, "?"),
                             "source": a.source} for a in rows]}


class CellBody(BaseModel):
    work_date: date
    shift_code: str
    employee_ids: list[int] = Field(default_factory=list, max_length=10)


@router.put("/schedules/{month}/cell")
def set_cell(month: str, body: CellBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    if month_of(body.work_date) != month:
        raise HTTPException(422, "Ngày không thuộc tháng này")
    if body.shift_code not in SHIFTS:
        raise HTTPException(422, "Ca không hợp lệ")
    _guard_edit(db, month)
    ids = list(dict.fromkeys(body.employee_ids))
    if ids and len(set(db.scalars(select(Employee.id).where(Employee.id.in_(ids))))) != len(ids):
        raise HTTPException(422, "Có nhân viên không tồn tại")
    names = {e.id: e.display_name for e in db.scalars(select(Employee))}
    # D5: Ràng buộc không ai quá 2 ca/ngày
    for e in ids:
        other_count = db.scalar(select(func.count()).select_from(Assignment).where(
            Assignment.work_date == body.work_date,
            Assignment.shift_code != body.shift_code,
            Assignment.employee_id == e
        )) or 0
        if other_count + 1 > 2:
            raise HTTPException(422, f"Nhân viên '{names.get(e, e)}' đã có {other_count} ca trong ngày {body.work_date.isoformat()}, không được vượt quá 2 ca/ngày (ràng buộc D5)")

    _month_row(db, month)
    old = [a.employee_id for a in db.scalars(select(Assignment).where(
        Assignment.work_date == body.work_date, Assignment.shift_code == body.shift_code))]
    db.execute(delete(Assignment).where(Assignment.work_date == body.work_date,
                                        Assignment.shift_code == body.shift_code))
    for e in ids:
        db.add(Assignment(month=month, work_date=body.work_date, shift_code=body.shift_code, employee_id=e, source="owner"))
    cap = _capacity(db)[body.shift_code]
    audit(db, actor, "set_cell", "schedule", f"{body.work_date}:{body.shift_code}", old, ids)
    db.commit()
    return {"ok": True, "warning": f"Ca này có {len(ids)} người, vượt sức chứa {cap}" if len(ids) > cap else None}


@router.post("/schedules/{month}/publish")
def publish(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    sm = _month_row(db, month)
    sm.status, sm.published_at, sm.published_by = "published", utcnow(), actor.id or None
    audit(db, actor, "publish", "schedule", month)
    db.commit()
    return {"ok": True}


@router.post("/schedules/{month}/unpublish")
def unpublish(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    sm = _month_row(db, month)
    sm.status = "draft"
    audit(db, actor, "unpublish", "schedule", month)
    db.commit()
    return {"ok": True}


@router.post("/schedules/{month}/import")
async def import_schedule(month: str, file: UploadFile = File(...), mapping: str = Form(default=""),
                          actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    _guard_edit(db, month)
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File quá lớn (tối đa 5 MB)")
    name = (file.filename or "").lower()
    try:
        if name.endswith((".xlsx", ".xlsm")):
            ps = si.parse_xlsx(io.BytesIO(data), month)
        elif name.endswith(".csv"):
            ps = si.parse_csv(data, month)
        else:
            raise HTTPException(422, "Chỉ nhận file .xlsx hoặc .csv")
    except si.ScheduleImportError as exc:
        raise HTTPException(422, str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f"Không đọc được file: {type(exc).__name__}")

    emps = {e.id: e.display_name for e in db.scalars(select(Employee).where(Employee.is_active.is_(True)))}
    try:
        manual = {k: int(v) for k, v in json.loads(mapping).items()} if mapping.strip() else {}
    except (ValueError, AttributeError):
        raise HTTPException(422, "mapping phải là JSON {tên trong file: mã nhân viên}")
    mapped, unmapped = si.map_names(ps.raw_names, emps, manual)
    if unmapped:  # không lưu gì cho tới khi ghép đủ (hệ thống không tự đoán tên)
        return {"needs_mapping": True, "unmapped": [{"name": n, "suggestions": s} for n, s in unmapped.items()],
                "employees": [{"id": i, "display_name": n} for i, n in emps.items()], "layout": ps.layout}
    if any(v not in emps for v in mapped.values()):
        raise HTTPException(422, "mapping trỏ tới nhân viên không hợp lệ")

    in_month = [(d, s, n) for d, s, n in ps.assignments if month_of(d) == month]
    skipped_other_month = len(ps.assignments) - len(in_month)
    rows, seen = [], set()
    for d, s, n in in_month:
        key = (d, s, mapped[n])
        if key not in seen:
            seen.add(key)
            rows.append(key)
    _month_row(db, month)
    db.execute(delete(Assignment).where(Assignment.month == month, Assignment.source == "import"))
    for d, s, e in rows:
        db.add(Assignment(month=month, work_date=d, shift_code=s, employee_id=e, source="import"))
    db.add(ImportBatch(month=month, file_name=(file.filename or "")[:200], file_sha256=hashlib.sha256(data).hexdigest(),
                       rows=len(rows), layout=ps.layout, user_id=actor.id or None))
    over = ps.over_capacity(_capacity(db))
    audit(db, actor, "import", "schedule", month, None, {"rows": len(rows), "layout": ps.layout})
    db.commit()
    return {"needs_mapping": False, "layout": ps.layout, "imported": len(rows), "skipped_other_month": skipped_other_month,
            "errors": [{"row": r, "reason": why} for r, why in ps.errors[:50]],
            "over_capacity": [{"date": d.isoformat(), "shift": s} for d, s in over[:50]]}


@router.post("/schedules/{month}/auto-draft")
def make_auto_draft(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    """E-13 (MỞ RỘNG): sinh bản nháp 3 quy tắc cho các ô còn trống; chủ quán chỉnh rồi Công bố."""
    if not get_config().flags.get("E13_AUTO_DRAFT", False):
        raise HTTPException(404, "Chức năng gợi ý lịch nháp đang tắt (E13_AUTO_DRAFT)")
    valid_month(month)
    _guard_edit(db, month)
    _month_row(db, month)
    db.execute(delete(Assignment).where(Assignment.month == month, Assignment.source == "auto_draft"))
    db.flush()
    avail = {(a.employee_id, a.work_date, a.shift_code): bool(a.available)
             for a in db.scalars(select(Availability).where(Availability.month == month))}
    existing: dict = {}
    for a in db.scalars(select(Assignment).where(Assignment.month == month)):
        existing.setdefault((a.work_date, a.shift_code), []).append(a.employee_id)
    emps = [e.id for e in db.scalars(select(Employee).where(Employee.is_active.is_(True)))]
    res = auto_draft(month_days(month), avail, existing, _capacity(db), emps,
                     int(get_setting(db, "cluster_fairness_slack")), int(get_setting(db, "max_shifts_per_day")))
    for d, s, e in res.assignments:
        db.add(Assignment(month=month, work_date=d, shift_code=s, employee_id=e, source="auto_draft"))
    audit(db, actor, "auto_draft", "schedule", month, None, {"assigned": len(res.assignments), "unassigned": len(res.unassigned)})
    db.commit()
    names = {e.id: e.display_name for e in db.scalars(select(Employee))}
    return {"assigned": len(res.assignments), "unassigned": [{"date": d.isoformat(), "shift": s} for d, s in res.unassigned],
            "counts": {names.get(k, str(k)): v for k, v in res.counts.items()}}


# ---------------- khai báo lịch rảnh (F06-C) ----------------
class AvailItem(BaseModel):
    work_date: date
    shift_code: str
    available: bool = True


class AvailBody(BaseModel):
    month: str
    items: list[AvailItem] = Field(max_length=400)
    employee_id: int | None = None  # chỉ chủ quán được khai hộ


@router.get("/availability")
def get_availability(month: str, employee_id: int | None = None, actor: Actor = Depends(current_actor),
                     db: Session = Depends(get_db)):
    valid_month(month)
    q = select(Availability).where(Availability.month == month)
    if actor.is_owner:
        if employee_id:
            q = q.where(Availability.employee_id == employee_id)
    else:
        if not actor.employee_id:
            raise HTTPException(400, "Tài khoản chưa gắn với nhân viên. Nhờ chủ quán liên kết.")
        q = q.where(Availability.employee_id == actor.employee_id)
    sm = db.get(ScheduleMonth, month)
    return {"month": month, "locked": bool(sm and sm.status == "published"),
            "items": [{"employee_id": a.employee_id, "work_date": a.work_date.isoformat(),
                       "shift_code": a.shift_code, "available": a.available} for a in db.scalars(q)]}


@router.put("/availability")
def put_availability(body: AvailBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    valid_month(body.month)
    emp = body.employee_id if actor.is_owner and body.employee_id else actor.employee_id
    if not emp:
        raise HTTPException(400, "Tài khoản chưa gắn với nhân viên. Nhờ chủ quán liên kết.")
    sm = db.get(ScheduleMonth, body.month)
    if sm and sm.status == "published" and not actor.is_owner:
        raise HTTPException(409, "Lịch tháng này đã công bố, không khai báo thêm được")
    for it in body.items:
        if it.shift_code not in SHIFTS or month_of(it.work_date) != body.month:
            raise HTTPException(422, "Ngày/ca không hợp lệ")
        row = db.scalar(select(Availability).where(Availability.employee_id == emp, Availability.work_date == it.work_date,
                                                   Availability.shift_code == it.shift_code))
        if row:
            row.available, row.submitted_at = it.available, utcnow()
        else:
            db.add(Availability(month=body.month, employee_id=emp, work_date=it.work_date, shift_code=it.shift_code,
                                available=it.available))
    audit(db, actor, "availability", "schedule", body.month, None, {"employee_id": emp, "items": len(body.items)})
    db.commit()
    return {"ok": True, "saved": len(body.items)}
