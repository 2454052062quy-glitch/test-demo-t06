"""Phân quyền theo vai trò và trạng thái đứng ca (E-01, D02, D23).

Vai trò đang hoạt động: owner, staff. 'shift_manager' và 'accountant' chỉ giữ chỗ (chưa xây): không có quyền nào.

Quyết định 12/11/2026 (D23): `duty_require_schedule` MẶC ĐỊNH TẮT (False) ở cả Demo và Live.
- Tắt: nhân viên thao tác giao ca / nhập hàng / báo nguyên liệu vào ngày KHÔNG có trong lịch phân công vẫn
  được lưu, bản ghi gắn cờ `out_of_schedule` ("Ngoài lịch phân công", phục vụ E-04). Không trả 403.
- Bật (chủ quán tự bật trên màn hình Cấu hình): chặn 403 như chế độ nghiêm ngặt.
Dùng `evaluate_access` ở tầng API; `can` giữ nguyên nghĩa chế độ nghiêm ngặt.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

OWNER_ONLY = {
    "pos.sync", "pos.import", "revenue.view", "schedule.edit", "schedule.publish", "swaps.decide",
    "pnl.view", "expenses.write", "payroll.view_all", "payroll.lock", "users.manage",
    "settings.edit", "audit.view", "handover.unlock", "attendance.qr_display", "schedule.autodraft",
}
STAFF_ALWAYS = {"schedule.view", "availability.write", "swaps.request", "payroll.view_own", "attendance.scan"}
STAFF_ON_DUTY = {"handover.write", "purchase.write", "ingredient.report"}
READ_FOR_ALL_ACTIVE = {"ingredient.view", "purchase.view", "handover.view"}
ACTIVE_ROLES = {"owner", "staff"}


def is_on_duty(employee_id: int | None, work_date: date, assignments, duty_require_schedule: bool = True) -> bool:
    """assignments: iterable (work_date, shift_code, employee_id). Đứng ca = có ít nhất 1 phân công trong ngày."""
    if employee_id is not None and any(d == work_date and e == employee_id for d, _s, e in assignments):
        return True
    return not duty_require_schedule  # D23: chủ quán tắt yêu cầu này khi chưa có lịch


def can(role: str, permission: str, on_duty: bool = False) -> bool:
    if role not in ACTIVE_ROLES:
        return False
    if role == "owner":
        return True
    if permission in OWNER_ONLY:
        return False
    if permission in STAFF_ALWAYS or permission in READ_FOR_ALL_ACTIVE:
        return True
    if permission in STAFF_ON_DUTY:
        return on_duty
    return False  # quyền lạ: từ chối mặc định


DEFAULT_DUTY_STRICT = False  # duty_require_schedule


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    out_of_schedule: bool = False


def evaluate_access(role: str, permission: str, assigned_today: bool, strict: bool = DEFAULT_DUTY_STRICT) -> AccessDecision:
    """Quyết định cho một thao tác. assigned_today: nhân viên có phân công trong ngày của bản ghi."""
    if role not in ACTIVE_ROLES:
        return AccessDecision(False)
    if role == "owner":
        return AccessDecision(True)
    if permission in OWNER_ONLY:
        return AccessDecision(False)
    if permission in STAFF_ALWAYS or permission in READ_FOR_ALL_ACTIVE:
        return AccessDecision(True)
    if permission in STAFF_ON_DUTY:
        if assigned_today:
            return AccessDecision(True)
        return AccessDecision(not strict, out_of_schedule=True)
    return AccessDecision(False)
