import unittest
from datetime import date, datetime, timezone

from backend.app.config import AppConfig, unescape_dollars
from backend.app.services.timeutil import business_date, local_naive_to_utc, parse_iso_utc, to_vn


class TimeTests(unittest.TestCase):
    def test_parse_seven_digit_fraction(self):  # TC-R01-11 (định dạng API §5.1)
        dt = parse_iso_utc("2022-05-19T07:04:10.3400000Z")
        self.assertEqual(dt, datetime(2022, 5, 19, 7, 4, 10, 340000, tzinfo=timezone.utc))

    def test_early_morning_order_belongs_to_next_vn_day(self):  # TC-R01-11
        # 23:30Z ngày 18 = 06:30 ngày 19 giờ VN (quán mở 06:30)
        dt = parse_iso_utc("2022-05-18T23:30:00.0000000Z")
        self.assertEqual(business_date(dt), date(2022, 5, 19))
        self.assertEqual(to_vn(dt).hour, 6)

    def test_local_file_time_to_utc(self):
        self.assertEqual(local_naive_to_utc(datetime(2026, 11, 2, 6, 45)),
                         datetime(2026, 11, 1, 23, 45, tzinfo=timezone.utc))

    def test_empty_string_rejected(self):
        with self.assertRaises(ValueError):
            parse_iso_utc(" ")


class ConfigTests(unittest.TestCase):
    def test_unescape_compose_dollars(self):
        self.assertEqual(unescape_dollars("$$top"), "$top")
        self.assertEqual(unescape_dollars("$skip"), "$skip")

    def test_env_params_and_headers(self):
        c = AppConfig.from_env({"APP_MODE": "demo", "POS365_TOP_PARAM": "$$top", "POS365_SKIP_PARAM": "$$skip",
                                "POS365_PAGE_SIZE": "20", "POS365_AUTH_MODE": "none",
                                "POS365_EXTRA_HEADERS": '{"Cookie":"ss-id=abc"}'})
        self.assertEqual((c.pos365_top_param, c.pos365_skip_param, c.pos365_page_size), ("$top", "$skip", 20))
        self.assertEqual(c.pos365_extra_headers, {"Cookie": "ss-id=abc"})

    def test_live_cannot_disable_auth_or_roles(self):  # TC-E02-04, D17
        c = AppConfig.from_env({"APP_MODE": "live", "E01_ROLES": "false", "E02_AUTH": "0"})
        self.assertTrue(c.flags["E01_ROLES"] and c.flags["E02_AUTH"])

    def test_demo_may_disable(self):
        c = AppConfig.from_env({"APP_MODE": "demo", "E02_AUTH": "false"})
        self.assertFalse(c.flags["E02_AUTH"])

    def test_removed_extensions_have_no_flags(self):  # TC-SCOPE-01
        c = AppConfig.from_env({})
        for gone in ("E06_ALERT_HANDOVER", "E07_ALERT_PRICE", "E08_STOCK_ESTIMATE", "E10_ALERT_REVENUE", "E12_PUSH"):
            self.assertNotIn(gone, c.flags)

    def test_bad_mode_and_auth_mode(self):
        with self.assertRaises(ValueError):
            AppConfig.from_env({"APP_MODE": "prod"})
        with self.assertRaises(ValueError):
            AppConfig.from_env({"POS365_AUTH_MODE": "x"})


if __name__ == "__main__":
    unittest.main()
