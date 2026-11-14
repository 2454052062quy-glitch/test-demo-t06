"""R07 Chi phí và lãi/lỗ (F07-A/B/C) + xuất báo cáo (E-05) + nhật ký (E-03)."""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Actor, audit, employee_names, get_config, month_days, owner_only, valid_month
from ..models import AuditLog, Expense, PnlManualRef, PosOrder, Purchase
from ..services.pnl import CATEGORIES, compute_pnl, reconcile
from .payroll import month_payroll
from .schedule import XLSX

router = APIRouter(prefix="/api")


class ExpenseBody(BaseModel):
    expense_date: date
    category: str
    item: str = Field(min_length=1, max_length=160)
    amount: int = Field(gt=0)
    note: str = Field(default="", max_length=500)


def _exp(e: Expense) -> dict:
    return {"id": e.id, "expense_date": e.expense_date.isoformat(), "category": e.category, "item": e.item,
            "amount": e.amount, "note": e.note}


@router.get("/expenses")
def list_expenses(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    d = month_days(month)
    return [_exp(e) for e in db.scalars(select(Expense).where(Expense.expense_date.between(d[0], d[-1]))
                                        .order_by(Expense.expense_date.desc(), Expense.id.desc()))]


@router.post("/expenses")
def create_expense(body: ExpenseBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    if body.category not in CATEGORIES:
        raise HTTPException(422, "Nhóm chi phí chỉ gồm co_dinh hoặc phat_sinh")
    e = Expense(created_by=actor.id or None, **body.model_dump())
    db.add(e)
    db.flush()
    audit(db, actor, "create", "expense", e.id, None, body.model_dump())
    db.commit()
    return _exp(e)


@router.put("/expenses/{eid}")
def update_expense(eid: int, body: ExpenseBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    e = db.get(Expense, eid)
    if not e:
        raise HTTPException(404, "Không có khoản chi phí")
    if body.category not in CATEGORIES:
        raise HTTPException(422, "Nhóm chi phí không hợp lệ")
    old = _exp(e)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    audit(db, actor, "update", "expense", e.id, old, _exp(e))
    db.commit()
    return _exp(e)


@router.delete("/expenses/{eid}")
def delete_expense(eid: int, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    e = db.get(Expense, eid)
    if not e:
        raise HTTPException(404, "Không có khoản chi phí")
    audit(db, actor, "delete", "expense", e.id, _exp(e), None)
    db.delete(e)
    db.commit()
    return {"ok": True}


def build_pnl(db: Session, month: str):
    from ..deps import today_vn
    d = month_days(month)
    orders = [{"business_date": o.business_date, "paid": o.paid} for o in
              db.scalars(select(PosOrder).where(PosOrder.business_date.between(d[0], d[-1])))]
    purchases = [{"purchase_date": p.purchase_date, "total_amount": p.total_amount} for p in
                 db.scalars(select(Purchase).where(Purchase.purchase_date.between(d[0], d[-1])))]
    exps = [{"expense_date": e.expense_date, "category": e.category, "amount": e.amount} for e in
            db.scalars(select(Expense).where(Expense.expense_date.between(d[0], d[-1])))]
    pay = month_payroll(db, month)
    return compute_pnl(month, orders, purchases, [r["amount"] for r in pay["rows"]], exps, as_of_date=today_vn()), pay


def _pnl_dict(p, pay) -> dict:
    return {"month": p.month, "revenue": p.revenue, "ingredients": p.ingredients, "payroll": p.payroll,
            "fixed": p.fixed, "other": p.other, "total_cost": p.total_cost, "profit": p.profit,
            "complete": p.complete, "missing": p.missing, "payroll_locked": pay["locked"],
            "is_current_month": p.is_current_month, "as_of_day": p.as_of_day, "total_days": p.total_days,
            "prorated_label": p.prorated_label, "payroll_full": p.payroll_full, "fixed_full": p.fixed_full}


@router.get("/pnl/{month}")
def get_pnl(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    p, pay = build_pnl(db, month)
    return _pnl_dict(p, pay)


class ManualBody(BaseModel):
    revenue: int | None = Field(default=None, ge=0)
    ingredients: int | None = Field(default=None, ge=0)
    payroll: int | None = Field(default=None, ge=0)
    fixed: int | None = Field(default=None, ge=0)
    other: int | None = Field(default=None, ge=0)


@router.put("/pnl/{month}/manual-reference")
def put_manual(month: str, body: ManualBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    row = db.get(PnlManualRef, month) or PnlManualRef(month=month)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    row.entered_by = actor.id or None
    db.add(row)
    audit(db, actor, "update", "pnl_manual_reference", month, None, body.model_dump())
    db.commit()
    return {"ok": True}


@router.get("/pnl/{month}/reconcile")
def get_reconcile(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    p, _ = build_pnl(db, month)
    ref = db.get(PnlManualRef, month)
    manual = {k: getattr(ref, k) for k in ("revenue", "ingredients", "payroll", "fixed", "other")} if ref else None
    return {"month": month, "rows": reconcile(p, manual)}


# ---------------- E-03 nhật ký ----------------
@router.get("/audit")
def get_audit(limit: int = 100, entity: str | None = None, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    if not get_config().flags.get("E03_AUDIT", True):
        raise HTTPException(404, "Nhật ký thao tác đang tắt")
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))
    if entity:
        q = q.where(AuditLog.entity == entity)
    return [{"id": a.id, "at": a.at.isoformat(), "username": a.username, "action": a.action, "entity": a.entity,
             "entity_id": a.entity_id, "old_value": a.old_value, "new_value": a.new_value} for a in db.scalars(q)]


# ---------------- E-05 xuất báo cáo (CSV/XLSX; PDF dùng nút In của trình duyệt) ----------------
def _table_for(db: Session, kind: str, month: str) -> tuple[list[str], list[list]]:
    valid_month(month)
    if kind == "pnl":
        p, _ = build_pnl(db, month)
        return ["Khoản mục", "Số tiền (đồng)"], [["Doanh thu", p.revenue], ["Nguyên liệu", p.ingredients],
                                                  ["Lương", p.payroll], ["Chi phí cố định", p.fixed],
                                                  ["Chi phí phát sinh", p.other], ["Lãi/lỗ", p.profit]]
    if kind == "revenue":
        d = month_days(month)
        from sqlalchemy import func
        got = {r[0]: (int(r[1]), int(r[2])) for r in db.execute(
            select(PosOrder.business_date, func.sum(PosOrder.paid), func.count())
            .where(PosOrder.business_date.between(d[0], d[-1])).group_by(PosOrder.business_date))}
        return ["Ngày", "Doanh thu (đồng)", "Số đơn"], [[x.isoformat(), got.get(x, (0, 0))[0], got.get(x, (0, 0))[1]] for x in d]
    if kind == "schedule":
        from ..models import Assignment
        names = employee_names(db)
        grid: dict = {}
        for a in db.scalars(select(Assignment).where(Assignment.month == month)):
            grid.setdefault(a.work_date, {}).setdefault(a.shift_code, []).append(names.get(a.employee_id, "?"))
        return (["Ngày", "Ca Sáng", "Ca Trưa", "Ca Tối"],
                [[x.isoformat()] + [", ".join(grid.get(x, {}).get(s, [])) for s in ("sang", "trua", "toi")]
                 for x in month_days(month)])
    raise HTTPException(404, "Loại báo cáo chỉ gồm pnl, revenue, schedule")


@router.get("/export/{kind}")
def export(kind: str, month: str, fmt: str = "xlsx", actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    if not get_config().flags.get("E05_EXPORT", True):
        raise HTTPException(404, "Xuất báo cáo đang tắt")
    head, rows = _table_for(db, kind, month)
    name = f"{kind}_{month}"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(head)
        w.writerows(rows)
        return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    if fmt == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(head)
        for r in rows:
            ws.append(r)
        out = io.BytesIO()
        wb.save(out)
        return Response(out.getvalue(), media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})
    raise HTTPException(422, "fmt chỉ gồm xlsx hoặc csv (PDF: dùng nút In/Lưu PDF của trình duyệt)")
