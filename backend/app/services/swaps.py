"""Yêu cầu đổi ca (R06 Đường 2, F06-F; căn cứ: CĐ-GV, NC-01 C2, CQ05).

Hai loại (D15, chốt 11/11):
- full_swap: đổi/nhường nguyên ca. Khi duyệt, đổi người trong lịch NGAY (một thao tác nguyên tử).
- partial_cover: nhờ làm phụ giữa ca / vắng nửa ca. Khi duyệt KHÔNG đổi lịch, KHÔNG đổi lương,
  chỉ tạo cờ cảnh báo cho màn hình lương (F06-G); chủ quán tự cộng/trừ tay (D25).

Schedule: dict {(work_date, shift_code): [employee_id, ...]}. Bản DB dùng cùng quy tắc trong một
giao dịch, khóa dòng yêu cầu (SELECT ... FOR UPDATE) để hai lần duyệt đồng thời chỉ một lần có hiệu lực.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

KINDS = ("full_swap", "partial_cover")
SHIFTS = ("sang", "trua", "toi")


class SwapError(Exception):
    pass


@dataclass
class SwapRequest:
    id: int
    kind: str
    work_date: date
    shift_code: str
    from_employee_id: int
    to_employee_id: int
    reason: str = ""
    # chỉ full_swap: nếu có, người nhận đồng thời nhường lại ca này cho người gửi (đổi hai chiều)
    counter_date: date | None = None
    counter_shift: str | None = None
    # chỉ partial_cover (tùy chọn)
    from_time: time | None = None
    to_time: time | None = None
    status: str = "pending"
    decided_by: int | None = None
    decided_at: datetime | None = None
    decision_note: str = ""


def create_request(req_id: int, schedule: dict, requester_id: int, kind: str, work_date: date,
                   shift_code: str, to_employee_id: int, reason: str = "", **extra) -> SwapRequest:
    if kind not in KINDS:
        raise SwapError(f"loại yêu cầu không hợp lệ: {kind!r}")
    if shift_code not in SHIFTS:
        raise SwapError("ca không hợp lệ")
    if to_employee_id == requester_id:
        raise SwapError("không thể gửi cho chính mình")
    if requester_id not in schedule.get((work_date, shift_code), []):
        raise SwapError("chỉ yêu cầu được ca của chính mình")
    req = SwapRequest(req_id, kind, work_date, shift_code, requester_id, to_employee_id, reason, **extra)
    if kind == "full_swap" and req.counter_date is not None:
        if to_employee_id not in schedule.get((req.counter_date, req.counter_shift), []):
            raise SwapError("người nhận không có ca đối ứng đã nêu")
    if kind == "partial_cover" and (req.counter_date or req.counter_shift):
        raise SwapError("phụ giữa ca không có ca đối ứng")
    return req


def _replace(schedule: dict, key: tuple, old: int, new: int) -> None:
    people = schedule.get(key, [])
    if old not in people:
        raise SwapError("lịch đã thay đổi, người gửi không còn trong ca này")
    people[people.index(old)] = new


def approve(req: SwapRequest, schedule: dict, decided_by: int, now: datetime, note: str = "") -> None:
    """Duyệt. Chỉ chủ quán gọi (kiểm quyền ở tầng API). Nguyên tử: lỗi thì không đổi gì."""
    if req.status != "pending":
        raise SwapError(f"yêu cầu đã ở trạng thái {req.status}")
    if req.kind == "full_swap":
        snapshot = {k: list(v) for k, v in schedule.items()}
        try:
            _replace(schedule, (req.work_date, req.shift_code), req.from_employee_id, req.to_employee_id)
            if req.counter_date is not None:
                _replace(schedule, (req.counter_date, req.counter_shift), req.to_employee_id, req.from_employee_id)
        except SwapError:
            schedule.clear()
            schedule.update(snapshot)
            raise
    # partial_cover: không đụng lịch
    req.status, req.decided_by, req.decided_at, req.decision_note = "approved", decided_by, now, note


def reject(req: SwapRequest, decided_by: int, now: datetime, note: str = "") -> None:
    if req.status != "pending":
        raise SwapError(f"yêu cầu đã ở trạng thái {req.status}")
    req.status, req.decided_by, req.decided_at, req.decision_note = "rejected", decided_by, now, note


def cancel(req: SwapRequest, by_employee_id: int) -> None:
    if req.status != "pending":
        raise SwapError(f"yêu cầu đã ở trạng thái {req.status}")
    if by_employee_id != req.from_employee_id:
        raise SwapError("chỉ người gửi mới hủy được")
    req.status = "cancelled"


def payroll_flags(requests, month: str) -> list[dict]:
    """Cờ cho F06-G: các yêu cầu phụ giữa ca/vắng nửa ca đã duyệt trong tháng. Không có trường tiền (D25)."""
    flags = []
    for r in requests:
        if r.kind == "partial_cover" and r.status == "approved" and r.work_date.strftime("%Y-%m") == month:
            flags.append({"work_date": r.work_date, "shift_code": r.shift_code,
                          "from_employee_id": r.from_employee_id, "cover_employee_id": r.to_employee_id,
                          "from_time": r.from_time, "to_time": r.to_time, "reason": r.reason})
    return sorted(flags, key=lambda f: (f["work_date"], f["shift_code"]))
