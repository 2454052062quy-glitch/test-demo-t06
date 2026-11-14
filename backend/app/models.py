"""Mô hình dữ liệu (xem docs/data-schema.md). Cột người dùng (created_by...) là số nguyên, không có khóa ngoại,
để chế độ tắt đăng nhập ở Demo (E02_AUTH=false) vẫn ghi được."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (JSON, BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------- nền tảng ----------------
class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20), default="staff")  # owner | staff (shift_manager, accountant: để chỗ)
    password_hash: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionToken(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):  # E-03
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(40), default="")
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(40), default="")
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# ---------------- R01 ----------------
class PosSyncLog(Base):
    __tablename__ = "pos_sync_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # api | file
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_name: Mapped[str] = mapped_column(String(200), default="")
    file_sha256: Mapped[str] = mapped_column(String(64), default="")
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_conflict: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped_void: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped_invalid: Mapped[int] = mapped_column(Integer, default=0)
    pos_count_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sum_paid_reported: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reconcile_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="ok")  # ok | error
    error: Mapped[str] = mapped_column(Text, default="")


class PosOrder(Base):
    __tablename__ = "pos_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_code: Mapped[str] = mapped_column(String(60), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    business_date: Mapped[date] = mapped_column(Date, index=True)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    paid: Mapped[int] = mapped_column(BigInteger, default=0)
    discount: Mapped[int] = mapped_column(BigInteger, default=0)
    pos_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="api")
    table_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    guests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ---------------- R03 ----------------
class HandoverRow(Base):
    __tablename__ = "shift_handovers"
    __table_args__ = (UniqueConstraint("business_date", "shift_code", name="uq_handover_day_shift"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, index=True)
    shift_code: Mapped[str] = mapped_column(String(8))
    pos_revenue_entered: Mapped[int] = mapped_column(BigInteger, default=0)
    pos_revenue_ref: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    transfer_total: Mapped[int] = mapped_column(BigInteger, default=0)
    shortage_refund: Mapped[int] = mapped_column(BigInteger, default=0)
    extra: Mapped[int] = mapped_column(BigInteger, default=0)
    cash_handed: Mapped[int] = mapped_column(BigInteger, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="draft")
    giver_id: Mapped[int] = mapped_column(Integer)
    giver_name: Mapped[str] = mapped_column(String(80), default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receiver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receiver_name: Mapped[str] = mapped_column(String(80), default="")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unlocked_by_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    out_of_schedule: Mapped[bool] = mapped_column(Boolean, default=False)  # E-04: "Ngoài lịch phân công"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------- R04, R09 ----------------
class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class Ingredient(Base):
    __tablename__ = "ingredients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    unit: Mapped[str] = mapped_column(String(30), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_date: Mapped[date] = mapped_column(Date, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(20), default="hoa_don")  # hoa_don | bien_lai_viet_tay | khong_chung_tu
    discount: Mapped[int] = mapped_column(BigInteger, default=0)
    total_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_name: Mapped[str] = mapped_column(String(80), default="")
    shift_code: Mapped[str | None] = mapped_column(String(8), nullable=True)  # E-04
    out_of_schedule: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(30), default="")
    unit_price: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total: Mapped[int] = mapped_column(BigInteger, default=0)


class PurchaseAttachment(Base):
    __tablename__ = "purchase_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(80))
    mime: Mapped[str] = mapped_column(String(40))
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class IngredientStatusRow(Base):
    __tablename__ = "ingredient_status_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    status: Mapped[str] = mapped_column(String(10))  # sap_het | het
    note: Mapped[str] = mapped_column(Text, default="")
    reported_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reported_by_name: Mapped[str] = mapped_column(String(80), default="")
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shift_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    out_of_schedule: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------- R06 ----------------
class ShiftType(Base):
    __tablename__ = "shift_types"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    hours: Mapped[float] = mapped_column(Numeric(4, 2))
    start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=1)


class PayRate(Base):
    __tablename__ = "pay_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    effective_from: Mapped[date] = mapped_column(Date)
    rate_a: Mapped[float] = mapped_column(Numeric(12, 2))
    rate_b: Mapped[float] = mapped_column(Numeric(12, 2))


class ScheduleMonth(Base):
    __tablename__ = "schedule_months"
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | published
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Assignment(Base):
    __tablename__ = "schedule_assignments"
    __table_args__ = (Index("ix_assign_month", "month"), Index("ix_assign_day", "work_date"))
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7))
    work_date: Mapped[date] = mapped_column(Date)
    shift_code: Mapped[str] = mapped_column(String(8))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    source: Mapped[str] = mapped_column(String(12), default="owner")  # import | owner | swap | auto_draft


class ImportBatch(Base):
    __tablename__ = "schedule_import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7))
    file_name: Mapped[str] = mapped_column(String(200))
    file_sha256: Mapped[str] = mapped_column(String(64))
    rows: Mapped[int] = mapped_column(Integer, default=0)
    layout: Mapped[str] = mapped_column(String(8), default="")
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Availability(Base):
    __tablename__ = "availability_declarations"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", "shift_code", name="uq_avail"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    work_date: Mapped[date] = mapped_column(Date)
    shift_code: Mapped[str] = mapped_column(String(8))
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SwapRow(Base):
    __tablename__ = "swap_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(14))  # full_swap | partial_cover
    work_date: Mapped[date] = mapped_column(Date)
    shift_code: Mapped[str] = mapped_column(String(8))
    from_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    to_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    counter_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    counter_shift: Mapped[str | None] = mapped_column(String(8), nullable=True)
    from_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    to_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")


class PayrollMonth(Base):
    __tablename__ = "payroll_months"
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    n_sang: Mapped[int] = mapped_column(Integer, default=0)
    n_trua: Mapped[int] = mapped_column(Integer, default=0)
    n_toi: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    locked_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # E1: lưu hai đơn giá tại thời điểm chốt lương để không bị ảnh hưởng khi đổi đơn giá sau
    rate_a_at_lock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_b_at_lock: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AttendanceLog(Base):  # E-09: chỉ đối chiếu, không tính lương
    __tablename__ = "attendance_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(3))  # in | out
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    out_of_schedule: Mapped[bool] = mapped_column(Boolean, default=False)
    method: Mapped[str] = mapped_column(String(20), default="qr")  # qr | pin | auto_close
    auto_closed: Mapped[bool] = mapped_column(Boolean, default=False)  # True khi hệ thống tự đóng ca
    note: Mapped[str] = mapped_column(Text, default="")


class KioskQrToken(Base):  # E-09: QR one-time token (máy quầy tạo, điện thoại quét)
    __tablename__ = "kiosk_qr_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kiosk_id: Mapped[str] = mapped_column(String(80), index=True)  # browser fingerprint của máy quầy
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # user_id sau khi điện thoại xác nhận
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_kind: Mapped[str | None] = mapped_column(String(3), nullable=True)  # in | out


class PosKioskSession(Base):  # E-09: phiên đăng nhập máy quầy
    __tablename__ = "pos_kiosk_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    kiosk_id: Mapped[str] = mapped_column(String(80), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str] = mapped_column(String(20), default="")  # manual | auto_timeout | next_shift
    attendance_in_id: Mapped[int | None] = mapped_column(ForeignKey("attendance_logs.id"), nullable=True)
    attendance_out_id: Mapped[int | None] = mapped_column(ForeignKey("attendance_logs.id"), nullable=True)


# ---------------- R07 ----------------
class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(12))  # co_dinh | phat_sinh
    item: Mapped[str] = mapped_column(String(160))
    amount: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PnlManualRef(Base):
    __tablename__ = "pnl_manual_reference"
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    revenue: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ingredients: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payroll: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fixed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    other: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    entered_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
