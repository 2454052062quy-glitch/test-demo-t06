import json
import threading
import unittest
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from backend.app.devtools.mockdata import fake_orders, pos_api_row
from backend.app.services.pos365 import (Pos365AuthError, Pos365Client, Pos365Error, fetch_all_orders,
                                         normalize_order, to_vnd)


class NormalizeTests(unittest.TestCase):
    def good(self, **kw):
        row = {"Id": 5, "Code": "HC190522-0008", "PurchaseDate": "2022-05-19T07:04:10.3400000Z", "Status": 2,
               "Total": 96185000.0000, "TotalPayment": 96000000.0000, "Discount": 185000.0000}
        row.update(kw)
        return row

    def test_mapping(self):  # TC-R01 ánh xạ
        r = normalize_order(self.good()).order
        self.assertEqual((r["doc_code"], r["paid"], r["total"], r["discount"]),
                         ("HC190522-0008", 96000000, 96185000, 185000))
        self.assertEqual(r["business_date"], date(2022, 5, 19))

    def test_total_rows_removed(self):  # TC-R01-09
        self.assertEqual(normalize_order(self.good(Id=-1)).skipped, "total")
        self.assertEqual(normalize_order(self.good(Code="Σ")).skipped, "total")

    def test_void_removed(self):  # TC-R01-10
        self.assertEqual(normalize_order(self.good(Status=3)).skipped, "void")

    def test_invalid(self):
        self.assertEqual(normalize_order(self.good(Code="")).skipped, "invalid")
        self.assertEqual(normalize_order(self.good(PurchaseDate="hỏng")).skipped, "invalid")

    def test_to_vnd(self):
        self.assertEqual(to_vnd(30000.0000), 30000)
        self.assertEqual(to_vnd(None), 0)


class PagingTests(unittest.TestCase):
    def make_pages(self, n):
        rows = [{"Id": i, "Code": f"C{i}"} for i in range(n)]
        calls = []

        def fetch(top, skip):
            calls.append((top, skip))
            return {"__count": n, "results": rows[skip:skip + top]}
        return rows, fetch, calls

    def test_all_pages_matching_count(self):  # TC-R01-01
        rows, fetch, calls = self.make_pages(45)
        res = fetch_all_orders(fetch, page_size=20)
        self.assertEqual(len(res.raw_rows), 45)
        self.assertEqual(res.count_reported, 45)
        self.assertEqual(calls, [(20, 0), (20, 20), (20, 40)])

    def test_exact_multiple_does_not_overfetch(self):
        _, fetch, calls = self.make_pages(40)
        fetch_all_orders(fetch, 20)
        self.assertEqual(len(calls), 2)

    def test_empty(self):
        _, fetch, _ = self.make_pages(0)
        self.assertEqual(fetch_all_orders(fetch, 20).raw_rows, [])

    def test_stops_on_empty_page_even_if_count_lies(self):
        def fetch(top, skip):
            return {"__count": 999, "results": [{"Id": 1, "Code": "X"}] if skip == 0 else []}
        self.assertEqual(len(fetch_all_orders(fetch, 20).raw_rows), 1)


class FakePos(BaseHTTPRequestHandler):
    orders: list = []
    expected_sid = "SID-1"
    logins = 0
    queries: list = []
    html_mode = False

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/auth/credentials":
            if q.get("Username") == ["admin"] and q.get("Password") == ["pw"]:
                FakePos.logins += 1
                FakePos.expected_sid = f"SID-{FakePos.logins}"
                return self._send(200, json.dumps({"SessionId": FakePos.expected_sid}))
            return self._send(401, json.dumps({"ResponseStatus": {"ErrorCode": "Unauthorized"}}))
        if u.path == "/api/orders":
            FakePos.queries.append(q)
            if FakePos.html_mode:
                return self._send(200, "<!doctype html><html>SPA</html>", "text/html")
            cookie = self.headers.get("Cookie", "")
            if f"ss-id={FakePos.expected_sid}" not in cookie:
                return self._send(401, "{}")
            top, skip = int(q["$top"][0]), int(q["$skip"][0])
            return self._send(200, json.dumps({"__count": len(FakePos.orders),
                                                "results": FakePos.orders[skip:skip + top]}))
        self._send(404, "{}")


class HttpClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakePos)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        days = [date(2026, 11, d) for d in range(1, 4)]
        FakePos.orders = [pos_api_row(o) for o in fake_orders(days, per_day=17)]  # 51 đơn -> 3 trang
        FakePos.logins, FakePos.expected_sid, FakePos.queries, FakePos.html_mode = 0, "SID-0", [], False

    def client(self, **kw):
        return Pos365Client(self.base, "admin", "pw", retry_sleep=0, **kw)

    def test_login_and_paging_with_dollar_params(self):  # TC-R01-01
        c = self.client()
        res = fetch_all_orders(c.get_orders_page, 20)
        self.assertEqual(len(res.raw_rows), 51)
        self.assertEqual(res.count_reported, 51)
        self.assertEqual([q["$top"] for q in FakePos.queries], [["20"]] * 3)
        self.assertEqual([q["$skip"] for q in FakePos.queries], [["0"], ["20"], ["40"]])

    def test_relogin_on_401(self):  # TC-R01-02
        c = self.client()
        c.get_orders_page(20, 0)
        self.assertEqual(FakePos.logins, 1)
        FakePos.expected_sid = "SID-EXPIRED"  # phiên hết hạn phía server
        res = c.get_orders_page(20, 20)
        self.assertEqual(len(res["results"]), 20)
        self.assertEqual(FakePos.logins, 2)

    def test_wrong_password_raises_auth_error(self):
        c = Pos365Client(self.base, "admin", "sai", retry_sleep=0)
        with self.assertRaises(Pos365AuthError):
            c.login()

    def test_auth_mode_none_uses_static_cookie_without_login(self):  # Static Header Injection
        FakePos.expected_sid = "STATIC"
        c = self.client(auth_mode="none", extra_headers={"Cookie": "ss-id=STATIC"})
        res = c.get_orders_page(20, 0)
        self.assertEqual(len(res["results"]), 20)
        self.assertEqual(FakePos.logins, 0)

    def test_html_response_gives_clear_error_not_jsondecodeerror(self):
        FakePos.html_mode = True
        c = self.client(auth_mode="none", extra_headers={"Cookie": "ss-id=x"})
        with self.assertRaises(Pos365Error) as ctx:
            c.get_orders_page(20, 0)
        self.assertIn("không phải JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakePos)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_probe_report_has_structure_only(self):
        from backend.tools_probe_pos365 import probe
        days = [date(2026, 11, d) for d in range(1, 4)]
        FakePos.orders = [pos_api_row(o) for o in fake_orders(days, per_day=17)]
        FakePos.orders.append({"Id": -1, "Code": "Σ", "PurchaseDate": "2026-11-03T10:00:00.0000000Z", "Status": 2})
        FakePos.logins, FakePos.expected_sid, FakePos.queries, FakePos.html_mode = 0, "SID-0", [], False
        rep = probe(Pos365Client(self.base, "admin", "pw", retry_sleep=0), pages=3)
        self.assertEqual(rep["rows_fetched"], 52)
        self.assertEqual(rep["total_like_rows"], 1)
        self.assertEqual(rep["status_values"], {"2": 52})
        self.assertTrue(rep["purchase_date_suffix_z"])
        flat = json.dumps(rep, ensure_ascii=False)
        self.assertNotIn("HDMOCK-", flat)  # không lọt mã đơn vào báo cáo
        self.assertIn("Status", rep["top_level_keys"])
