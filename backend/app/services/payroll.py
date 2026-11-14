"""Tính lương theo ca (CQ05, NV06, R06).

lương = a × 5,5 × (số ca sáng) + b × 5,5 × (số ca trưa) + b × 4,0 × (số ca tối)
Số giờ mỗi ca và mức a, b do chủ quán cấu hình (D05, D06); mặc định theo CQ05.
Giờ công LẤY TỪ LỊCH CA ĐÃ DUYỆT, không từ chấm công QR (ràng buộc E-09).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DEFAULT_HOURS = {"sang": Decimal("5.5"), "trua": Decimal("5.5"), "toi": Decimal("4.0")}
# a áp dụng cho ca sáng; b áp dụng cho ca trưa và ca tối (CQ05)
RATE_KEY = {"sang": "a", "trua": "b", "toi": "b"}


def compute_employee_pay(counts: dict, rate_a, rate_b, hours: dict | None = None) -> Decimal:
    hours = hours or DEFAULT_HOURS
    rates = {"a": Decimal(str(rate_a)), "b": Decimal(str(rate_b))}
    total = Decimal(0)
    for shift, n in counts.items():
        if shift not in RATE_KEY:
            raise ValueError(f"ca không hợp lệ: {shift!r}")
        total += rates[RATE_KEY[shift]] * Decimal(str(hours[shift])) * int(n)
    return total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def compute_payroll(assignments, rate_a, rate_b, hours: dict | None = None, month: str | None = None) -> dict:
    """assignments: iterable (work_date, shift_code, employee_id). Trả {employee_id: {...}}."""
    result: dict = {}
    for work_date, shift, emp in assignments:
        if month and work_date.strftime("%Y-%m") != month:
            continue
        r = result.setdefault(emp, {"sang": 0, "trua": 0, "toi": 0})
        if shift not in r:
            raise ValueError(f"ca không hợp lệ: {shift!r}")
        r[shift] += 1
    out = {}
    for emp, counts in result.items():
        out[emp] = {"n_sang": counts["sang"], "n_trua": counts["trua"], "n_toi": counts["toi"],
                    "amount": compute_employee_pay(counts, rate_a, rate_b, hours)}
    return out
