"""R01 Doanh thu POS: đồng bộ API, nạp file, nhật ký, doanh thu ngày/tháng, hóa đơn chi tiết (F01-A…F).

A1-A4: thêm tab Danh sách hóa đơn với lọc/phân trang.
B1-B5: đồng bộ có mốc ngày, giới hạn trang, timeout, nhật ký chi tiết.
C4: đăng nhập nhanh Demo (server từ chối ở Live).
"""
from __future__ import annotations

import hashlib
import io
import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Actor, audit, current_actor, get_config, month_days, owner_only, today_vn, valid_month
from ..models import PosOrder, PosSyncLog, utcnow
from ..services import pos_ingest
from ..services.pos365 import (Pos365AuthError, Pos365Client, Pos365Error,
                                fetch_orders_since, normalize_order)
from ..services.timeutil import VN_TZ

router = APIRouter(prefix="/api")
MAX_UPLOAD = 15 * 1024 * 1024
FIELDS = ("doc_code", "created_at", "business_date", "total", "paid", "discount", "pos_id", "source",
          "table_name", "guests")


def _to_dict(o: PosOrder) -> dict:
    return {k: getattr(o, k) for k in FIELDS}


def _load_existing(db: Session, incoming: list[dict]) -> dict:
    """Nạp các đơn đã có trong cùng khoảng ngày (để bắt trùng mềm) và theo mã (để bắt trùng cứng)."""
    if not incoming:
        return {}
    lo = min(o["business_date"] for o in incoming) - timedelta(days=1)
    hi = max(o["business_date"] for o in incoming) + timedelta(days=1)
    rows = list(db.scalars(select(PosOrder).where(PosOrder.business_date.between(lo, hi))))
    have = {r.doc_code for r in rows}
    codes = [o["doc_code"] for o in incoming if o["doc_code"] not in have]
    for i in range(0, len(codes), 500):
        rows += list(db.scalars(select(PosOrder).where(PosOrder.doc_code.in_(codes[i:i + 500]))))
    return {r.doc_code: _to_dict(r) for r in rows}


def _persist(db: Session, existing: dict, snapshot: dict, log: PosSyncLog) -> None:
    by_code = {}
    changed = [c for c, rec in existing.items() if c not in snapshot or rec != snapshot[c]]
    for i in range(0, len(changed), 500):
        for r in db.scalars(select(PosOrder).where(PosOrder.doc_code.in_(changed[i:i + 500]))):
            by_code[r.doc_code] = r
    for code in changed:
        rec = existing[code]
        row = by_code.get(code)
        if row is None:
            row = PosOrder(doc_code=code)
            db.add(row)
        for k in FIELDS:
            setattr(row, k, rec.get(k))
        row.last_seen_log_id = log.id


def _ingest(db: Session, log: PosSyncLog, incoming: list[dict]) -> None:
    existing = _load_existing(db, incoming)
    snapshot = {c: dict(v) for c, v in existing.items()}
    stats = pos_ingest.merge_orders(existing, incoming)
    _persist(db, existing, snapshot, log)
    log.rows_inserted, log.rows_updated = stats.inserted, stats.updated
    log.rows_duplicate, log.rows_conflict = stats.duplicate, stats.conflict
    log.warnings = stats.warnings[:50] or None


def _serialize(log: PosSyncLog) -> dict:
    return {c.name: (getattr(log, c.name).isoformat() if hasattr(getattr(log, c.name), "isoformat")
                     else getattr(log, c.name)) for c in log.__table__.columns}


def _get_sync_since(cfg) -> date | None:
    """B1: xác định mốc ngày đồng bộ. Mặc định = ngày 1 tháng trước (giờ VN)."""
    from datetime import datetime
    raw = getattr(cfg, "pos365_sync_from_date", "") or ""
    if raw.strip():
        try:
            return date.fromisoformat(raw.strip())
        except ValueError:
            pass
    # mặc định: ngày 1 của tháng trước
    today = datetime.now(VN_TZ).date()
    if today.month == 1:
        return date(today.year - 1, 12, 1)
    return date(today.year, today.month - 1, 1)


def _friendly_error(exc: Exception) -> str:
    """B3: chuyển lỗi kỹ thuật thành thông báo tiếng Việt dễ hiểu."""
    s = str(exc)
    if "401" in s or "Unauthorized" in s or "SessionId" in s:
        return f"[ERR-AUTH] Lỗi xác thực POS365: phiên đăng nhập hết hạn hoặc sai tài khoản. {s[:200]}"
    if "403" in s or "Forbidden" in s:
        return f"[ERR-PERM] Tài khoản POS365 không có quyền truy cập. {s[:200]}"
    if "timeout" in s.lower() or "TimeoutError" in type(exc).__name__:
        return f"[ERR-TIMEOUT] Hết thời gian kết nối POS365. Kiểm tra đường truyền mạng. {s[:200]}"
    if "kết nối" in s or "URLError" in type(exc).__name__ or "Connection" in type(exc).__name__:
        return f"[ERR-NET] Không kết nối được POS365_BASE_URL. Kiểm tra địa chỉ và mạng. {s[:200]}"
    if "JSON" in s or "json" in s:
        return f"[ERR-JSON] POS365 trả dữ liệu không phải JSON (có thể do Cookie hết hạn). {s[:200]}"
    return f"[ERR] {s[:300]}"


@router.post("/pos/sync")
def sync_pos(actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    """B1-B5: đồng bộ POS365 có mốc ngày, giới hạn trang, timeout, ghi nhật ký."""
    cfg = get_config()
    if not cfg.pos365_base_url:
        raise HTTPException(400, "Chưa cấu hình POS365_BASE_URL. Dùng nạp file 'Chi tiết doanh thu' thay thế.")
    since = _get_sync_since(cfg)
    max_pages = getattr(cfg, "pos365_sync_max_pages", 500)
    timeout = getattr(cfg, "pos365_request_timeout", 30.0)

    log = PosSyncLog(kind="api", user_id=actor.id or None)
    db.add(log)
    db.flush()
    client = Pos365Client(cfg.pos365_base_url, os.environ.get("POS365_USERNAME", ""),
                          os.environ.get("POS365_PASSWORD", ""), cfg.pos365_auth_mode,
                          cfg.pos365_extra_headers, cfg.pos365_top_param, cfg.pos365_skip_param,
                          timeout=timeout)
    try:
        res = fetch_orders_since(client.get_orders_page, cfg.pos365_page_size,
                                 max_pages=max_pages, since=since)
    except (Pos365AuthError, Pos365Error) as exc:
        err_msg = _friendly_error(exc)
        log.status, log.error, log.finished_at = "error", err_msg, utcnow()
        db.commit()
        raise HTTPException(502, f"Không đồng bộ được với POS365: {err_msg}")
    except Exception as exc:
        err_msg = _friendly_error(exc)
        log.status, log.error, log.finished_at = "error", err_msg, utcnow()
        db.commit()
        raise HTTPException(502, f"Lỗi không mong đợi khi đồng bộ: {err_msg}")

    good, skipped = [], {"total": 0, "void": 0, "invalid": 0}
    for raw in res.raw_rows:
        n = normalize_order(raw)
        if n.order:
            good.append(n.order)
        else:
            skipped[n.skipped or "invalid"] += 1
    log.rows_read, log.pos_count_reported = len(res.raw_rows), res.count_reported
    log.rows_skipped_total = skipped["total"]
    log.rows_skipped_void = skipped["void"]
    log.rows_skipped_invalid = skipped["invalid"]

    # B4: ghi thêm thông tin vào nhật ký
    extra_warnings = []
    if res.stopped_early:
        extra_warnings.append(
            f"Đã dừng vì đạt giới hạn {max_pages} trang. Bấm 'Đồng bộ lại' để lấy tiếp."
        )
        log.status = "partial"
    if res.cutoff_hit:
        extra_warnings.append(f"Đã dừng vì gặp đơn cũ hơn mốc {since.isoformat()}.")
    if extra_warnings:
        log.error = "; ".join(extra_warnings)

    _ingest(db, log, good)
    log.finished_at = utcnow()
    if not res.stopped_early:
        log.status = "ok"

    audit(db, actor, "sync", "pos_orders", log.id, None,
          {"inserted": log.rows_inserted, "updated": log.rows_updated,
           "pages": res.pages, "since": since.isoformat() if since else None})
    db.commit()
    out = _serialize(log)
    out["stopped_early"] = res.stopped_early
    out["cutoff_hit"] = res.cutoff_hit
    out["since"] = since.isoformat() if since else None
    return out


def _import_bytes(db: Session, actor: Actor, name: str, data: bytes) -> dict:
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File quá lớn (tối đa 15 MB)")
    lower = name.lower()
    try:
        if lower.endswith((".xlsx", ".xlsm")):
            pf = pos_ingest.parse_xlsx(io.BytesIO(data))
        elif lower.endswith(".csv"):
            pf = pos_ingest.parse_csv(data)
        else:
            raise HTTPException(422, "Chỉ nhận file .xlsx hoặc .csv")
    except pos_ingest.ImportFormatError as exc:
        raise HTTPException(422, f"File không đúng mẫu 'Chi tiết doanh thu': {exc}")
    except HTTPException:
        raise
    except Exception as exc:  # openpyxl/zip lỗi
        raise HTTPException(422, f"Không đọc được file: {type(exc).__name__}")
    sha = hashlib.sha256(data).hexdigest()
    again = db.scalar(select(func.count()).select_from(PosSyncLog).where(PosSyncLog.file_sha256 == sha)) > 0
    rec = pf.reconcile()
    log = PosSyncLog(kind="file", user_id=actor.id or None, file_name=name[:200], file_sha256=sha,
                     rows_read=pf.rows_read, rows_skipped_total=pf.skipped_total,
                     rows_skipped_invalid=len(pf.skipped_invalid), reconcile_ok=rec["ok"],
                     pos_count_reported=pf.summary.get("order_count"), sum_paid_reported=pf.summary.get("total_paid"))
    db.add(log)
    db.flush()
    _ingest(db, log, pf.orders)
    warnings = list(log.warnings or [])
    if again:
        warnings.append("File này đã từng được nạp (kết quả không bị nhân đôi nhờ chống trùng mã chứng từ)")
    for row, why in pf.skipped_invalid[:20]:
        warnings.append(f"Dòng {row} bị bỏ: {why}")
    log.warnings = warnings[:50] or None
    log.finished_at = utcnow()
    audit(db, actor, "import", "pos_orders", log.id, None, {"file": name, "inserted": log.rows_inserted})
    db.commit()
    out = _serialize(log)
    out["reconcile"] = rec
    return out


@router.post("/pos/import")
async def import_pos(file: UploadFile = File(...), actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    data = await file.read()
    return _import_bytes(db, actor, file.filename or "upload", data)


@router.post("/pos/import-sample")
def import_sample(actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    """Chỉ Demo: nạp file doanh thu giả lập có sẵn để thử nhanh."""
    if get_config().is_live:
        raise HTTPException(403, "Không có ở chế độ Live")
    path = os.path.join(os.environ.get("DATA_DIR", "/app/data"), "mock", "chi_tiet_doanh_thu_mock.xlsx")
    if not os.path.exists(path):
        raise HTTPException(404, "Không thấy data/mock/chi_tiet_doanh_thu_mock.xlsx")
    with open(path, "rb") as f:
        return _import_bytes(db, actor, os.path.basename(path), f.read())


@router.get("/pos/sync-logs")
def sync_logs(limit: int = 30, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    rows = db.scalars(select(PosSyncLog).order_by(PosSyncLog.id.desc()).limit(min(limit, 200)))
    return [_serialize(r) for r in rows]


# ---------- A4: Danh sách hóa đơn chi tiết với lọc / phân trang ----------
def _serialize_order(o: PosOrder) -> dict:
    created_vn = o.created_at.astimezone(VN_TZ) if o.created_at else None
    return {
        "id": o.id,
        "doc_code": o.doc_code,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "created_at_vn": created_vn.strftime("%H:%M") if created_vn else None,
        "business_date": o.business_date.isoformat() if o.business_date else None,
        "total": o.total,
        "paid": o.paid,
        "discount": o.discount,
        "table_name": o.table_name or "—",
        "guests": o.guests,
        "source": o.source or "file",
        "pos_id": o.pos_id,
    }


@router.get("/pos/orders")
def list_orders(
    month: str | None = Query(default=None),
    day: str | None = Query(default=None),
    q: str | None = Query(default=None, description="tìm theo mã đơn hoặc tên bàn"),
    source: str | None = Query(default=None, description="api | file"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    actor: Actor = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """A4: Danh sách hóa đơn chi tiết với lọc tháng/ngày/từ khóa/nguồn, phân trang, mới nhất trước."""
    stmt = select(PosOrder)

    if day:
        try:
            d = date.fromisoformat(day)
            stmt = stmt.where(PosOrder.business_date == d)
        except ValueError:
            raise HTTPException(422, "day phải có dạng YYYY-MM-DD")
    elif month:
        valid_month(month)
        days = month_days(month)
        stmt = stmt.where(PosOrder.business_date.between(days[0], days[-1]))

    if source in ("api", "file"):
        stmt = stmt.where(PosOrder.source == source)

    if q:
        kw = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(PosOrder.doc_code).like(kw),
                func.lower(func.coalesce(PosOrder.table_name, "")).like(kw),
            )
        )

    # đếm tổng
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # phân trang
    offset = (page - 1) * page_size
    rows = db.scalars(stmt.order_by(PosOrder.created_at.desc()).offset(offset).limit(page_size))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "orders": [_serialize_order(r) for r in rows],
    }


@router.get("/revenue/daily")
def revenue_daily(month: str, actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    valid_month(month)
    days = month_days(month)
    rows = db.execute(select(PosOrder.business_date, func.sum(PosOrder.paid), func.count())
                      .where(PosOrder.business_date.between(days[0], days[-1]))
                      .group_by(PosOrder.business_date)).all()
    got = {d: (int(s), int(c)) for d, s, c in rows}
    return {"month": month, "days": [{"date": d.isoformat(), "revenue": got.get(d, (0, 0))[0],
                                      "orders": got.get(d, (0, 0))[1]} for d in days],
            "total": sum(v[0] for v in got.values()), "orders": sum(v[1] for v in got.values())}


@router.get("/revenue/monthly")
def revenue_monthly(actor: Actor = Depends(owner_only), db: Session = Depends(get_db)):
    month = func.to_char(PosOrder.business_date, "YYYY-MM")
    rows = db.execute(select(month, func.sum(PosOrder.paid), func.count()).group_by(month).order_by(month)).all()
    return [{"month": m, "revenue": int(s), "orders": int(c)} for m, s, c in rows]
