"""Chấm công QR máy quầy (E-09): QR one-time + PIN dự phòng + phiên máy quầy.

Logic:
- make_qr_token / verify_qr_token: tạo / kiểm tra token 1 lần, hết hạn sau QR_TTL_SECONDS
- hash_pin / verify_pin: bcrypt nhẹ cho mã PIN 4-6 số
- auto_close_shift: tự đóng phiên nếu > 8 tiếng hoặc người khác vào ca
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

# -- Tương thích bcrypt --
try:
    import bcrypt as _bcrypt

    def hash_pin(pin: str) -> str:
        return _bcrypt.hashpw(pin.encode(), _bcrypt.gensalt(rounds=6)).decode()

    def verify_pin(pin: str, hashed: str) -> bool:
        try:
            return _bcrypt.checkpw(pin.encode(), hashed.encode())
        except Exception:
            return False

except ImportError:
    # Dự phòng: sha256 + salt (kém an toàn hơn, nhưng không crash)
    def hash_pin(pin: str) -> str:  # type: ignore[misc]
        salt = secrets.token_hex(8)
        h = hashlib.sha256((salt + pin).encode()).hexdigest()
        return f"sha256:{salt}:{h}"

    def verify_pin(pin: str, hashed: str) -> bool:  # type: ignore[misc]
        try:
            if hashed.startswith("sha256:"):
                _, salt, h = hashed.split(":", 2)
                return hmac.compare_digest(h, hashlib.sha256((salt + pin).encode()).hexdigest())
        except Exception:
            pass
        return False


# ---------- QR one-time token ----------
QR_TTL_SECONDS = 120  # 2 phút


def make_qr_token() -> str:
    """Sinh token ngẫu nhiên 32 byte (hex 64 ký tự). Lưu vào DB với expires_at."""
    return secrets.token_hex(32)


def qr_expires_at(now: datetime | None = None) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)
    return now + timedelta(seconds=QR_TTL_SECONDS)


def next_kind(last_kind: str | None) -> str:
    return "out" if last_kind == "in" else "in"


def is_token_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None and now.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    elif expires_at.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return expires_at < now


# ---------- Auto-close: 8 tiếng hoặc ca mới ----------
_AUTO_CLOSE_HOURS = 8


def auto_close_hours() -> int:
    return _AUTO_CLOSE_HOURS


def should_auto_close(opened_at: datetime, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    if opened_at.tzinfo is None and now.tzinfo is not None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    elif opened_at.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now - opened_at).total_seconds() > _AUTO_CLOSE_HOURS * 3600


# ---------- PIN validation ----------
def valid_pin(pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 6


# ---------- Legacy HMAC token (giữ lại để không break tests cũ) ----------
WINDOW_SECONDS = 60


def _window(now: datetime, window: int) -> int:
    return int(now.timestamp()) // window


def make_token(secret: str, now: datetime, window: int = WINDOW_SECONDS) -> str:
    w = _window(now, window)
    mac = hmac.new(secret.encode(), str(w).encode(), hashlib.sha256).hexdigest()[:24]
    return f"{w}.{mac}"


def verify_token(secret: str, token: str, now: datetime, window: int = WINDOW_SECONDS, tolerance: int = 1) -> bool:
    try:
        w_str, mac = token.split(".", 1)
        w = int(w_str)
    except (ValueError, AttributeError):
        return False
    if abs(_window(now, window) - w) > tolerance:
        return False
    expected = hmac.new(secret.encode(), str(w).encode(), hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(mac, expected)


def can_scan(assigned_today: bool) -> bool:
    return assigned_today
