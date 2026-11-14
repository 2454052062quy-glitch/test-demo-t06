#!/usr/bin/env python3
"""Sinh dữ liệu GIẢ LẬP vào data/mock/. Không chứa số liệu hay tên thật; chỉ mô phỏng cấu trúc.

  python scripts/generate_mock_data.py [--month 2026-10]
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
from datetime import date

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from backend.app.devtools.mockdata import fake_orders, pos_api_row, revenue_xlsx_bytes  # noqa: E402
from backend.app.services.schedule_template import flat_template, grid_template  # noqa: E402



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="2026-10")
    args = ap.parse_args()
    y, m = map(int, args.month.split("-"))
    days = [date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]
    out = os.path.join(ROOT, "data", "mock")
    os.makedirs(out, exist_ok=True)

    orders = fake_orders(days, per_day=8)
    with open(os.path.join(out, "chi_tiet_doanh_thu_mock.xlsx"), "wb") as f:
        f.write(revenue_xlsx_bytes(orders))
    with open(os.path.join(out, "pos_orders_api_mock.json"), "w", encoding="utf-8") as f:
        rows = [pos_api_row(o) for o in orders]
        json.dump({"__count": len(rows), "results": rows}, f, ensure_ascii=False, indent=1)

    # Lịch ca giả lập tháng 11/2026 theo ĐỊNH DẠNG 1 (lưới) để thử nạp ngay; kèm bản phẳng (định dạng 2)
    with open(os.path.join(out, "sample_schedule_2026_11.xlsx"), "wb") as f:
        f.write(grid_template("2026-11", fill_demo=True))
    with open(os.path.join(out, "sample_schedule_flat_2026_11.xlsx"), "wb") as f:
        f.write(flat_template("2026-11"))
    print(f"Đã tạo {len(orders)} đơn giả (tháng {args.month}) và 2 file lịch ca mẫu tháng 11/2026 trong data/mock/")


if __name__ == "__main__":
    main()
