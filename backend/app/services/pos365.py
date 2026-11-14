"""Tích hợp POS365 (API Specification Doc v1.0, §1, §2, §5.1).

- Xác thực: GET /api/auth/credentials?format=json -> SessionId, gửi lại qua Header Cookie: ss-id=<SessionId>.
- POS365_AUTH_MODE=none: bỏ bước đăng nhập, dùng header tĩnh POS365_EXTRA_HEADERS (vd {"Cookie":"ss-id=..."}).
- Phân trang: $top, $skip; tổng số dòng ở trường __count. API trả MỚI -> CŨ.
- Dòng tổng (Id = -1 hoặc Code = "Σ") và đơn hủy bị loại. Hai quy tắc này là kết quả
  thực nghiệm của nhóm, KHÔNG có trong PDF (D08); Status = 2 chỉ có từ ví dụ trong PDF.
- B1: dừng sớm khi gặp đơn cũ hơn mốc ngày (API trả mới->cũ).
- B2: giới hạn số trang tối đa mỗi lần đồng bộ (POS365_SYNC_MAX_PAGES).
- B3: timeout cấu hình được (POS365_REQUEST_TIMEOUT).
- A3: bổ sung bàn (Pos/RoomId) và số khách (NumberOfGuests) vào đơn.
"""
from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Callable

from .timeutil import VN_TZ, business_date, parse_iso_utc

ORDER_FIELD_MAP = {
    "doc_code": "Code",
    "created_at": "PurchaseDate",
    "paid": "TotalPayment",
    "total": "Total",
    "discount": "Discount",
}
VALID_STATUS = 2  # ví dụ trong API §5.1/§5.3; chưa có bảng giá trị chính thức (D08)
TOTAL_ROW_CODE = "Σ"
TOTAL_ROW_ID = -1


class Pos365Error(Exception):
    pass


class Pos365AuthError(Pos365Error):
    """HTTP 401: SessionId hết hạn hoặc sai tài khoản."""


def to_vnd(value) -> int:
    """POS365 trả 0.0000; làm tròn về đồng."""
    if value is None or value == "":
        return 0
    try:
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError) as exc:
        raise Pos365Error(f"giá trị tiền không hợp lệ: {value!r}") from exc


@dataclass
class NormalizeResult:
    order: dict | None
    skipped: str | None = None  # None | 'total' | 'void' | 'invalid'


def normalize_order(raw: dict) -> NormalizeResult:
    """Chuyển một phần tử results của /api/orders sang bản ghi nội bộ, hoặc báo lý do bỏ.
    A3: bổ sung table_name từ Pos/RoomId và guests từ NumberOfGuests.
    """
    code = raw.get("Code")
    if raw.get("Id") == TOTAL_ROW_ID or (isinstance(code, str) and code.strip() == TOTAL_ROW_CODE):
        return NormalizeResult(None, "total")
    if not code or not str(code).strip():
        return NormalizeResult(None, "invalid")
    status = raw.get("Status")
    if status is not None and status != VALID_STATUS:
        return NormalizeResult(None, "void")
    try:
        created = parse_iso_utc(raw[ORDER_FIELD_MAP["created_at"]])
    except (KeyError, ValueError):
        return NormalizeResult(None, "invalid")

    # A3: bàn từ trường Pos (tên) hoặc RoomId (mã phòng/bàn)
    table_name = None
    pos_val = raw.get("Pos")
    if pos_val and str(pos_val).strip():
        table_name = str(pos_val).strip()
    elif raw.get("RoomId") is not None:
        table_name = f"Bàn {raw['RoomId']}"

    guests = None
    ng = raw.get("NumberOfGuests")
    if ng is not None:
        try:
            guests = int(ng)
        except (ValueError, TypeError):
            guests = None

    return NormalizeResult({
        "doc_code": str(code).strip(),
        "created_at": created,
        "business_date": business_date(created),
        "paid": to_vnd(raw.get(ORDER_FIELD_MAP["paid"])),
        "total": to_vnd(raw.get(ORDER_FIELD_MAP["total"])),
        "discount": to_vnd(raw.get(ORDER_FIELD_MAP["discount"])),
        "pos_id": raw.get("Id"),
        "source": "api",
        "table_name": table_name,
        "guests": guests,
    })


@dataclass
class FetchResult:
    raw_rows: list
    count_reported: int | None
    pages: int
    stopped_early: bool = False   # B2: dừng vì đạt giới hạn trang
    cutoff_hit: bool = False      # B1: dừng vì gặp đơn cũ hơn mốc


def _order_created_date(raw: dict) -> date | None:
    """Lấy ngày tạo đơn từ raw để kiểm tra mốc B1."""
    try:
        created = parse_iso_utc(raw.get("PurchaseDate", ""))
        return business_date(created)
    except Exception:
        return None


def fetch_orders_since(fetch_page: Callable[[int, int], dict], page_size: int = 20,
                       max_pages: int = 500, since: date | None = None) -> FetchResult:
    """Lấy đơn từ API POS365, dừng sớm theo B1 và B2.

    B1: API trả MỚI -> CŨ, dừng ngay khi gặp đơn có business_date < since.
    B2: dừng êm khi đã đọc max_pages trang, ghi nhận stopped_early=True.
    """
    rows: list = []
    count_reported: int | None = None
    pages = 0
    skip = 0
    stopped_early = False
    cutoff_hit = False

    while pages < max_pages:
        payload = fetch_page(page_size, skip)
        pages += 1
        if count_reported is None and payload.get("__count") is not None:
            count_reported = int(payload["__count"])
        results = payload.get("results") or []
        if not results:
            break

        # B1: kiểm tra mốc ngày
        if since is not None:
            page_rows = []
            for raw in results:
                d = _order_created_date(raw)
                if d is not None and d < since:
                    cutoff_hit = True
                    break
                page_rows.append(raw)
            rows.extend(page_rows)
            if cutoff_hit:
                break
        else:
            rows.extend(results)

        skip += page_size
        if count_reported is not None and skip >= count_reported:
            break
    else:
        # B2: chạm giới hạn trang
        stopped_early = True

    return FetchResult(rows, count_reported, pages, stopped_early, cutoff_hit)


def fetch_all_orders(fetch_page: Callable[[int, int], dict], page_size: int = 20,
                     max_pages: int = 5000) -> FetchResult:
    """Tương thích ngược: gọi fetch_orders_since không có mốc."""
    return fetch_orders_since(fetch_page, page_size, max_pages, since=None)


@dataclass
class Pos365Client:
    base_url: str
    username: str = ""
    password: str = ""
    auth_mode: str = "credentials"
    extra_headers: dict = field(default_factory=dict)
    top_param: str = "$top"
    skip_param: str = "$skip"
    timeout: float = 30.0  # B3: cấu hình được
    retries: int = 3
    retry_sleep: float = 0.5
    session_id: str | None = None

    # ---- HTTP thấp ----
    def _open(self, url: str, headers: dict) -> tuple[int, bytes]:
        req = urllib.request.Request(url, headers=headers, method="GET")
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read()
            except (http.client.IncompleteRead, http.client.RemoteDisconnected,
                    ConnectionResetError, TimeoutError, urllib.error.URLError) as exc:
                last = exc  # IncompleteRead: lý do dùng trang nhỏ (PAGE_SIZE=20)
                time.sleep(self.retry_sleep)
        raise Pos365Error(f"lỗi kết nối sau {self.retries} lần thử: {last}")

    @staticmethod
    def _json(status: int, body: bytes, where: str) -> dict:
        if status == 401:
            raise Pos365AuthError(f"401 Unauthorized tại {where}")
        if status == 403:
            raise Pos365AuthError(f"403 Forbidden tại {where} – kiểm tra quyền tài khoản")
        if status >= 500:
            raise Pos365Error(f"Máy chủ POS365 lỗi {status} tại {where}")
        text = body.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            # SPA trả HTML (vd trang đăng nhập) thay cho JSON -> thường do thiếu/sai Cookie
            head = text.strip()[:60].replace("\n", " ")
            raise Pos365Error(f"phản hồi không phải JSON tại {where} (HTTP {status}): {head!r}") from exc

    # ---- API ----
    def login(self) -> str:
        if self.auth_mode == "none":
            return ""
        q = urllib.parse.urlencode({"Username": self.username, "Password": self.password, "format": "json"})
        status, body = self._open(f"{self.base_url}/api/auth/credentials?{q}", {"Accept": "application/json"})
        data = self._json(status, body, "/api/auth/credentials")
        sid = data.get("SessionId")
        if not sid:
            raise Pos365AuthError("đăng nhập không trả SessionId")
        self.session_id = sid
        return sid

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        h.update(self.extra_headers)
        if self.auth_mode != "none" and self.session_id:
            h["Cookie"] = f"ss-id={self.session_id}"
        return h

    def get_orders_page(self, top: int, skip: int) -> dict:
        url = (f"{self.base_url}/api/orders?format=json"
               f"&{self.top_param}={top}&{self.skip_param}={skip}")
        if self.auth_mode != "none" and not self.session_id:
            self.login()
        status, body = self._open(url, self._headers())
        if status == 401 and self.auth_mode != "none":
            self.login()  # API §1: gặp 401 phải đăng nhập lại
            status, body = self._open(url, self._headers())
        return self._json(status, body, "/api/orders")
