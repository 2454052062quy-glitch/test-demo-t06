"""Múi giờ và ngày kinh doanh.

POS365 trả PurchaseDate dạng UTC có hậu tố Z (API Spec §5.1). Quán mở 06:30 (CQ09),
tức 23:30 UTC của ngày hôm trước, nên ngày kinh doanh phải tính theo GMT+7.
Việt Nam không có giờ mùa hè nên dùng offset cố định, không phụ thuộc tzdata.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))

_FRACTION = re.compile(r"(\.\d+)")


def parse_iso_utc(value: str) -> datetime:
    """Parse '2022-05-19T07:04:10.3400000Z' (7 chữ số lẻ giây) thành datetime UTC aware."""
    v = value.strip()
    if not v:
        raise ValueError("chuỗi thời gian rỗng")
    m = _FRACTION.search(v)
    if m:
        frac = m.group(1)[1:7].ljust(6, "0")
        v = v[: m.start()] + "." + frac + v[m.end():]
    if v.endswith("Z") or v.endswith("z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_vn(dt_utc: datetime) -> datetime:
    return dt_utc.astimezone(VN_TZ)


def business_date(dt_utc: datetime) -> date:
    return to_vn(dt_utc).date()


def local_naive_to_utc(naive: datetime) -> datetime:
    """Giờ địa phương (GMT+7) không kèm múi giờ -> UTC. Dùng cho file xuất (D10)."""
    return naive.replace(tzinfo=VN_TZ).astimezone(timezone.utc)
