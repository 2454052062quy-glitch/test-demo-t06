"""Mật khẩu (bcrypt) và phiên đăng nhập (token ngẫu nhiên, chỉ lưu băm SHA-256)."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

MAX_FAILED = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 8


def validate_password_strength(pw: str) -> str | None:
    """Kiểm tra mật khẩu mạnh: >8 ký tự (ít nhất 9 ký tự hoặc >=8 kèm chữ hoa, chữ thường, số, ký tự đặc biệt)."""
    if len(pw) <= MIN_PASSWORD:
        return "Mật khẩu phải có trên 8 ký tự (tối thiểu 9 ký tự)."
    if not re.search(r"[A-Z]", pw):
        return "Mật khẩu phải có ít nhất 1 chữ cái viết hoa (A-Z)."
    if not re.search(r"[a-z]", pw):
        return "Mật khẩu phải có ít nhất 1 chữ cái viết thường (a-z)."
    if not re.search(r"[0-9]", pw):
        return "Mật khẩu phải có ít nhất 1 chữ số (0-9)."
    if not re.search(r"[^A-Za-z0-9]", pw):
        return "Mật khẩu phải có ít nhất 1 ký tự đặc biệt (ví dụ: !@#$%^&*)."
    return None


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode())
    except ValueError:
        return False


def new_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def expiry(hours: int) -> datetime:
    return utcnow() + timedelta(hours=hours)
