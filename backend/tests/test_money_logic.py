import unittest
from datetime import date, datetime
from decimal import Decimal

from backend.app.services import handover as ho
from backend.app.services.attendance import can_scan, make_token, next_kind, verify_token
from backend.app.services.duty import can, is_on_duty
from backend.app.services.payroll import compute_payroll
from backend.app.services.pnl import compute_pnl, reconcile

D = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 21, 30)


class PayrollTests(unittest.TestCase):
    def test_worked_example_345(self):  # TC-R06-18
        a = [(date(2026, 11, d), "sang", 1) for d in (1, 2, 3)]
        a += [(date(2026, 11, d), "trua", 1) for d in (4, 5)]
        a += [(date(2026, 11, 6), "toi", 1)]
        r = compute_payroll(a, 10, 12)[1]
        self.assertEqual((r["n_sang"], r["n_trua"], r["n_toi"]), (3, 2, 1))
        self.assertEqual(r["amount"], Decimal(345))  # 10*5.5*3 + 12*5.5*2 + 12*4*1

    def test_month_filter_and_multiple_people(self):
        a = [(date(2026, 10, 31), "sang", 1), (date(2026, 11, 1), "sang", 1), (date(2026, 11, 1), "trua", 2)]
        r = compute_payroll(a, 10, 12, month="2026-11")
        self.assertEqual(r[1]["n_sang"], 1)
        self.assertEqual(r[2]["amount"], Decimal(66))

    def test_rates_configurable(self):  # TC-R06-01
        a = [(D, "sang", 1)]
        self.assertEqual(compute_payroll(a, 20000, 0)[1]["amount"], Decimal(110000))

    def test_invalid_shift(self):
        with self.assertRaises(ValueError):
            compute_payroll([(D, "dem", 1)], 1, 1)

    def test_qr_logs_do_not_change_pay(self):  # TC-E09-02: compute_payroll không nhận log chấm công
        a = [(D, "sang", 1)]
        self.assertEqual(compute_payroll(a, 10, 12), compute_payroll(a, 10, 12))
        import inspect
        self.assertNotIn("attendance", " ".join(inspect.signature(compute_payroll).parameters))


class PnLTests(unittest.TestCase):
    def setUp(self):
        self.orders = [{"business_date": date(2026, 11, 1), "paid": 1_000_000},
                       {"business_date": date(2026, 11, 30), "paid": 500_000},
                       {"business_date": date(2026, 12, 1), "paid": 999}]
        self.purchases = [{"purchase_date": date(2026, 11, 30), "total_amount": 300_000},
                          {"purchase_date": date(2026, 10, 31), "total_amount": 5}]
        self.expenses = [{"expense_date": date(2026, 11, 30), "category": "co_dinh", "amount": 400_000},
                         {"expense_date": date(2026, 11, 15), "category": "phat_sinh", "amount": 50_000},
                         {"expense_date": date(2026, 12, 1), "category": "co_dinh", "amount": 7}]

    def test_hand_computed_month(self):  # TC-R07-03, TC-R07-02 (ranh giới tháng)
        p = compute_pnl("2026-11", self.orders, self.purchases, [200_000], self.expenses)
        self.assertEqual((p.revenue, p.ingredients, p.payroll, p.fixed, p.other),
                         (1_500_000, 300_000, 200_000, 400_000, 50_000))
        self.assertEqual(p.profit, 550_000)
        self.assertTrue(p.complete)

    def test_loss_is_negative(self):
        p = compute_pnl("2026-11", self.orders, self.purchases, [5_000_000], self.expenses)
        self.assertLess(p.profit, 0)

    def test_missing_sources_flagged_not_hidden(self):  # TC-R07-04
        p = compute_pnl("2026-11", self.orders, self.purchases, [], self.expenses)
        self.assertFalse(p.complete)
        self.assertTrue(any("lương" in m for m in p.missing))

    def test_bad_category(self):
        with self.assertRaises(ValueError):
            compute_pnl("2026-11", [], [], [], [{"expense_date": date(2026, 11, 1), "category": "x", "amount": 1}])

    def test_reconcile_per_group(self):  # TC-R07-05
        p = compute_pnl("2026-11", self.orders, self.purchases, [200_000], self.expenses)
        r = reconcile(p, {"revenue": 1_450_000, "ingredients": 300_000})
        self.assertEqual(r["revenue"]["diff"], 50_000)
        self.assertEqual(r["ingredients"]["diff"], 0)
        self.assertIsNone(r["payroll"]["diff"])  # chưa nhập -> để trống


class HandoverTests(unittest.TestCase):
    def make(self, **kw):
        base = dict(business_date=D, shift_code="trua", giver_id=1, pos_revenue_entered=1_000_000,
                    transfer_total=200_000, cash_handed=800_000)
        base.update(kw)
        return ho.Handover(**base)

    def test_no_computed_cash_field(self):  # TC-R03-03, D01: không có trường tự tính tiền két
        names = ho.field_names()
        self.assertFalse({"expected_cash", "variance", "difference", "chenh_lech"} & names)

    def test_stores_five_numbers_and_note(self):  # TC-R03-01
        h = self.make(shortage_refund=-20_000, extra=0, note="trả lại khách nhầm bill")
        ho.submit(h, NOW)
        self.assertEqual((h.pos_revenue_entered, h.transfer_total, h.shortage_refund, h.extra, h.cash_handed),
                         (1_000_000, 200_000, -20_000, 0, 800_000))

    def test_reason_required_when_nonzero(self):
        h = self.make(shortage_refund=-20_000)
        with self.assertRaises(ho.HandoverError):
            ho.submit(h, NOW)

    def test_negative_cash_rejected(self):
        with self.assertRaises(ho.HandoverError):
            ho.submit(self.make(cash_handed=-1), NOW)

    def test_cannot_self_confirm_and_status_flow(self):  # TC-R03-05, TC-R03-06
        h = self.make()
        with self.assertRaises(ho.HandoverError):
            ho.confirm(h, 2, NOW)  # chưa gửi
        ho.submit(h, NOW)
        with self.assertRaises(ho.HandoverError):
            ho.confirm(h, 1, NOW)  # tự xác nhận
        ho.confirm(h, 2, NOW)
        self.assertEqual((h.status, h.receiver_id), ("confirmed", 2))

    def test_locked_after_submit_until_owner_unlocks(self):  # TC-R03-04
        h = self.make()
        ho.submit(h, NOW)
        with self.assertRaises(ho.HandoverError):
            ho.edit(h, cash_handed=1)
        h.unlocked_by_owner = True
        ho.edit(h, cash_handed=1)
        self.assertEqual(h.cash_handed, 1)

    def test_cannot_edit_non_input_fields(self):
        with self.assertRaises(ho.HandoverError):
            ho.edit(self.make(), status="confirmed")


class PermissionTests(unittest.TestCase):
    ASSIGN = [(D, "trua", 7)]

    def test_on_duty_by_assignment(self):  # TC-E01-02
        self.assertTrue(is_on_duty(7, D, self.ASSIGN))
        self.assertFalse(is_on_duty(8, D, self.ASSIGN))
        self.assertFalse(is_on_duty(7, date(2026, 11, 4), self.ASSIGN))

    def test_staff_core_ops_need_duty(self):
        for perm in ("handover.write", "purchase.write", "ingredient.report"):
            self.assertTrue(can("staff", perm, on_duty=True), perm)
            self.assertFalse(can("staff", perm, on_duty=False), perm)

    def test_staff_cannot_do_owner_things(self):  # TC-AUTH-02
        for perm in ("pnl.view", "swaps.decide", "schedule.publish", "users.manage", "payroll.view_all",
                     "settings.edit", "pos.sync", "audit.view", "schedule.autodraft"):
            self.assertFalse(can("staff", perm, on_duty=True), perm)

    def test_staff_always_allowed(self):
        for perm in ("schedule.view", "availability.write", "swaps.request", "payroll.view_own", "attendance.scan"):
            self.assertTrue(can("staff", perm))

    def test_owner_all(self):
        self.assertTrue(can("owner", "pnl.view"))

    def test_reserved_roles_have_no_access(self):  # D02
        for role in ("shift_manager", "accountant", "ghost"):
            self.assertFalse(can(role, "schedule.view"))

    def test_unknown_permission_denied_for_staff(self):
        self.assertFalse(can("staff", "something.new", on_duty=True))

    def test_duty_requirement_can_be_relaxed_when_no_schedule(self):  # D23
        self.assertTrue(is_on_duty(9, D, [], duty_require_schedule=False))
        self.assertFalse(is_on_duty(9, D, [], duty_require_schedule=True))


class AttendanceTokenTests(unittest.TestCase):
    T0 = datetime(2026, 11, 3, 8, 0, 30)

    def test_valid_and_tampered(self):  # TC-E09-01
        tok = make_token("s3cret", self.T0)
        self.assertTrue(verify_token("s3cret", tok, self.T0))
        self.assertFalse(verify_token("khac", tok, self.T0))
        self.assertFalse(verify_token("s3cret", tok[:-1] + ("0" if tok[-1] != "0" else "1"), self.T0))
        self.assertFalse(verify_token("s3cret", "rac", self.T0))

    def test_expires(self):
        tok = make_token("s3cret", self.T0)
        self.assertTrue(verify_token("s3cret", tok, datetime(2026, 11, 3, 8, 1, 10)))
        self.assertFalse(verify_token("s3cret", tok, datetime(2026, 11, 3, 8, 5, 0)))

    def test_alternates_and_requires_assignment(self):
        self.assertEqual((next_kind(None), next_kind("in"), next_kind("out")), ("in", "out", "in"))
        self.assertFalse(can_scan(False))


if __name__ == "__main__":
    unittest.main()
