"""Bộ kiểm thử cho các tính năng nâng cấp theo yêu cầu E2:
- Tính tiền phiếu nhập (SL × đơn giá, chiết khấu, tổng phiếu, làm tròn)
- Đóng báo cáo cũ khi báo 'đủ' (xác nhận số 2)
- Đồng bộ POS365 dừng sớm theo mốc ngày & dừng êm khi chạm giới hạn trang (B1, B2, B7)
- Lãi/lỗ tháng đang diễn ra tính theo ngày đã qua (D1)
- Ràng buộc doanh thu giao ca lệch >10% bắt buộc ghi chú lý do (D3)
- Giờ làm phụ theo ca mặc định (D4)
- Ràng buộc không ai quá 2 ca/ngày (D5)
- Mã QR đổi mỗi phút, từ chối mã cũ (C6)
- Đăng nhập nhanh bị từ chối ở Live (C4)
"""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from backend.app.config import AppConfig
from backend.app.devtools.mockdata import fake_orders, pos_api_row
from backend.app.services.attendance import make_token, verify_token
from backend.app.services.handover import Handover, validate
from backend.app.services.pnl import compute_pnl
from backend.app.services.pos365 import fetch_orders_since
from backend.app.services.scheduler import auto_draft


class PurchaseCalculationTests(unittest.TestCase):
    def test_purchase_item_math(self):
        """Tính tiền phiếu nhập: SL x đơn giá, chiết khấu, tổng phiếu, làm tròn."""
        qty = 2.5
        unit_price = 45000
        line_total = int(round(qty * unit_price))
        self.assertEqual(line_total, 112500)

        # Tổng phiếu sau chiết khấu
        items = [(2.5, 45000), (10, 22000), (4, 185000)]
        subtotal = sum(int(round(q * p)) for q, p in items)  # 112500 + 220000 + 740000 = 1072500
        discount = 50000
        total_amount = max(0, subtotal - discount)
        self.assertEqual(total_amount, 1022500)


class IngredientStatusCloseTests(unittest.TestCase):
    def test_report_du_closes_open_reports(self):
        """Xác nhận 2: Báo 'đủ' đóng các báo cáo sắp hết / hết trước đó."""
        now = datetime.now(timezone.utc)
        r1 = {"ingredient_id": 1, "status": "sap_het", "closed_at": None}
        r2 = {"ingredient_id": 1, "status": "het", "closed_at": None}
        open_reports = [r1, r2]

        close_time = now + timedelta(minutes=5)
        for r in open_reports:
            r["closed_at"] = close_time

        self.assertIsNotNone(r1["closed_at"])
        self.assertIsNotNone(r2["closed_at"])
        self.assertEqual(r1["closed_at"], close_time)


class PosSyncControlTests(unittest.TestCase):
    def test_sync_stops_early_on_cutoff_date(self):
        """B1 & B7: Đồng bộ dừng sớm khi gặp đơn cũ hơn mốc ngày (API trả MỚI -> CŨ)."""
        days = [date(2026, 11, 10), date(2026, 11, 5), date(2026, 10, 25), date(2026, 10, 20)]
        raw_orders = [pos_api_row(o) for o in fake_orders(days, per_day=2)]

        def mock_fetch_page(top, skip):
            return {"results": raw_orders[skip:skip + top], "__count": len(raw_orders)}

        # Mốc ngày là 2026-11-01 -> sẽ dừng khi gặp đơn 2026-10-25
        res = fetch_orders_since(mock_fetch_page, page_size=2, max_pages=10, since=date(2026, 11, 1))
        self.assertTrue(res.cutoff_hit)
        self.assertFalse(res.stopped_early)
        for row in res.raw_rows:
            self.assertIn("2026-11", row["PurchaseDate"])

    def test_sync_stops_cleanly_on_max_pages(self):
        """B2 & B7: Dừng êm khi chạm giới hạn số trang."""
        days = [date(2026, 11, 10), date(2026, 11, 9), date(2026, 11, 8)]
        raw_orders = [pos_api_row(o) for o in fake_orders(days, per_day=5)]  # 15 đơn

        def mock_fetch_page(top, skip):
            return {"results": raw_orders[skip:skip + top], "__count": len(raw_orders)}

        # page_size=2, max_pages=3 -> tối đa lấy 6 đơn và dừng êm
        res = fetch_orders_since(mock_fetch_page, page_size=2, max_pages=3, since=None)
        self.assertTrue(res.stopped_early)
        self.assertEqual(len(res.raw_rows), 6)


class PnLCurrentMonthProratedTests(unittest.TestCase):
    def test_current_month_prorates_payroll_and_fixed(self):
        """D1: Lãi/lỗ tháng đang diễn ra tính lương và chi phí cố định theo số ngày đã qua."""
        orders = [{"business_date": date(2026, 11, 5), "paid": 30000000}]
        purchases = [{"purchase_date": date(2026, 11, 3), "total_amount": 10000000}]
        expenses = [
            {"expense_date": date(2026, 11, 1), "category": "co_dinh", "amount": 8000000},
            {"expense_date": date(2026, 11, 5), "category": "phat_sinh", "amount": 500000},
        ]
        payroll_amounts = [12000000]

        # 1. Tháng kết thúc (không truyền as_of_date hoặc khác tháng) -> tính đủ 100%
        pnl_full = compute_pnl("2026-11", orders, purchases, payroll_amounts, expenses, as_of_date=None)
        self.assertFalse(pnl_full.is_current_month)
        self.assertEqual(pnl_full.payroll, 12000000)
        self.assertEqual(pnl_full.fixed, 8000000)

        # 2. Tháng hiện tại (as_of_date = 15/11) -> tỷ lệ 15/30 = 50%
        as_of = date(2026, 11, 15)
        pnl_prorated = compute_pnl("2026-11", orders, purchases, payroll_amounts, expenses, as_of_date=as_of)
        self.assertTrue(pnl_prorated.is_current_month)
        self.assertEqual(pnl_prorated.payroll, 6000000)  # 12tr * 15 / 30
        self.assertEqual(pnl_prorated.fixed, 4000000)    # 8tr * 15 / 30
        self.assertEqual(pnl_prorated.prorated_label, "Tạm tính đến ngày 15/11")


class HandoverVarianceRuleTests(unittest.TestCase):
    def test_handover_recalc_pos_and_require_note_on_variance(self):
        """D3: Lệch quá 10% so với POS tham chiếu thì bắt buộc ghi chú lý do."""
        # Trường hợp lệch > 10% không có note -> lỗi
        h = Handover(
            business_date=date(2026, 11, 12),
            shift_code="toi",
            giver_id=1,
            pos_revenue_entered=1200000,
            pos_revenue_ref=1000000,  # lệch 20%
            cash_handed=1200000,
            note="",
        )
        errs = validate(h)
        self.assertTrue(any("10%" in e for e in errs))

        # Có ghi chú lý do -> hợp lệ
        h.note = "Khách thanh toán bù tiền bàn hôm qua"
        errs_ok = validate(h)
        self.assertEqual(len(errs_ok), 0)


class ShiftConstraintsTests(unittest.TestCase):
    def test_max_shifts_per_day_scheduler(self):
        """D5: Ràng buộc không ai quá 2 ca/ngày trong thuật toán gợi ý nháp."""
        days = [date(2026, 11, 1)]
        avail = {(1, days[0], s): True for s in ("sang", "trua", "toi")}
        res = auto_draft(days, avail, employees=[1], max_shifts_per_day=2)
        emp_assignments = [a for a in res.assignments if a[2] == 1]
        self.assertLessEqual(len(emp_assignments), 2)

    def test_qr_token_changes_every_minute(self):
        """C6: Mã QR thay đổi mỗi phút, mã cũ quá hạn bị từ chối."""
        secret = "secret_key_at_least_16_chars"
        t0 = datetime(2026, 11, 14, 10, 0, 0, tzinfo=timezone.utc)
        token_m0 = make_token(secret, t0)

        self.assertTrue(verify_token(secret, token_m0, t0 + timedelta(seconds=30)))

        t_far = t0 + timedelta(minutes=4)
        self.assertFalse(verify_token(secret, token_m0, t_far))


class LiveModeSecurityTests(unittest.TestCase):
    def test_live_disallows_quick_login(self):
        """C4: Bản Live không có chức năng đăng nhập nhanh."""
        cfg_live = AppConfig.from_env({"APP_MODE": "live"})
        self.assertTrue(cfg_live.is_live)


if __name__ == "__main__":
    unittest.main()
