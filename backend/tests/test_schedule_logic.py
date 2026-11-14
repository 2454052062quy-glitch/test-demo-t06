import io
import unittest
from datetime import date, datetime, time
from decimal import Decimal

from backend.app.devtools.mockdata import schedule_long_xlsx_bytes
from backend.app.services import swaps as sw
from backend.app.services.payroll import compute_payroll
from backend.app.services.schedule_import import (ScheduleImportError, map_names, parse_csv, parse_rows,
                                                  parse_xlsx, replace_import_rows)
from backend.app.services.scheduler import auto_draft

D1, D2 = date(2026, 11, 3), date(2026, 11, 4)
NOW = datetime(2026, 11, 2, 20, 0)


def flat(schedule):
    return [(d, s, e) for (d, s), people in sorted(schedule.items()) for e in people]


class SwapTests(unittest.TestCase):
    def setUp(self):
        self.sch = {(D1, "sang"): [1], (D1, "trua"): [2], (D2, "sang"): [2]}

    def test_full_swap_updates_schedule_and_payroll_at_once(self):  # TC-R06-14, TC-R06-19
        before = compute_payroll(flat(self.sch), 10, 12)
        req = sw.create_request(1, self.sch, 1, "full_swap", D1, "sang", 3, "bận đột xuất")
        sw.approve(req, self.sch, decided_by=99, now=NOW)
        self.assertEqual(self.sch[(D1, "sang")], [3])
        after = compute_payroll(flat(self.sch), 10, 12)
        self.assertNotIn(1, after)
        self.assertEqual(after[3]["amount"], Decimal(10) * Decimal("5.5"))
        self.assertEqual(before[1]["n_sang"], 1)
        self.assertEqual(req.status, "approved")

    def test_two_way_swap(self):
        req = sw.create_request(1, self.sch, 1, "full_swap", D1, "sang", 2, counter_date=D2, counter_shift="sang")
        sw.approve(req, self.sch, 99, NOW)
        self.assertEqual((self.sch[(D1, "sang")], self.sch[(D2, "sang")]), ([2], [1]))

    def test_reject_keeps_schedule(self):  # TC-R06-17
        req = sw.create_request(1, self.sch, 1, "full_swap", D1, "sang", 3)
        sw.reject(req, 99, NOW, "thiếu người")
        self.assertEqual(self.sch[(D1, "sang")], [1])
        self.assertEqual(req.status, "rejected")

    def test_cannot_swap_someone_elses_shift(self):  # TC-R06-16
        with self.assertRaises(sw.SwapError):
            sw.create_request(1, self.sch, 3, "full_swap", D1, "sang", 2)

    def test_second_approval_has_no_effect(self):  # TC-R06-15 (mức logic; bản DB khóa dòng)
        req = sw.create_request(1, self.sch, 1, "full_swap", D1, "sang", 3)
        sw.approve(req, self.sch, 99, NOW)
        snapshot = {k: list(v) for k, v in self.sch.items()}
        with self.assertRaises(sw.SwapError):
            sw.approve(req, self.sch, 99, NOW)
        self.assertEqual(self.sch, snapshot)
        with self.assertRaises(sw.SwapError):
            sw.reject(req, 99, NOW)

    def test_approve_is_atomic_when_schedule_changed(self):
        req = sw.create_request(1, self.sch, 1, "full_swap", D1, "sang", 2, counter_date=D2, counter_shift="sang")
        self.sch[(D2, "sang")] = [5]  # lịch đổi giữa lúc chờ duyệt: người nhận không còn ca đối ứng
        snapshot = {k: list(v) for k, v in self.sch.items()}
        with self.assertRaises(sw.SwapError):
            sw.approve(req, self.sch, 99, NOW)
        self.assertEqual(self.sch, snapshot)
        self.assertEqual(req.status, "pending")

    def test_partial_cover_changes_nothing_but_flags(self):  # TC-R06-21, TC-R06-22
        before_sched = {k: list(v) for k, v in self.sch.items()}
        before_pay = compute_payroll(flat(self.sch), 10, 12)
        req = sw.create_request(7, self.sch, 1, "partial_cover", D1, "sang", 3, "đau bụng nửa ca",
                                from_time=time(9, 0), to_time=time(11, 45))
        self.assertEqual(sw.payroll_flags([req], "2026-11"), [])  # chưa duyệt: chưa có cờ
        sw.approve(req, self.sch, 99, NOW)
        self.assertEqual(self.sch, before_sched)
        self.assertEqual(compute_payroll(flat(self.sch), 10, 12), before_pay)
        flags = sw.payroll_flags([req], "2026-11")
        self.assertEqual(len(flags), 1)
        self.assertEqual((flags[0]["from_employee_id"], flags[0]["cover_employee_id"]), (1, 3))
        self.assertNotIn("amount", flags[0])  # D25: hệ thống không lưu/tính tiền điều chỉnh
        self.assertEqual(sw.payroll_flags([req], "2026-12"), [])

    def test_rejected_partial_cover_makes_no_flag(self):
        req = sw.create_request(7, self.sch, 1, "partial_cover", D1, "sang", 3)
        sw.reject(req, 99, NOW)
        self.assertEqual(sw.payroll_flags([req], "2026-11"), [])

    def test_cancel_only_by_requester_while_pending(self):
        req = sw.create_request(1, self.sch, 1, "full_swap", D1, "sang", 3)
        with self.assertRaises(sw.SwapError):
            sw.cancel(req, 2)
        sw.cancel(req, 1)
        self.assertEqual(req.status, "cancelled")
        with self.assertRaises(sw.SwapError):
            sw.approve(req, self.sch, 99, NOW)

    def test_validation(self):
        for kwargs in ({"kind": "khac"}, {"to_employee_id": 1}, {"shift_code": "dem"}):
            args = dict(kind="full_swap", work_date=D1, shift_code="sang", to_employee_id=3)
            args.update(kwargs)
            with self.assertRaises(sw.SwapError):
                sw.create_request(1, self.sch, 1, **args)
        with self.assertRaises(sw.SwapError):  # phụ giữa ca không có ca đối ứng
            sw.create_request(1, self.sch, 1, "partial_cover", D1, "sang", 3, counter_date=D2, counter_shift="sang")


def avail(*cells):
    return {c: True for c in cells}


class SchedulerTests(unittest.TestCase):
    def test_rule1_only_available(self):  # TC-E13-01
        a = avail((1, D1, "sang"))
        a[(2, D1, "sang")] = False  # bận
        r = auto_draft([D1], a, employees=[1, 2, 3])
        self.assertEqual(r.assignments, [(D1, "sang", 1)])
        self.assertIn((D1, "trua"), r.unassigned)  # không ai rảnh -> để trống

    def test_missing_declaration_means_unavailable(self):
        r = auto_draft([D1], {}, employees=[1, 2])
        self.assertEqual(r.assignments, [])
        self.assertEqual(len(r.unassigned), 3)

    def test_rule2_fairness_over_days(self):  # TC-E13-02
        days = [date(2026, 11, d) for d in range(1, 9)]
        a = {(e, d, "sang"): True for e in (1, 2, 3) for d in days}
        r = auto_draft(days, a)
        self.assertEqual(sorted(r.counts.values()), [2, 3, 3])  # 8 ca / 3 người

    def test_rule3_cluster_sang_trua(self):  # TC-E13-03
        a = {(1, D1, "sang"): True, (1, D1, "trua"): True, (2, D1, "sang"): True, (2, D1, "trua"): True}
        r = auto_draft([D1], a, employees=[1, 2])
        got = {(s, e) for _d, s, e in r.assignments}
        # sáng: hòa -> mã nhỏ (1); trưa: 1 đã có 1 ca, 2 có 0; slack=1 nên ghép cụm cho 1
        self.assertEqual(got, {("sang", 1), ("trua", 1)})

    def test_rule3_does_not_break_fairness_beyond_slack(self):
        # người 1 đã có 3 ca; sáng D1 chỉ người 1 rảnh nên nhận (thành 4 ca). Trưa D1 cả hai rảnh:
        # ghép cụm cho 1 sẽ vượt mức thấp nhất (0) + slack (1) -> nhường người 2.
        existing = {(date(2026, 11, 1), "sang"): [1], (date(2026, 11, 1), "trua"): [1],
                    (date(2026, 11, 2), "sang"): [1]}
        a = {(1, D1, "sang"): True, (1, D1, "trua"): True, (2, D1, "trua"): True}
        r = auto_draft([D1], a, existing=existing, employees=[1, 2])
        got = {s: e for _d, s, e in r.assignments}
        self.assertEqual((got["sang"], got["trua"]), (1, 2))
        # với slack lớn hơn thì ghép cụm thắng
        r2 = auto_draft([D1], a, existing=existing, employees=[1, 2], cluster_fairness_slack=10)
        self.assertEqual({s: e for _d, s, e in r2.assignments}["trua"], 1)

    def test_max_shifts_per_day(self):
        a = {(1, D1, s): True for s in ("sang", "trua", "toi")}
        r = auto_draft([D1], a, employees=[1], max_shifts_per_day=2)
        self.assertEqual(len(r.assignments), 2)
        self.assertEqual(r.unassigned, [(D1, "toi")])

    def test_keeps_existing_and_counts_them(self):
        existing = {(D1, "sang"): [1]}
        a = {(e, D2, "sang"): True for e in (1, 2)}
        r = auto_draft([D1, D2], a, existing=existing, employees=[1, 2])
        self.assertNotIn((D1, "sang", 2), r.assignments)
        self.assertIn((D2, "sang", 2), r.assignments)  # người 1 đã có ca, người 2 ít hơn

    def test_deterministic(self):  # TC-E13-05
        days = [date(2026, 11, d) for d in range(1, 6)]
        a = {(e, d, s): True for e in (1, 2, 3) for d in days for s in ("sang", "trua", "toi")}
        self.assertEqual(auto_draft(days, a).assignments, auto_draft(days, a).assignments)

    def test_capacity_two(self):
        a = {(e, D1, "sang"): True for e in (1, 2, 3)}
        r = auto_draft([D1], a, capacity={"sang": 2, "trua": 1, "toi": 1})
        self.assertEqual(len([x for x in r.assignments if x[1] == "sang"]), 2)


class ImportTests(unittest.TestCase):
    ROWS = [(date(2026, 11, 3), "Sáng", "Lan"), (date(2026, 11, 3), "Trưa", "Minh"), (date(2026, 11, 3), "Tối", "Lan")]

    def test_long_xlsx(self):  # TC-R06-03
        ps = parse_xlsx(io.BytesIO(schedule_long_xlsx_bytes(self.ROWS)))
        self.assertEqual(len(ps.assignments), 3)
        self.assertEqual((ps.assignments[0][1], ps.assignments[2][1]), ("sang", "toi"))
        self.assertEqual(ps.errors, [])

    def test_grid_csv_with_chieu_alias_and_short_dates(self):
        text = "Ngày,Sáng,Trưa,Chiều\n03/11,Lan,Minh,Lan\n04/11,Minh,,Hoa\n"
        ps = parse_csv(text, month="2026-11")
        self.assertEqual(len(ps.assignments), 5)
        self.assertEqual(ps.layout, "grid")
        self.assertIn((date(2026, 11, 4), "toi", "Hoa"), ps.assignments)

    def test_row_errors_reported(self):
        ps = parse_rows([["Ngày", "Ca", "Nhân viên"], ["x", "Sáng", "Lan"], [date(2026, 11, 3), "Đêm", "Lan"],
                         [date(2026, 11, 3), "Sáng", ""]])
        self.assertEqual([e[0] for e in ps.errors], [2, 3, 4])
        self.assertEqual(ps.assignments, [])

    def test_unknown_layout(self):
        with self.assertRaises(ScheduleImportError):
            parse_rows([["a", "b"]])

    def test_unmapped_names_not_auto_assigned(self):  # TC-R06-04
        ps = parse_rows([["Ngày", "Ca", "Nhân viên"], [date(2026, 11, 3), "Sáng", "Lan"],
                         [date(2026, 11, 3), "Trưa", "Ngoc Anh"]])
        mapping, unmapped = map_names(ps.raw_names, {1: "Lan", 2: "Ngọc Anh"})
        self.assertEqual(mapping, {"Lan": 1})
        self.assertEqual(unmapped, {"Ngoc Anh": [2]})  # gợi ý khác dấu, vẫn chờ người dùng chọn
        mapping2, unmapped2 = map_names(ps.raw_names, {1: "Lan", 2: "Ngọc Anh"}, manual={"Ngoc Anh": 2})
        self.assertEqual((mapping2["Ngoc Anh"], unmapped2), (2, {}))

    def test_case_and_space_insensitive_match(self):
        mapping, unmapped = map_names(["  lan "], {1: "Lan"})
        self.assertEqual((mapping, unmapped), ({"  lan ": 1}, {}))

    def test_reimport_replaces_only_import_rows(self):  # TC-R06-05
        old = [{"work_date": D1, "shift_code": "sang", "employee_id": 1, "source": "import"},
               {"work_date": D1, "shift_code": "trua", "employee_id": 2, "source": "swap"},
               {"work_date": D2, "shift_code": "sang", "employee_id": 3, "source": "owner"}]
        new = [{"work_date": D1, "shift_code": "sang", "employee_id": 1}]
        once = replace_import_rows(old, new)
        twice = replace_import_rows(once, new)
        self.assertEqual(len(once), 3)
        self.assertEqual(once, twice)
        self.assertEqual(sorted(r["source"] for r in twice), ["import", "owner", "swap"])

    def test_over_capacity(self):  # TC-R06-06
        ps = parse_rows([["Ngày", "Ca", "Nhân viên"], [D1, "Sáng", "Lan"], [D1, "Sáng", "Minh"], [D1, "Trưa", "Lan"]])
        self.assertEqual(ps.over_capacity(), [(D1, "sang")])
        self.assertEqual(ps.over_capacity({"sang": 2, "trua": 1, "toi": 1}), [])


if __name__ == "__main__":
    unittest.main()
