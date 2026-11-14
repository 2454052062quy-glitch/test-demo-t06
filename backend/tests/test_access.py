import unittest

from backend.app.services.duty import DEFAULT_DUTY_STRICT, evaluate_access


class AccessTests(unittest.TestCase):
    def test_default_is_not_strict(self):  # D23 chốt 12/11
        self.assertFalse(DEFAULT_DUTY_STRICT)

    def test_off_schedule_is_saved_with_flag_not_403(self):
        for perm in ("handover.write", "purchase.write", "ingredient.report"):
            d = evaluate_access("staff", perm, assigned_today=False)
            self.assertTrue(d.allowed, perm)
            self.assertTrue(d.out_of_schedule, perm)

    def test_on_schedule_has_no_flag(self):
        d = evaluate_access("staff", "handover.write", assigned_today=True)
        self.assertEqual((d.allowed, d.out_of_schedule), (True, False))

    def test_strict_mode_blocks(self):
        d = evaluate_access("staff", "purchase.write", assigned_today=False, strict=True)
        self.assertFalse(d.allowed)

    def test_strict_mode_still_allows_on_schedule(self):
        self.assertTrue(evaluate_access("staff", "purchase.write", True, strict=True).allowed)

    def test_owner_never_flagged(self):
        d = evaluate_access("owner", "handover.write", assigned_today=False, strict=True)
        self.assertEqual((d.allowed, d.out_of_schedule), (True, False))

    def test_relaxed_duty_does_not_open_owner_only_routes(self):
        for perm in ("pnl.view", "swaps.decide", "users.manage", "settings.edit", "payroll.view_all"):
            self.assertFalse(evaluate_access("staff", perm, True).allowed, perm)
            self.assertFalse(evaluate_access("staff", perm, False).allowed, perm)

    def test_reserved_roles_denied(self):
        self.assertFalse(evaluate_access("accountant", "handover.write", True).allowed)


if __name__ == "__main__":
    unittest.main()
