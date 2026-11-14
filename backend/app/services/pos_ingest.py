"""Hợp nhất dữ liệu POS từ hai đường (API và file "Chi tiết doanh thu") và chống nhân đôi.

Khóa chống trùng: doc_code (mã chứng từ). Khi trùng mã:
- giống hệt -> đếm 'duplicate';
- khác giá trị: API ghi đè file; file không ghi đè API (đếm 'conflict').
Cảnh báo mềm: khác mã nhưng cùng phút và cùng số tiền (D19, mã OFFLINE...).
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .timeutil import business_date, local_naive_to_utc

REQUIRED_COLUMNS = ["Mã chứng từ", "Ngày tạo", "Tổng cộng", "Thanh toán"]
OPTIONAL_COLUMNS = ["Khách hàng", "Phòng/Bàn", "Số khách", "Chiết khấu"]
SUMMARY_LABELS = {
    "số đơn hàng": "order_count",
    "tổng giá trị": "total_value",
    "tổng thanh toán": "total_paid",
    "tổng số khách": "total_guests",
}
COMPARE_FIELDS = ("created_at", "paid", "total", "discount")


class ImportFormatError(Exception):
    pass


def _norm(s) -> str:
    s = "" if s is None else str(s)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().rstrip(":").strip().casefold()


def parse_money(value) -> int | None:
    """Số hoặc chuỗi kiểu '1.234.000', '1,234,000', '1234000.00' -> đồng (int). Rỗng -> None."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("giá trị tiền không hợp lệ")
    if isinstance(value, (int, float, Decimal)):
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    s = str(value).strip().replace(" ", "").replace("đ", "").replace("₫", "")
    if s == "":
        return None
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()")
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        thou = "." if dec == "," else ","
        s = s.replace(thou, "").replace(dec, ".")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        parts = s.split(sep)
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = "".join(parts)  # dấu phân cách hàng nghìn
        else:
            s = ".".join(parts)
    try:
        n = int(Decimal(s).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError(f"giá trị tiền không hợp lệ: {value!r}") from exc
    return -n if neg else n


_DT_FORMATS = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
               "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M")


def parse_local_datetime(value) -> datetime | None:
    """Ngày tạo của file xuất; không có múi giờ -> coi là giờ địa phương GMT+7 (D10). Trả UTC."""
    if isinstance(value, datetime):
        return local_naive_to_utc(value.replace(tzinfo=None))
    if value is None:
        return None
    s = str(value).strip()
    for fmt in _DT_FORMATS:
        try:
            return local_naive_to_utc(datetime.strptime(s, fmt))
        except ValueError:
            continue
    return None


@dataclass
class ParsedFile:
    orders: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    skipped_total: int = 0
    skipped_invalid: list = field(default_factory=list)  # [(số dòng, lý do)]
    rows_read: int = 0

    def reconcile(self) -> dict:
        """Đối soát với khối tổng ở đầu file (nếu có). ok=None nghĩa là file không có khối tổng."""
        out = {}
        if "order_count" in self.summary:
            out["order_count"] = {"file": self.summary["order_count"], "parsed": len(self.orders),
                                  "ok": self.summary["order_count"] == len(self.orders)}
        if "total_paid" in self.summary:
            s = sum(o["paid"] for o in self.orders)
            out["total_paid"] = {"file": self.summary["total_paid"], "parsed": s,
                                 "ok": self.summary["total_paid"] == s}
        out["ok"] = (all(v["ok"] for v in out.values()) if out else None)
        return out


def _find_header(rows: list[list]) -> tuple[int, dict]:
    for i, row in enumerate(rows):
        cells = {_norm(c): j for j, c in enumerate(row) if c not in (None, "")}
        if _norm("Mã chứng từ") in cells and _norm("Ngày tạo") in cells:
            return i, {name: cells[_norm(name)] for name in REQUIRED_COLUMNS + OPTIONAL_COLUMNS
                       if _norm(name) in cells}
    raise ImportFormatError("không tìm thấy dòng tiêu đề (cần cột 'Mã chứng từ' và 'Ngày tạo')")


def _read_summary(rows: list[list], header_idx: int) -> dict:
    summary = {}
    for row in rows[:header_idx]:
        for j, c in enumerate(row):
            key = SUMMARY_LABELS.get(_norm(c))
            if not key:
                continue
            for v in row[j + 1:]:
                if v not in (None, ""):
                    try:
                        summary[key] = parse_money(v)
                    except ValueError:
                        pass
                    break
    return summary


def parse_rows(rows: list[list]) -> ParsedFile:
    """rows: bảng ô thô (từ xlsx hoặc csv). Bỏ tiêu đề, dải tổng đầu/cuối; kiểm tra cột bắt buộc."""
    hi, cols = _find_header(rows)
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        raise ImportFormatError("thiếu cột bắt buộc: " + ", ".join(missing))
    pf = ParsedFile(summary=_read_summary(rows, hi))
    for off, row in enumerate(rows[hi + 1:], start=hi + 2):
        def cell(name):
            j = cols.get(name)
            return row[j] if j is not None and j < len(row) else None
        code, created_raw = cell("Mã chứng từ"), cell("Ngày tạo")
        if all(c in (None, "") for c in row):
            continue
        created = parse_local_datetime(created_raw)
        if code in (None, "") or created is None:
            # dải tổng (không có mã hoặc không có ngày) -> bỏ
            if any(c not in (None, "") for c in row):
                pf.skipped_total += 1
            continue
        pf.rows_read += 1
        if str(code).strip() == "Σ":
            pf.skipped_total += 1
            continue
        try:
            paid, total = parse_money(cell("Thanh toán")), parse_money(cell("Tổng cộng"))
            discount = parse_money(cell("Chiết khấu")) or 0
        except ValueError as exc:
            pf.skipped_invalid.append((off, str(exc)))
            continue
        if paid is None or total is None:
            pf.skipped_invalid.append((off, "thiếu Tổng cộng hoặc Thanh toán"))
            continue
        guests = cell("Số khách")
        pf.orders.append({
            "doc_code": str(code).strip(), "created_at": created, "business_date": business_date(created),
            "paid": paid, "total": total, "discount": discount, "pos_id": None, "source": "file",
            "table_name": (str(cell("Phòng/Bàn")).strip() if cell("Phòng/Bàn") not in (None, "") else None),
            "guests": int(guests) if isinstance(guests, (int, float)) else None,
        })
    return pf


def parse_xlsx(source) -> ParsedFile:
    """source: đường dẫn hoặc file-like. Dùng openpyxl (data_only để lấy giá trị, không lấy công thức)."""
    import openpyxl
    wb = openpyxl.load_workbook(source, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    return parse_rows([list(r) for r in ws.iter_rows(values_only=True)])


def parse_csv(data: bytes | str) -> ParsedFile:
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return parse_rows([row for row in csv.reader(io.StringIO(text), dialect)])


@dataclass
class MergeStats:
    inserted: int = 0
    updated: int = 0
    duplicate: int = 0
    conflict: int = 0
    warnings: list = field(default_factory=list)


def _differs(a: dict, b: dict) -> bool:
    return any(a.get(k) != b.get(k) for k in COMPARE_FIELDS)


def merge_orders(existing: dict, incoming: list[dict]) -> MergeStats:
    """Hợp nhất vào `existing` (doc_code -> bản ghi). Sửa tại chỗ, trả thống kê."""
    stats = MergeStats()
    fingerprints = {(o["created_at"].replace(second=0, microsecond=0), o["paid"]): code
                    for code, o in existing.items()}
    for new in incoming:
        code = new["doc_code"]
        old = existing.get(code)
        if old is None:
            fp = (new["created_at"].replace(second=0, microsecond=0), new["paid"])
            other = fingerprints.get(fp)
            if other and other != code:
                stats.warnings.append(f"{code} cùng giờ và số tiền với {other} nhưng khác mã (kiểm tra trùng, D19)")
            existing[code] = dict(new)
            fingerprints[fp] = code
            stats.inserted += 1
        elif not _differs(old, new):
            stats.duplicate += 1
        elif old.get("source") == "api" and new.get("source") == "file":
            stats.conflict += 1  # API ghi đè file, không để file ghi đè API
            stats.warnings.append(f"{code}: file khác dữ liệu API, giữ bản API")
        else:
            old.update({k: new[k] for k in COMPARE_FIELDS})
            old["business_date"], old["source"] = new["business_date"], new["source"]
            if new.get("pos_id") is not None:
                old["pos_id"] = new["pos_id"]
            stats.updated += 1
    return stats


def daily_revenue(orders: dict, month: str | None = None) -> dict[date, int]:
    out: dict[date, int] = {}
    for o in orders.values():
        d = o["business_date"]
        if month and d.strftime("%Y-%m") != month:
            continue
        out[d] = out.get(d, 0) + o["paid"]  # doanh thu = Σ TotalPayment (D07)
    return dict(sorted(out.items()))


def monthly_revenue(orders: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for d, v in daily_revenue(orders).items():
        out[d.strftime("%Y-%m")] = out.get(d.strftime("%Y-%m"), 0) + v
    return out
