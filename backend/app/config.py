"""Cấu hình đọc từ biến môi trường (không phụ thuộc thư viện ngoài)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

ALWAYS_ON_IN_LIVE = ("E01_ROLES", "E02_AUTH")
OPTIONAL_FLAGS = ("E03_AUDIT", "E04_SHIFT_TAG", "E05_EXPORT", "E09_QR_ATTENDANCE", "E13_AUTO_DRAFT")


def unescape_dollars(value: str) -> str:
    """Trong .env, Docker Compose cần '$$top'; chạy ngoài Docker thì còn nguyên '$$'."""
    return value.replace("$$", "$")


def _truthy(v: str | None, default: bool) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class AppConfig:
    app_mode: str = "demo"
    session_hours: int = 12
    owner_username: str = ""
    pos365_base_url: str = ""
    pos365_auth_mode: str = "credentials"  # 'credentials' | 'none'
    pos365_extra_headers: dict = field(default_factory=dict)
    pos365_page_size: int = 20
    pos365_top_param: str = "$top"
    pos365_skip_param: str = "$skip"
    pos365_sync_from_date: str = ""       # B1: mốc ngày đồng bộ (YYYY-MM-DD), mặc định = đầu tháng trước
    pos365_sync_max_pages: int = 500      # B2: giới hạn số trang mỗi lần đồng bộ
    pos365_request_timeout: float = 30.0  # B3: timeout mỗi request tới POS365 (giây)
    qr_base_url: str = ""                 # C6: địa chỉ gốc QR chấm công
    flags: dict = field(default_factory=dict)

    @property
    def is_live(self) -> bool:
        return self.app_mode == "live"

    @classmethod
    def from_env(cls, env: dict | None = None) -> "AppConfig":
        e = os.environ if env is None else env
        mode = (e.get("APP_MODE") or "demo").strip().lower()
        if mode not in ("demo", "live"):
            raise ValueError(f"APP_MODE không hợp lệ: {mode!r} (chỉ 'demo' hoặc 'live')")
        auth_mode = (e.get("POS365_AUTH_MODE") or "credentials").strip().lower()
        if auth_mode not in ("credentials", "none"):
            raise ValueError("POS365_AUTH_MODE chỉ nhận 'credentials' hoặc 'none'")
        raw_headers = e.get("POS365_EXTRA_HEADERS") or ""
        headers = json.loads(raw_headers) if raw_headers.strip() else {}
        if not isinstance(headers, dict):
            raise ValueError("POS365_EXTRA_HEADERS phải là JSON object")
        page = int(e.get("POS365_PAGE_SIZE") or 20)
        if page < 1:
            raise ValueError("POS365_PAGE_SIZE phải >= 1")
        flags = {}
        for name in ALWAYS_ON_IN_LIVE:
            flags[name] = _truthy(e.get(name), True)
            if mode == "live":
                flags[name] = True  # D17: bắt buộc, không tắt được ở Live
        for name in OPTIONAL_FLAGS:
            flags[name] = _truthy(e.get(name), name != "E09_QR_ATTENDANCE" and name != "E13_AUTO_DRAFT")
        return cls(
            app_mode=mode,
            session_hours=int(e.get("SESSION_HOURS") or 12),
            owner_username=(e.get("OWNER_USERNAME") or "").strip(),
            pos365_base_url=(e.get("POS365_BASE_URL") or "").rstrip("/"),
            pos365_auth_mode=auth_mode,
            pos365_extra_headers=headers,
            pos365_page_size=page,
            pos365_top_param=unescape_dollars(e.get("POS365_TOP_PARAM") or "$top"),
            pos365_skip_param=unescape_dollars(e.get("POS365_SKIP_PARAM") or "$skip"),
            pos365_sync_from_date=(e.get("POS365_SYNC_FROM_DATE") or "").strip(),
            pos365_sync_max_pages=max(1, int(e.get("POS365_SYNC_MAX_PAGES") or 500)),
            pos365_request_timeout=max(5.0, float(e.get("POS365_REQUEST_TIMEOUT") or 30.0)),
            qr_base_url=(e.get("QR_BASE_URL") or "").rstrip("/"),
            flags=flags,
        )
