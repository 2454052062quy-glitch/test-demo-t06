"""Sinh file mẫu .xlsx cho F06-B (nút "Tải file mẫu .xlsx"). Chỉ dùng tên giả."""
from __future__ import annotations

import calendar
import io
from datetime import date

WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
SHIFT_LABEL = {"sang": "Sáng", "trua": "Trưa", "toi": "Tối"}
DEMO_NAMES = ["Nhân viên A", "Nhân viên B", "Nhân viên C", "Nhân viên D"]

GUIDE = [
    "HƯỚNG DẪN NẠP LỊCH CA",
    "Dạng 1 (lưới): sheet đầu tiên có cột Thứ, Ngày, Ca Sáng, Ca Trưa, Ca Tối. Mỗi ô là tên nhân viên.",
    "Nhiều người trong một ca: ngăn cách bằng dấu phẩy. Ô trống = chưa xếp.",
    "Dạng 2 (phẳng): cột Ngày (YYYY-MM-DD hoặc DD/MM/YYYY), Mã ca (Sáng/Trưa/Tối), Tên nhân viên.",
    "Tên phải khớp danh sách nhân viên; tên lạ sẽ được hỏi để ghép tay, hệ thống không tự đoán.",
    "Chỉ sheet đầu tiên được đọc. Sheet này chỉ để hướng dẫn.",
]


def _month_days(month: str) -> list[date]:
    y, m = int(month[:4]), int(month[5:7])
    return [date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]


def grid_template(month: str, fill_demo: bool = False) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lịch ca"
    ws.append(["Thứ", "Ngày", "Ca Sáng", "Ca Trưa", "Ca Tối"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5D50")
        c.alignment = Alignment(horizontal="center")
    for i, d in enumerate(_month_days(month)):
        row = [WEEKDAYS[d.weekday()], d, None, None, None]
        if fill_demo:
            # ví dụ: mỗi ca một người, xoay vòng, không ai làm quá 2 ca một ngày
            row[2:5] = [DEMO_NAMES[(i + j) % len(DEMO_NAMES)] for j in range(3)]
        elif i < 2:
            row[2:5] = [DEMO_NAMES[0], DEMO_NAMES[1], DEMO_NAMES[2]]
        ws.append(row)
        ws.cell(row=ws.max_row, column=2).number_format = "dd/mm/yyyy"
    for col, w in zip("ABCDE", (12, 14, 18, 18, 18)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    g = wb.create_sheet("Hướng dẫn")
    for line in GUIDE:
        g.append([line])
    g.column_dimensions["A"].width = 100
    g["A1"].font = Font(bold=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def flat_template(month: str) -> bytes:
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lịch ca"
    ws.append(["Ngày", "Mã ca", "Tên nhân viên"])
    for c in ws[1]:
        c.font = Font(bold=True)
    days = _month_days(month)
    for j, label in enumerate(("Sáng", "Trưa", "Tối")):
        ws.append([days[0], label, DEMO_NAMES[j]])
        ws.cell(row=ws.max_row, column=1).number_format = "yyyy-mm-dd"
    g = wb.create_sheet("Hướng dẫn")
    for line in GUIDE:
        g.append([line])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def template_bytes(kind: str, month: str) -> bytes:
    if kind == "grid":
        return grid_template(month)
    if kind == "flat":
        return flat_template(month)
    raise ValueError("kind phải là 'grid' hoặc 'flat'")
