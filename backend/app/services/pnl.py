"""Báo cáo lãi/lỗ tháng (R07, F07-B) và đối chiếu với cách tính thủ công (F07-C).

lãi/lỗ = doanh thu − nguyên liệu − lương − chi phí cố định − chi phí phát sinh
Mỗi nguồn chỉ có MỘT nơi ghi (không nhập tay nguyên liệu/lương ở báo cáo).
D1: Tháng hiện tại tính lương và chi phí cố định THEO SỐ NGÀY ĐÃ QUA (tỷ lệ ngày đã qua / tổng ngày).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

CATEGORIES = ("co_dinh", "phat_sinh")


@dataclass
class PnL:
    month: str
    revenue: int
    ingredients: int
    payroll: int
    fixed: int
    other: int
    missing: list = field(default_factory=list)
    # D1: Thông tin tạm tính cho tháng đang diễn ra
    is_current_month: bool = False
    as_of_day: int | None = None
    total_days: int | None = None
    prorated_label: str | None = None
    payroll_full: int | None = None
    fixed_full: int | None = None

    @property
    def total_cost(self) -> int:
        return self.ingredients + self.payroll + self.fixed + self.other

    @property
    def profit(self) -> int:
        return self.revenue - self.total_cost

    @property
    def complete(self) -> bool:
        return not self.missing


def compute_pnl(month: str, orders, purchases, payroll_amounts, expenses, as_of_date: date | None = None) -> PnL:
    """orders: iterable dict có business_date, paid.
    purchases: iterable dict có purchase_date, total_amount.
    payroll_amounts: iterable số tiền lương của tháng.
    expenses: iterable dict có expense_date, category, amount.
    as_of_date: ngày đối chiếu (mặc định hôm nay). Nếu as_of_date thuộc month, áp dụng D1 pro-rate."""
    rev = [o["paid"] for o in orders if o["business_date"].strftime("%Y-%m") == month]
    pur = [p["total_amount"] for p in purchases if p["purchase_date"].strftime("%Y-%m") == month]
    pay_raw = list(payroll_amounts)
    payroll_total = sum(pay_raw)

    fixed_total, other = 0, 0
    for e in expenses:
        if e["expense_date"].strftime("%Y-%m") != month:
            continue
        if e["category"] == "co_dinh":
            fixed_total += e["amount"]
        elif e["category"] == "phat_sinh":
            other += e["amount"]
        else:
            raise ValueError(f"nhóm chi phí không hợp lệ: {e['category']!r}")

    missing = []
    if not rev:
        missing.append("doanh thu POS (chưa đồng bộ/nạp)")
    if not pur:
        missing.append("nhập hàng")
    if not pay_raw:
        missing.append("lương (chưa có lịch ca)")

    # D1: Xử lý tạm tính theo số ngày đã qua nếu là tháng hiện tại
    is_current = False
    as_of_day = None
    total_days = None
    prorated_label = None
    payroll_effective = payroll_total
    fixed_effective = fixed_total

    if as_of_date and as_of_date.strftime("%Y-%m") == month:
        is_current = True
        y, m = int(month[:4]), int(month[5:7])
        total_days = calendar.monthrange(y, m)[1]
        as_of_day = min(as_of_date.day, total_days)
        prorated_label = f"Tạm tính đến ngày {as_of_day:02d}/{m:02d}"

        # Công thức D1: giá trị * (ngày đã qua / tổng số ngày trong tháng)
        if total_days > 0:
            payroll_effective = int(round(payroll_total * as_of_day / total_days))
            fixed_effective = int(round(fixed_total * as_of_day / total_days))

    return PnL(
        month=month,
        revenue=sum(rev),
        ingredients=sum(pur),
        payroll=payroll_effective,
        fixed=fixed_effective,
        other=other,
        missing=missing,
        is_current_month=is_current,
        as_of_day=as_of_day,
        total_days=total_days,
        prorated_label=prorated_label,
        payroll_full=payroll_total if is_current else None,
        fixed_full=fixed_total if is_current else None,
    )


def reconcile(pnl: PnL, manual: dict | None) -> dict:
    """manual: {'revenue','ingredients','payroll','fixed','other'} (trường nào để None thì chưa nhập)."""
    mine = {"revenue": pnl.revenue, "ingredients": pnl.ingredients, "payroll": pnl.payroll,
            "fixed": pnl.fixed, "other": pnl.other}
    out = {}
    for k, v in mine.items():
        m = (manual or {}).get(k)
        out[k] = {"system": v, "manual": m, "diff": None if m is None else v - m}
    return out
