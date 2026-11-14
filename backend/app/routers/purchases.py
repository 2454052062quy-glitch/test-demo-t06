"""R04 Nhập hàng + R09 Nguyên liệu (F04-A/B/C, F09-A/B/C)."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Actor, audit, check_duty_access, current_actor, get_config, month_days, owner_only, today_vn, valid_month
from ..models import Ingredient, IngredientStatusRow, Purchase, PurchaseAttachment, PurchaseItem, Supplier, utcnow

router = APIRouter(prefix="/api")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
MAX_IMAGE = 8 * 1024 * 1024
DOC_TYPES = ("hoa_don", "bien_lai_viet_tay", "khong_chung_tu")
MAGIC = {b"\xff\xd8\xff": ("jpg", "image/jpeg"), b"\x89PNG\r\n\x1a\n": ("png", "image/png")}


def _sniff(data: bytes) -> tuple[str, str] | None:
    for sig, v in MAGIC.items():
        if data.startswith(sig):
            return v
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ("webp", "image/webp")
    return None


class ItemBody(BaseModel):
    ingredient_name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    unit: str = Field(default="", max_length=30)
    unit_price: int = Field(ge=0)


class PurchaseBody(BaseModel):
    purchase_date: date
    supplier_name: str = Field(default="", max_length=120)
    doc_type: str = "hoa_don"
    discount: int = Field(default=0, ge=0)
    note: str = Field(default="", max_length=1000)
    items: list[ItemBody] = Field(min_length=1, max_length=60)


def _ingredient(db: Session, name: str, unit: str) -> Ingredient:
    name = name.strip()
    ing = db.scalar(select(Ingredient).where(func.lower(Ingredient.name) == name.lower()))
    if ing is None:
        ing = Ingredient(name=name, unit=unit)
        db.add(ing)
        db.flush()
    elif not ing.unit and unit:
        ing.unit = unit
    return ing


def _line_total(qty: float, price: int) -> int:
    return int((Decimal(str(qty)) * price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _write_items(db: Session, p: Purchase, body: PurchaseBody) -> None:
    total = 0
    for it in body.items:
        ing = _ingredient(db, it.ingredient_name, it.unit)
        lt = _line_total(it.quantity, it.unit_price)
        total += lt
        db.add(PurchaseItem(purchase_id=p.id, ingredient_id=ing.id, quantity=it.quantity, unit=it.unit or ing.unit,
                            unit_price=it.unit_price, line_total=lt))
    if body.discount > total:
        raise HTTPException(422, "Chiết khấu lớn hơn tổng tiền hàng")
    p.discount, p.total_amount = body.discount, total - body.discount


def _supplier(db: Session, name: str) -> int | None:
    name = name.strip()
    if not name:
        return None
    s = db.scalar(select(Supplier).where(func.lower(Supplier.name) == name.lower()))
    if s is None:
        s = Supplier(name=name)
        db.add(s)
        db.flush()
    return s.id


def _detail(db: Session, p: Purchase) -> dict:
    sup = db.get(Supplier, p.supplier_id) if p.supplier_id else None
    items = db.execute(select(PurchaseItem, Ingredient.name).join(Ingredient, Ingredient.id == PurchaseItem.ingredient_id)
                       .where(PurchaseItem.purchase_id == p.id)).all()
    atts = db.scalars(select(PurchaseAttachment).where(PurchaseAttachment.purchase_id == p.id)).all()
    return {"id": p.id, "purchase_date": p.purchase_date.isoformat(), "supplier": sup.name if sup else "",
            "doc_type": p.doc_type, "discount": p.discount, "total_amount": p.total_amount, "note": p.note,
            "created_by": p.created_by, "created_by_name": p.created_by_name, "shift_code": p.shift_code,
            "out_of_schedule": p.out_of_schedule,
            "items": [{"ingredient": n, "quantity": float(i.quantity), "unit": i.unit, "unit_price": i.unit_price,
                       "line_total": i.line_total} for i, n in items],
            "attachments": [{"id": a.id, "mime": a.mime} for a in atts]}


@router.post("/purchases")
def create_purchase(body: PurchaseBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(422, "Loại chứng từ không hợp lệ")
    access = check_duty_access(db, actor, "purchase.write", body.purchase_date)
    sid = _supplier(db, body.supplier_name)
    p = Purchase(purchase_date=body.purchase_date, supplier_id=sid, doc_type=body.doc_type, note=body.note,
                 created_by=actor.id or None, created_by_name=actor.display_name, shift_code=access.shift_code,
                 out_of_schedule=access.out_of_schedule)
    db.add(p)
    db.flush()
    _write_items(db, p, body)
    dup = db.scalar(select(func.count()).select_from(Purchase).where(
        Purchase.id != p.id, Purchase.purchase_date == p.purchase_date, Purchase.supplier_id == p.supplier_id,
        Purchase.total_amount == p.total_amount))
    audit(db, actor, "create", "purchase", p.id, None, {"total": p.total_amount, "date": p.purchase_date})
    db.commit()
    out = _detail(db, p)
    out["warnings"] = ["Đã có phiếu cùng nhà cung cấp, ngày và tổng tiền. Kiểm tra xem có nhập trùng không."] if dup else []
    return out


@router.get("/purchases")
def list_purchases(month: str, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    valid_month(month)
    days = month_days(month)
    rows = db.scalars(select(Purchase).where(Purchase.purchase_date.between(days[0], days[-1]))
                      .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())).all()
    return [_detail(db, p) for p in rows]


@router.get("/purchases/summary")
def purchases_summary(month: str, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    valid_month(month)
    days = month_days(month)
    rows = db.execute(select(func.coalesce(Supplier.name, "(không rõ)"), func.sum(Purchase.total_amount), func.count())
                      .select_from(Purchase).outerjoin(Supplier, Supplier.id == Purchase.supplier_id)
                      .where(Purchase.purchase_date.between(days[0], days[-1]))
                      .group_by(Supplier.name).order_by(func.sum(Purchase.total_amount).desc())).all()
    return {"month": month, "total": sum(int(r[1]) for r in rows), "count": sum(int(r[2]) for r in rows),
            "by_supplier": [{"supplier": n, "total": int(t), "count": int(c)} for n, t, c in rows]}


@router.get("/purchases/{pid}")
def get_purchase(pid: int, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if not p:
        raise HTTPException(404, "Không có phiếu nhập")
    return _detail(db, p)


@router.put("/purchases/{pid}")
def update_purchase(pid: int, body: PurchaseBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if not p:
        raise HTTPException(404, "Không có phiếu nhập")
    if not actor.is_owner and p.created_by != actor.id and p.created_by_name != actor.display_name:
        raise HTTPException(403, "Chỉ người lập phiếu hoặc chủ quán mới được sửa phiếu nhập này")
    old = _detail(db, p)
    for it in db.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == p.id)):
        db.delete(it)
    db.flush()
    p.purchase_date, p.doc_type, p.note, p.supplier_id = body.purchase_date, body.doc_type, body.note, _supplier(db, body.supplier_name)
    _write_items(db, p, body)
    audit(db, actor, "update", "purchase", p.id, old, {"total": p.total_amount})
    db.commit()
    return _detail(db, p)


@router.delete("/purchases/{pid}")
def delete_purchase(pid: int, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if not p:
        raise HTTPException(404, "Không có phiếu nhập")
    if not actor.is_owner and p.created_by != actor.id and p.created_by_name != actor.display_name:
        raise HTTPException(403, "Chỉ người lập phiếu hoặc chủ quán mới được xóa phiếu nhập này")
    audit(db, actor, "delete", "purchase", p.id, _detail(db, p), None)
    for a in db.scalars(select(PurchaseAttachment).where(PurchaseAttachment.purchase_id == p.id)):
        try:
            os.remove(os.path.join(UPLOAD_DIR, a.file_name))
        except OSError:
            pass
    for it in db.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == p.id)):
        db.delete(it)
    db.flush()
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/purchases/{pid}/attachments")
async def add_attachment(pid: int, file: UploadFile = File(...), actor: Actor = Depends(current_actor),
                         db: Session = Depends(get_db)):
    p = db.get(Purchase, pid)
    if not p:
        raise HTTPException(404, "Không có phiếu nhập")
    if not actor.is_owner and p.created_by != actor.id:
        raise HTTPException(403, "Chỉ người lập phiếu hoặc chủ quán được đính kèm ảnh")
    data = await file.read()
    if len(data) > MAX_IMAGE:
        raise HTTPException(413, "Ảnh quá lớn (tối đa 8 MB)")
    kind = _sniff(data)
    if not kind:
        raise HTTPException(422, "Chỉ nhận ảnh JPG, PNG hoặc WEBP")
    sha = hashlib.sha256(data).hexdigest()
    dup = db.scalar(select(PurchaseAttachment.id).where(PurchaseAttachment.sha256 == sha))
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{kind[0]}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    a = PurchaseAttachment(purchase_id=p.id, file_name=name, mime=kind[1], sha256=sha, uploaded_by=actor.id or None)
    db.add(a)
    audit(db, actor, "attach", "purchase", p.id, None, {"sha256": sha[:12]})
    db.commit()
    return {"id": a.id, "warning": "Ảnh này đã được đính kèm ở một phiếu khác" if dup else None}


@router.get("/purchases/{pid}/attachments/{aid}")
def get_attachment(pid: int, aid: int, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    a = db.get(PurchaseAttachment, aid)
    if not a or a.purchase_id != pid:
        raise HTTPException(404, "Không có ảnh")
    path = os.path.join(UPLOAD_DIR, os.path.basename(a.file_name))
    if not os.path.exists(path):
        raise HTTPException(404, "Tệp ảnh không còn")
    return FileResponse(path, media_type=a.mime)


# ---------------- R09 ----------------
class IngredientBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(default="", max_length=30)
    is_active: bool = True


class StatusBody(BaseModel):
    ingredient_id: int
    status: str  # du | sap_het | het | da_dat
    note: str = Field(default="", max_length=500)


def _status_open(db: Session, ing_id: int) -> IngredientStatusRow | None:
    return db.scalar(select(IngredientStatusRow).where(IngredientStatusRow.ingredient_id == ing_id,
                                                       IngredientStatusRow.closed_at.is_(None))
                     .order_by(IngredientStatusRow.id.desc()))


@router.get("/ingredients")
def list_ingredients(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    out = []
    for ing in db.scalars(select(Ingredient).order_by(Ingredient.name)):
        last = db.execute(select(PurchaseItem.unit_price, Purchase.purchase_date, PurchaseItem.unit)
                          .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
                          .where(PurchaseItem.ingredient_id == ing.id)
                          .order_by(Purchase.purchase_date.desc(), PurchaseItem.id.desc()).limit(1)).first()
        st = _status_open(db, ing.id)
        out.append({"id": ing.id, "name": ing.name, "unit": ing.unit, "is_active": ing.is_active,
                    "last_price": last[0] if last else None, "last_price_unit": last[2] if last else None,
                    "last_purchase_date": last[1].isoformat() if last else None,  # giá nhập gần nhất lấy từ R04
                    "status": st.status if st else "du", "status_note": st.note if st else "",
                    "status_at": st.reported_at.isoformat() if st else None,
                    "status_by_name": st.reported_by_name if st else ""})
    return out


@router.post("/ingredients")
def create_ingredient(body: IngredientBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if db.scalar(select(Ingredient.id).where(func.lower(Ingredient.name) == body.name.strip().lower())):
        raise HTTPException(409, "Nguyên liệu đã có trong danh mục")
    ing = Ingredient(name=body.name.strip(), unit=body.unit.strip(), is_active=body.is_active)
    db.add(ing)
    db.flush()
    audit(db, actor, "create", "ingredient", ing.id, None, body.model_dump())
    db.commit()
    return {"id": ing.id}


@router.put("/ingredients/{iid}")
def update_ingredient(iid: int, body: IngredientBody, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    ing = db.get(Ingredient, iid)
    if not ing:
        raise HTTPException(404, "Không có nguyên liệu")
    clash = db.scalar(select(Ingredient.id).where(func.lower(Ingredient.name) == body.name.strip().lower(),
                                                  Ingredient.id != iid))
    if clash:
        raise HTTPException(409, "Trùng tên nguyên liệu khác")
    old = {"name": ing.name, "unit": ing.unit, "is_active": ing.is_active}
    ing.name, ing.unit, ing.is_active = body.name.strip(), body.unit.strip(), body.is_active
    audit(db, actor, "update", "ingredient", ing.id, old, body.model_dump())
    db.commit()
    return {"ok": True}


@router.delete("/ingredients/{iid}")
def delete_ingredient(iid: int, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    ing = db.get(Ingredient, iid)
    if not ing:
        raise HTTPException(404, "Không có nguyên liệu")
    old = {"id": ing.id, "name": ing.name, "unit": ing.unit}
    for st in db.scalars(select(IngredientStatusRow).where(IngredientStatusRow.ingredient_id == iid)):
        db.delete(st)
    for pi in db.scalars(select(PurchaseItem).where(PurchaseItem.ingredient_id == iid)):
        db.delete(pi)
    db.flush()
    db.delete(ing)
    audit(db, actor, "delete", "ingredient", iid, old, None)
    db.commit()
    return {"ok": True}


@router.post("/ingredient-status")
def report_status(body: StatusBody, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if body.status not in ("du", "sap_het", "het", "da_dat"):
        raise HTTPException(422, "Tình trạng chỉ gồm du, sap_het, het, da_dat")
    ing = db.get(Ingredient, body.ingredient_id)
    if not ing:
        raise HTTPException(404, "Không có nguyên liệu")
    access = check_duty_access(db, actor, "ingredient.report", today_vn())
    now = utcnow()
    for r in db.scalars(select(IngredientStatusRow).where(IngredientStatusRow.ingredient_id == ing.id,
                                                          IngredientStatusRow.closed_at.is_(None))):
        r.closed_at = now  # báo mới (hoặc báo "đủ") đóng báo cáo trước
    if body.status != "du":
        db.add(IngredientStatusRow(ingredient_id=ing.id, status=body.status, note=body.note, reported_by=actor.id or None,
                                   reported_by_name=actor.display_name, shift_code=access.shift_code,
                                   out_of_schedule=access.out_of_schedule))
    audit(db, actor, "report", "ingredient_status", ing.id, None, {"status": body.status})
    db.commit()
    return {"ok": True, "out_of_schedule": access.out_of_schedule}


@router.get("/ingredient-status/open")
def open_status(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.execute(select(IngredientStatusRow, Ingredient.name, Ingredient.unit)
                      .join(Ingredient, Ingredient.id == IngredientStatusRow.ingredient_id)
                      .where(IngredientStatusRow.closed_at.is_(None))
                      .order_by(IngredientStatusRow.reported_at.desc())).all()
    return [{"id": r.id, "ingredient_id": r.ingredient_id, "ingredient": n, "ingredient_name": n,
             "unit": u, "status": r.status, "note": r.note,
             "reported_by_name": r.reported_by_name, "created_by_name": r.reported_by_name,
             "reported_at": r.reported_at.isoformat(), "created_at": r.reported_at.isoformat(),
             "out_of_schedule": r.out_of_schedule} for r, n, u in rows]


@router.get("/ingredient-status/history")
def status_history(limit: int = 30, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    """Lịch sử báo cáo nguyên liệu gần đây (dùng cho khung 'Đã báo gần đây')."""
    rows = db.execute(select(IngredientStatusRow, Ingredient.name, Ingredient.unit)
                      .join(Ingredient, Ingredient.id == IngredientStatusRow.ingredient_id)
                      .order_by(IngredientStatusRow.reported_at.desc()).limit(min(limit, 100))).all()
    return [{"id": r.id, "ingredient_id": r.ingredient_id, "ingredient": n, "ingredient_name": n,
             "unit": u, "status": r.status, "note": r.note,
             "reported_by_name": r.reported_by_name, "created_by_name": r.reported_by_name,
             "reported_at": r.reported_at.isoformat(), "created_at": r.reported_at.isoformat(),
             "closed_at": r.closed_at.isoformat() if r.closed_at else None,
             "out_of_schedule": r.out_of_schedule} for r, n, u in rows]
