"""Biên bản giao ca (R03, F03-A/B). D01: CHỈ lưu số nhân viên nhập + lý do, KHÔNG tự tính tiền két.

Trường theo biên bản giấy (QT1-B1 Bảng H): ngày, doanh thu hệ thống, bill CK, thiếu/trả, phát sinh,
thực tế giao, ký tên. `pos_revenue_ref` chỉ là ảnh chụp tổng doanh thu ngày từ R01 để tham chiếu.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date, datetime

SHIFTS = ("sang", "trua", "toi")
STATUSES = ("draft", "submitted", "confirmed")


class HandoverError(Exception):
    pass


@dataclass
class Handover:
    business_date: date
    shift_code: str
    giver_id: int
    pos_revenue_entered: int = 0
    transfer_total: int = 0
    shortage_refund: int = 0
    extra: int = 0
    cash_handed: int = 0
    note: str = ""
    pos_revenue_ref: int | None = None
    status: str = "draft"
    submitted_at: datetime | None = None
    receiver_id: int | None = None
    confirmed_at: datetime | None = None
    unlocked_by_owner: bool = False


INPUT_FIELDS = ("pos_revenue_entered", "transfer_total", "shortage_refund", "extra", "cash_handed", "note")


def validate(h: Handover) -> list[str]:
    errs = []
    if h.shift_code not in SHIFTS:
        errs.append("ca không hợp lệ")
    for name in ("pos_revenue_entered", "transfer_total", "cash_handed"):
        if getattr(h, name) < 0:
            errs.append(f"{name} không được âm")
    if h.pos_revenue_entered <= 0 and h.transfer_total <= 0 and h.cash_handed <= 0 and not h.note.strip():
        errs.append("Vui lòng nhập số liệu doanh thu hoặc tiền mặt bàn giao (nếu ca 0 đồng phải ghi rõ lý do)")
    if (h.shortage_refund != 0 or h.extra != 0) and not h.note.strip():
        errs.append("có khoản thiếu/trả hoặc phát sinh thì phải ghi lý do")
    # D3: Lệch quá 10% so với POS tham chiếu thì bắt buộc ghi chú lý do
    if h.pos_revenue_ref is not None:
        if h.pos_revenue_ref > 0:
            diff = abs(h.pos_revenue_entered - h.pos_revenue_ref)
            if diff > 0.10 * h.pos_revenue_ref and not h.note.strip():
                errs.append("Doanh thu nhập vào lệch quá 10% so với POS tham chiếu, bắt buộc ghi chú lý do")
        elif h.pos_revenue_entered > 0 and not h.note.strip():
            errs.append("Doanh thu nhập vào lệch quá 10% so với POS tham chiếu, bắt buộc ghi chú lý do")
    return errs


def edit(h: Handover, **changes) -> None:
    if h.status != "draft" and not h.unlocked_by_owner:
        raise HandoverError("biên bản đã gửi/xác nhận, chỉ chủ quán mở khóa mới sửa được")
    for k, v in changes.items():
        if k not in INPUT_FIELDS:
            raise HandoverError(f"không được sửa trường {k!r}")
        setattr(h, k, v)


def submit(h: Handover, now: datetime) -> None:
    if h.status != "draft":
        raise HandoverError("chỉ gửi được biên bản nháp")
    errs = validate(h)
    if errs:
        raise HandoverError("; ".join(errs))
    h.status, h.submitted_at, h.unlocked_by_owner = "submitted", now, False


def confirm(h: Handover, receiver_id: int, now: datetime) -> None:
    if h.status != "submitted":
        raise HandoverError("chỉ xác nhận được biên bản đã gửi")
    if receiver_id == h.giver_id:
        raise HandoverError("người giao không được tự xác nhận")
    h.status, h.receiver_id, h.confirmed_at = "confirmed", receiver_id, now


def field_names() -> set[str]:
    return {f.name for f in fields(Handover)}
