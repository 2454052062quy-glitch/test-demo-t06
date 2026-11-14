import io
import unittest
from datetime import date, datetime, timezone

import openpyxl

from backend.app.devtools.mockdata import fake_orders, pos_api_row, revenue_xlsx_bytes
from backend.app.services.pos365 import normalize_order
from backend.app.services.pos_ingest import (ImportFormatError, daily_revenue, merge_orders, monthly_revenue,
                                             parse_csv, parse_money, parse_rows, parse_xlsx)

DAYS = [date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)]


class MoneyTests(unittest.TestCase):
    def test_formats(self):
        for raw, want in [(30000, 30000), (30000.0, 30000), ("30.000", 30000), ("1.234.000", 1234000),
                          ("1,234,000", 1234000), ("1.234.000,50", 1234001), ("1234000.00", 1234000),
                          ("30000 đ", 30000), ("", None), (None, None), ("(5.000)", -5000)]:
            self.assertEqual(parse_money(raw), want, raw)

    def test_garbage(self):
        with self.assertRaises(ValueError):
            parse_money("abc")


class FileImportTests(unittest.TestCase):
    def setUp(self):
        self.orders = fake_orders(DAYS, per_day=6)
        self.data = revenue_xlsx_bytes(self.orders)

    def test_xlsx_skips_title_summary_and_total_bands(self):  # TC-R01-03, TC-R01-09
        pf = parse_xlsx(io.BytesIO(self.data))
        self.assertEqual(len(pf.orders), len(self.orders))
        self.assertEqual(pf.skipped_total, 2)  # dải tổng dưới tiêu đề + cuối bảng
        self.assertTrue(all(o["source"] == "file" for o in pf.orders))

    def test_reconcile_with_header_summary(self):  # TC-R01-05
        pf = parse_xlsx(io.BytesIO(self.data))
        rec = pf.reconcile()
        self.assertTrue(rec["ok"])
        self.assertEqual(rec["order_count"]["parsed"], len(self.orders))

    def test_reconcile_detects_mismatch(self):
        bad = revenue_xlsx_bytes(self.orders, summary_paid=123)
        self.assertFalse(parse_xlsx(io.BytesIO(bad)).reconcile()["ok"])

    def test_no_summary_gives_none(self):
        pf = parse_xlsx(io.BytesIO(revenue_xlsx_bytes(self.orders, with_summary=False)))
        self.assertIsNone(pf.reconcile()["ok"])

    def test_missing_column_names_the_column(self):  # TC-R01-04
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Mã chứng từ", "Ngày tạo", "Tổng cộng"])
        ws.append(["HD1", datetime(2026, 11, 1, 8, 0), 1000])
        buf = io.BytesIO()
        wb.save(buf)
        with self.assertRaises(ImportFormatError) as ctx:
            parse_xlsx(io.BytesIO(buf.getvalue()))
        self.assertIn("Thanh toán", str(ctx.exception))

    def test_no_header_at_all(self):
        with self.assertRaises(ImportFormatError):
            parse_rows([["a", "b"], [1, 2]])

    def test_file_time_is_local_and_business_date_correct(self):
        pf = parse_xlsx(io.BytesIO(self.data))
        for src, got in zip(self.orders, pf.orders):
            self.assertEqual(got["business_date"], src["local"].date())  # kể cả đơn 06:30 sáng

    def test_csv_semicolon_and_vn_money(self):
        text = ("Mã chứng từ;Ngày tạo;Khách hàng;Phòng/Bàn;Số khách;Chiết khấu;Tổng cộng;Thanh toán\n"
                "HDMOCK-1;02/11/2026 06:45;;Bàn 1;2;0;35.000;35.000\n"
                ";;;;;;35.000;35.000\n")
        pf = parse_csv(text)
        self.assertEqual(len(pf.orders), 1)
        self.assertEqual((pf.orders[0]["paid"], pf.orders[0]["business_date"]), (35000, date(2026, 11, 2)))
        self.assertEqual(pf.skipped_total, 1)

    def test_bad_money_row_reported_not_fatal(self):
        rows = [["Mã chứng từ", "Ngày tạo", "Tổng cộng", "Thanh toán"],
                ["HD1", datetime(2026, 11, 1, 9, 0), "xx", 10], ["HD2", datetime(2026, 11, 1, 9, 5), 10, 10]]
        pf = parse_rows(rows)
        self.assertEqual(len(pf.orders), 1)
        self.assertEqual(len(pf.skipped_invalid), 1)


class DedupTests(unittest.TestCase):
    def setUp(self):
        self.orders = fake_orders(DAYS, per_day=6)
        self.file_orders = parse_xlsx(io.BytesIO(revenue_xlsx_bytes(self.orders))).orders
        self.api_orders = [normalize_order(pos_api_row(o)).order for o in self.orders]

    def test_import_twice_no_duplicates(self):  # TC-R01-06
        store = {}
        s1 = merge_orders(store, self.file_orders)
        s2 = merge_orders(store, self.file_orders)
        self.assertEqual((s1.inserted, s2.inserted, s2.duplicate), (len(self.orders), 0, len(self.orders)))
        self.assertEqual(len(store), len(self.orders))

    def test_api_after_file_no_duplicates(self):  # TC-R01-07
        store = {}
        merge_orders(store, self.file_orders)
        s = merge_orders(store, self.api_orders)
        self.assertEqual(s.inserted, 0)
        self.assertEqual(len(store), len(self.orders))
        self.assertTrue(all(o["pos_id"] is not None for o in store.values()))  # API bổ sung pos_id

    def test_file_never_overrides_api(self):
        store = {}
        merge_orders(store, self.api_orders)
        changed = [dict(self.file_orders[0], paid=1)]
        s = merge_orders(store, changed)
        self.assertEqual((s.conflict, s.updated), (1, 0))
        self.assertNotEqual(store[changed[0]["doc_code"]]["paid"], 1)

    def test_api_overrides_file_and_counts_update(self):
        store = {}
        merge_orders(store, self.file_orders)
        changed = dict(self.api_orders[0], paid=777)
        s = merge_orders(store, [changed])
        self.assertEqual(s.updated, 1)
        self.assertEqual(store[changed["doc_code"]]["paid"], 777)

    def test_same_minute_same_amount_different_code_warns(self):  # TC-R01-08, D19
        store = {}
        merge_orders(store, self.api_orders)
        clone = dict(self.api_orders[0], doc_code="OFFLINEMOCK-X")
        s = merge_orders(store, [clone])
        self.assertEqual(s.inserted, 1)
        self.assertTrue(any("khác mã" in w for w in s.warnings))

    def test_totals_equal_sum_of_days(self):  # TC-R01-12
        store = {}
        merge_orders(store, self.file_orders)
        daily = daily_revenue(store, "2026-11")
        self.assertEqual(sum(daily.values()), sum(o["paid"] for o in self.orders))
        self.assertEqual(monthly_revenue(store)["2026-11"], sum(daily.values()))

    def test_revenue_uses_paid_not_total(self):  # D07
        store = {}
        merge_orders(store, [dict(self.file_orders[0], total=100, paid=90, discount=10)])
        self.assertEqual(sum(daily_revenue(store).values()), 90)


if __name__ == "__main__":
    unittest.main()
