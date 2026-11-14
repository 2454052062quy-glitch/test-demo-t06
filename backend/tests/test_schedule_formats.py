import io
import unittest
from datetime import date, datetime

import openpyxl

from backend.app.services.schedule_import import (ScheduleImportError, map_names, parse_csv, parse_date,
                                                  parse_rows, parse_xlsx)
from backend.app.services.schedule_template import grid_template, flat_template, template_bytes

SAMPLE = "data/mock/sample_schedule_2026_11.xlsx"


class GridFormatTests(unittest.TestCase):
    def test_sample_file_defined_by_user_parses(self):  # F06-B định dạng 1
        ps = parse_xlsx(SAMPLE, month="2026-11")
        self.assertEqual(ps.layout, "grid")
        self.assertEqual(ps.errors, [])
        self.assertEqual(len(ps.assignments), 30 * 3)  # 30 ngày × 3 ca, đã xếp đủ
        self.assertEqual(ps.raw_names, ["Nhân viên A", "Nhân viên B", "Nhân viên C", "Nhân viên D"])
        self.assertEqual(ps.over_capacity(), [])
        self.assertEqual(min(d for d, _s, _n in ps.assignments), date(2026, 11, 1))
        self.assertEqual(max(d for d, _s, _n in ps.assignments), date(2026, 11, 30))

    def test_no_one_works_three_shifts_in_sample(self):
        ps = parse_xlsx(SAMPLE, month="2026-11")
        per_day = {}
        for d, _s, n in ps.assignments:
            per_day[(d, n)] = per_day.get((d, n), 0) + 1
        self.assertLessEqual(max(per_day.values()), 2)

    def test_grid_template_round_trips(self):
        for fill in (False, True):
            ps = parse_xlsx(io.BytesIO(grid_template("2026-11", fill_demo=fill)), month="2026-11")
            self.assertEqual(ps.errors, [])
            self.assertEqual(ps.layout, "grid")
        self.assertEqual(len(parse_xlsx(io.BytesIO(grid_template("2026-11")), "2026-11").assignments), 6)

    def test_header_variants_ca_sang_and_thu_with_embedded_date(self):
        rows = [["Thứ", "Ca Sáng", "Ca Trưa", "Ca Tối"],
                ["Thứ Hai, 02/11/2026", "Lan", None, "Minh"],
                ["T3 03/11", "Minh", "Lan", None]]
        ps = parse_rows(rows, month="2026-11")
        self.assertEqual(ps.errors, [])
        self.assertIn((date(2026, 11, 3), "trua", "Lan"), ps.assignments)
        self.assertEqual(len(ps.assignments), 4)

    def test_thu_only_without_date_is_reported(self):
        ps = parse_rows([["Thứ", "Ca Sáng", "Ca Trưa", "Ca Tối"], ["Thứ Hai", "Lan", None, None]], month="2026-11")
        self.assertEqual(ps.assignments, [])
        self.assertEqual(len(ps.errors), 1)

    def test_ngay_column_wins_over_thu(self):
        rows = [["Thứ", "Ngày", "Ca Sáng", "Ca Trưa", "Ca Tối"],
                ["Thứ Hai", datetime(2026, 11, 2), "Lan", None, None]]
        self.assertEqual(parse_rows(rows).assignments, [(date(2026, 11, 2), "sang", "Lan")])

    def test_multiple_names_in_cell_and_over_capacity(self):
        ps = parse_rows([["Ngày", "Ca Sáng", "Ca Trưa", "Ca Tối"], [date(2026, 11, 2), "Lan, Minh", None, None]])
        self.assertEqual(len(ps.assignments), 2)
        self.assertEqual(ps.over_capacity(), [(date(2026, 11, 2), "sang")])


class FlatFormatTests(unittest.TestCase):
    def test_header_names_ma_ca_and_ten_nhan_vien(self):  # định dạng 2
        rows = [["Ngày", "Mã ca", "Tên nhân viên"], ["2026-11-02", "Sáng", "Lan"], ["03/11/2026", "Trưa", "Minh"],
                [datetime(2026, 11, 4), "Tối", "Hoa"]]
        ps = parse_rows(rows)
        self.assertEqual(ps.layout, "long")
        self.assertEqual(ps.errors, [])
        self.assertEqual([d for d, _s, _n in ps.assignments], [date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4)])

    def test_csv_flat_with_dd_mm_yyyy(self):
        ps = parse_csv("Ngày,Mã ca,Tên nhân viên\n03/11/2026,Sáng,Lan\n", month="2026-11")
        self.assertEqual(ps.assignments, [(date(2026, 11, 3), "sang", "Lan")])

    def test_flat_template_round_trips(self):
        ps = parse_xlsx(io.BytesIO(flat_template("2026-11")))
        self.assertEqual((ps.layout, len(ps.assignments), ps.errors), ("long", 3, []))

    def test_sample_flat_file(self):
        ps = parse_xlsx("data/mock/sample_schedule_flat_2026_11.xlsx")
        self.assertEqual(len(ps.assignments), 3)

    def test_template_bytes_dispatch(self):
        self.assertTrue(template_bytes("grid", "2026-11")[:2] == b"PK")  # xlsx là zip
        with self.assertRaises(ValueError):
            template_bytes("khac", "2026-11")


class DateTests(unittest.TestCase):
    def test_parse_date_forms(self):
        for raw, want in [("2026-11-02", date(2026, 11, 2)), ("02/11/2026", date(2026, 11, 2)),
                          (datetime(2026, 11, 2, 0, 0), date(2026, 11, 2)),
                          ("Chủ Nhật, 01/11/2026", date(2026, 11, 1)), ("T2 02/11", None)]:
            self.assertEqual(parse_date(raw), want, raw)
        self.assertEqual(parse_date("T2 02/11", "2026-11"), date(2026, 11, 2))
        self.assertIsNone(parse_date("31/02/2026"))

    def test_unknown_layout_message_mentions_template(self):
        with self.assertRaises(ScheduleImportError) as ctx:
            parse_rows([["a", "b"]])
        self.assertIn("file mẫu", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
