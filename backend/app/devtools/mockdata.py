"""Dữ liệu GIẢ LẬP (không có số liệu thật). Mô phỏng CẤU TRÚC file 'Chi tiết doanh thu' theo ảnh QS02:
tiêu đề, khối tổng ở H:I, dòng tiêu đề 8 cột, dải tổng ngay dưới tiêu đề và ở cuối bảng.
Mã chứng từ có tiền tố HDMOCK / OFFLINEMOCK (giả), không sao chép mã thật.

D2: Doanh thu mẫu tăng lên khoảng 2,2–2,8 triệu đồng/ngày (có biến động cuối tuần).
D3: Doanh thu trải theo ca: Ca Tối ≈ 40%, Sáng ≈ 30%, Trưa ≈ 30%.
A2: Đầy đủ thông tin Phòng/Bàn, Số khách, Chiết khấu, Tổng cộng, Thanh toán.
"""
from __future__ import annotations

import io
import random
from datetime import date, datetime, timedelta, timezone

from ..services.timeutil import VN_TZ

HEADER = ["Mã chứng từ", "Ngày tạo", "Khách hàng", "Phòng/Bàn", "Số khách", "Chiết khấu", "Tổng cộng", "Thanh toán"]

TABLES = [
    "Bàn 1", "Bàn 2", "Bàn 3", "Bàn 4", "Bàn 5", "Bàn 6", "Bàn 7", "Bàn 8",
    "Bàn 9", "Bàn 10", "Mang về", "Quầy bar"
]


def fake_orders(days: list[date], per_day: int | None = None, seed: int = 7) -> list[dict]:
    """Tạo đơn hàng giả lập.
    Nếu per_day được chỉ định, tạo đúng per_day đơn/ngày (tương thích test cũ).
    Nếu per_day là None, tạo doanh thu đạt 2,2 - 2,8 triệu đồng/ngày theo D2 và phân bổ theo D3.
    """
    rnd = random.Random(seed)
    out, n = [], 0

    if per_day is not None:
        for d in days:
            for _ in range(per_day):
                n += 1
                hh, mm = rnd.randint(6, 21), rnd.randint(0, 59)
                if hh == 6:
                    mm = max(mm, 30)  # quán mở 06:30 (CQ09)
                local = datetime(d.year, d.month, d.day, hh, mm, rnd.randint(0, 59), tzinfo=VN_TZ)
                total = rnd.choice([25, 30, 35, 45, 60, 90, 120]) * 1000
                disc = rnd.choice([0, 0, 0, 5000])
                prefix = "OFFLINEMOCK" if n % 7 == 0 else "HDMOCK"
                out.append({
                    "doc_code": f"{prefix}-{n:06d}",
                    "local": local,
                    "total": total,
                    "discount": disc,
                    "paid": total - disc,
                    "table": f"Bàn {rnd.randint(1, 12)}",
                    "guests": rnd.randint(1, 4),
                })
        return out

    for d in days:
        is_weekend = d.weekday() >= 5  # Thứ 7, CN
        target_day_rev = rnd.randint(2500, 2800) * 1000 if is_weekend else rnd.randint(2200, 2550) * 1000

        # Phân bổ doanh thu mục tiêu theo ca (D3: Tối ~40%, Sáng ~30%, Trưa ~30%)
        target_sang = int(target_day_rev * rnd.uniform(0.28, 0.32))
        target_trua = int(target_day_rev * rnd.uniform(0.28, 0.32))
        target_toi = target_day_rev - target_sang - target_trua

        shift_targets = [
            ("sang", (6, 30), (12, 0), target_sang),
            ("trua", (12, 0), (17, 30), target_trua),
            ("toi", (17, 30), (21, 30), target_toi),
        ]

        for s_code, (start_h, start_m), (end_h, end_m), s_target in shift_targets:
            curr_rev = 0
            start_total_m = start_h * 60 + start_m
            end_total_m = end_h * 60 + end_m

            while curr_rev < s_target:
                n += 1
                minute_offset = rnd.randint(0, end_total_m - start_total_m - 1)
                order_m = start_total_m + minute_offset
                hh = order_m // 60
                mm = order_m % 60
                ss = rnd.randint(0, 59)
                local = datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=VN_TZ)

                # Giá trị đơn từ 30.000 đến 160.000
                rem = s_target - curr_rev
                if rem <= 40000:
                    order_val = rem
                else:
                    order_val = rnd.choice([35, 40, 45, 55, 65, 80, 95, 120, 145]) * 1000

                # Chiết khấu 0 hoặc 5k-15k
                disc = rnd.choice([0, 0, 0, 5000, 10000]) if order_val > 50000 else 0
                paid = max(10000, order_val - disc)
                total = paid + disc
                curr_rev += paid

                prefix = "OFFLINEMOCK" if n % 8 == 0 else "HDMOCK"
                out.append({
                    "doc_code": f"{prefix}-{n:06d}",
                    "local": local,
                    "total": total,
                    "discount": disc,
                    "paid": paid,
                    "table": rnd.choice(TABLES),
                    "guests": rnd.randint(1, 5),
                    "shift_code": s_code,
                })

    return out


def pos_api_row(o: dict, status: int = 2) -> dict:
    """Một phần tử results của /api/orders (giả), PurchaseDate dạng UTC có Z như API §5.1."""
    utc = o["local"].astimezone(timezone.utc)
    return {
        "Id": 100000 + int(o["doc_code"][-6:]),
        "Code": o["doc_code"],
        "PurchaseDate": utc.strftime("%Y-%m-%dT%H:%M:%S.") + "3400000Z",
        "Status": status,
        "Total": float(o["total"]),
        "TotalPayment": float(o["paid"]),
        "Discount": float(o["discount"]),
        "Pos": o.get("table", "Bàn 1"),
        "NumberOfGuests": o.get("guests", 2),
    }


def revenue_xlsx_bytes(orders: list[dict], with_summary: bool = True, summary_paid: int | None = None) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MasterDocument"
    ws["A1"] = "CHI TIẾT DOANH THU"
    ws["A3"] = "Từ ngày"
    ws["A4"] = "Ngày lập báo cáo:"
    paid = sum(o["paid"] for o in orders) if summary_paid is None else summary_paid
    if with_summary:
        ws["H1"], ws["I1"] = "Số đơn hàng:", len(orders)
        ws["H2"], ws["I2"] = "Tổng giá trị:", sum(o["total"] for o in orders)
        ws["H3"], ws["I3"] = "Tổng thanh toán:", paid
        ws["H4"], ws["I4"] = "Tổng số khách:", sum(o["guests"] for o in orders)
    ws.append([])
    ws.append(HEADER)
    ws.append([None, None, None, None, None, None, sum(o["total"] for o in orders), paid])  # dải tổng dưới tiêu đề
    for o in orders:
        ws.append([o["doc_code"], o["local"].replace(tzinfo=None), None, o["table"], o["guests"],
                   o["discount"], o["total"], o["paid"]])
    ws.append([None, None, None, None, None, None, sum(o["total"] for o in orders), paid])  # dải tổng cuối bảng
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def schedule_long_xlsx_bytes(rows: list[tuple]) -> bytes:
    """rows: [(date, 'Sáng'|'Trưa'|'Tối', 'Tên')]"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Ngày", "Ca", "Nhân viên"])
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
