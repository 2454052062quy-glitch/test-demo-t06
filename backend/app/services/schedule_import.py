"""Nạp file Excel/CSV lịch ca (R06 Đường 1, F06-B). Căn cứ: QT3a-B1 C.3a.1 (lịch là file bảng tính trong Zalo nhóm).

Hai định dạng (chốt 12/11/2026, D28), có nút "Tải file mẫu .xlsx" ở giao diện:
  1. LƯỚI/MA TRẬN của quán: dòng tiêu đề gồm cột Ngày (và/hoặc Thứ) rồi 3 cột Ca Sáng | Ca Trưa | Ca Tối.
     Mỗi ô là tên nhân viên (nhiều tên cách nhau , / ;). Ô trống = chưa xếp.
  2. DANH SÁCH PHẲNG: cột Ngày (YYYY-MM-DD hoặc DD/MM/YYYY) | Mã ca (Sáng/Trưa/Tối) | Tên nhân viên.
Ngày có thể là ô ngày của Excel hoặc chuỗi; ở dạng lưới chấp nhận cả "Thứ Hai, 03/11/2026" hoặc "T2 03/11"
(thiếu năm thì lấy năm của tháng đang nạp).
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

SHIFT_ALIASES = {"sáng": "sang", "sang": "sang", "ca sáng": "sang", "trưa": "trua", "trua": "trua",
                 "ca trưa": "trua", "tối": "toi", "toi": "toi", "ca tối": "toi", "chiều": "toi",
                 "chieu": "toi", "ca chiều": "toi"}


class ScheduleImportError(Exception):
    pass


def _norm(s) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", "" if s is None else str(s))).strip().casefold()


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_DM = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?")


def parse_date(value, month: str | None = None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = _norm(value)
    if not s:
        return None
    m0 = _DM.search(s)  # "thứ hai, 03/11/2026", "t2 03/11"
    if m0 and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", s):
        day, mon, year = int(m0.group(1)), int(m0.group(2)), m0.group(3)
        y = int(year) if year else (int(month[:4]) if month else None)
        if y is None:
            return None
        try:
            return date(y, mon, day)
        except ValueError:
            return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", s)
    if m and month:
        y = int(month[:4])
        try:
            return date(y, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


@dataclass
class ParsedSchedule:
    assignments: list = field(default_factory=list)  # [(date, shift, raw_name)]
    errors: list = field(default_factory=list)       # [(số dòng, lý do)]
    layout: str = ""

    @property
    def raw_names(self) -> list[str]:
        return sorted({n for _d, _s, n in self.assignments})

    def over_capacity(self, capacity: dict | None = None) -> list[tuple]:
        cap = capacity or {"sang": 1, "trua": 1, "toi": 1}
        seen: dict = {}
        for d, s, n in self.assignments:
            seen.setdefault((d, s), set()).add(_norm(n))
        return sorted((k for k, v in seen.items() if len(v) > cap.get(k[1], 1)), key=lambda k: (k[0], k[1]))


def parse_rows(rows: list[list], month: str | None = None) -> ParsedSchedule:
    for hi, row in enumerate(rows):
        cells = [_norm(c) for c in row]
        has_ca = "ca" in cells or "mã ca" in cells
        has_name = any(c in cells for c in ("nhân viên", "tên", "tên nhân viên"))
        if "ngày" in cells and has_ca and has_name:
            return _parse_long(rows, hi, cells, month)
        if ("ngày" in cells or "thứ" in cells) and sum(1 for c in cells if c in SHIFT_ALIASES) >= 2:
            return _parse_grid(rows, hi, cells, month)
    raise ScheduleImportError("không nhận ra bố cục. Dạng lưới: cột 'Ngày' (hoặc 'Thứ') + 'Ca Sáng', 'Ca Trưa', "
                              "'Ca Tối'. Dạng phẳng: cột 'Ngày', 'Mã ca', 'Tên nhân viên'. Dùng nút Tải file mẫu.")


def _split_names(v) -> list[str]:
    return [p.strip() for p in re.split(r"[,/;]", "" if v is None else str(v)) if p.strip()]


def _parse_long(rows, hi, cells, month) -> ParsedSchedule:
    ps = ParsedSchedule(layout="long")
    ci = cells.index("ngày")
    cs = cells.index("mã ca") if "mã ca" in cells else cells.index("ca")
    cn = next(cells.index(c) for c in ("tên nhân viên", "nhân viên", "tên") if c in cells)
    for off, row in enumerate(rows[hi + 1:], start=hi + 2):
        if all(c in (None, "") for c in row):
            continue
        d = parse_date(row[ci] if ci < len(row) else None, month)
        shift = SHIFT_ALIASES.get(_norm(row[cs] if cs < len(row) else None))
        names = _split_names(row[cn] if cn < len(row) else None)
        if d is None:
            ps.errors.append((off, "ngày không hợp lệ"))
        elif shift is None:
            ps.errors.append((off, "ca không hợp lệ (cần Sáng/Trưa/Tối)"))
        elif not names:
            ps.errors.append((off, "thiếu tên nhân viên"))
        else:
            ps.assignments.extend((d, shift, n) for n in names)
    return ps


def _parse_grid(rows, hi, cells, month) -> ParsedSchedule:
    ps = ParsedSchedule(layout="grid")
    # ưu tiên cột "Ngày"; nếu chỉ có cột "Thứ" thì tìm ngày trong đó
    date_cols = [cells.index(c) for c in ("ngày", "thứ") if c in cells]
    shift_cols = {j: SHIFT_ALIASES[c] for j, c in enumerate(cells) if c in SHIFT_ALIASES}
    for off, row in enumerate(rows[hi + 1:], start=hi + 2):
        if all(c in (None, "") for c in row):
            continue
        d = None
        for ci in date_cols:
            d = parse_date(row[ci] if ci < len(row) else None, month)
            if d is not None:
                break
        if d is None:
            ps.errors.append((off, "ngày không hợp lệ (cột Thứ cần kèm ngày cụ thể, ví dụ 'Thứ Hai, 03/11/2026')"))
            continue
        for j, shift in shift_cols.items():
            ps.assignments.extend((d, shift, n) for n in _split_names(row[j] if j < len(row) else None))
    return ps


def parse_xlsx(source, month: str | None = None) -> ParsedSchedule:
    import openpyxl
    wb = openpyxl.load_workbook(source, data_only=True, read_only=True)
    return parse_rows([list(r) for r in wb.worksheets[0].iter_rows(values_only=True)], month)


def parse_csv(data: bytes | str, month: str | None = None) -> ParsedSchedule:
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return parse_rows([r for r in csv.reader(io.StringIO(text), dialect)], month)


def map_names(raw_names: list[str], employees: dict[int, str], manual: dict[str, int] | None = None):
    """Trả (mapping raw->id, unmapped {raw: [gợi ý id]}). Khớp: sau chuẩn hóa NFC + không phân biệt hoa thường;
    gợi ý khi chỉ khác dấu. Tên lạ KHÔNG tự gán: người dùng phải ánh xạ tay (không lưu cho tới khi đủ)."""
    manual = manual or {}
    by_norm = {_norm(n): i for i, n in employees.items()}
    by_plain = {}
    for i, n in employees.items():
        by_plain.setdefault(_strip_accents(_norm(n)), []).append(i)
    mapping, unmapped = {}, {}
    for raw in raw_names:
        if raw in manual:
            mapping[raw] = manual[raw]
        elif _norm(raw) in by_norm:
            mapping[raw] = by_norm[_norm(raw)]
        else:
            unmapped[raw] = by_plain.get(_strip_accents(_norm(raw)), [])
    return mapping, unmapped


def replace_import_rows(schedule_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """Nạp lại cùng tháng thay các dòng source='import', giữ dòng owner/swap/auto_draft (không nhân đôi)."""
    kept = [r for r in schedule_rows if r.get("source") != "import"]
    return kept + [dict(r, source="import") for r in new_rows]
