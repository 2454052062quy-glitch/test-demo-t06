"""Gợi ý xếp lịch nháp (E-13, MỞ RỘNG; D24). Chủ quán xem nháp, chỉnh ô trống, rồi Công bố.

Quy tắc (đề xuất của nhóm 11/11):
  1. Chỉ xếp người có available = True tại (ngày, ca). Không khai báo = không rảnh.
  2. Công bằng: ưu tiên người có ít ca nhất trong tháng (tính đến thời điểm xử lý ô này).
  3. Cụm ca liền kề: nếu người đó vừa làm ca liền trước trong cùng ngày và vẫn rảnh ca này,
     tăng ưu tiên, nhưng chỉ khi số ca của họ <= mức thấp nhất + cluster_fairness_slack.
Tham số tự đặt (cần xác nhận): cluster_fairness_slack=1, max_shifts_per_day=2. Hòa: chọn mã nhỏ hơn.
Quy tắc 3 chưa có căn cứ trong tài liệu.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SHIFT_ORDER = ("sang", "trua", "toi")


@dataclass
class DraftResult:
    assignments: list = field(default_factory=list)   # [(date, shift, employee_id)] mới thêm
    unassigned: list = field(default_factory=list)    # [(date, shift)] còn thiếu người
    counts: dict = field(default_factory=dict)        # employee_id -> tổng ca trong tháng sau khi xếp


def auto_draft(dates: list[date], availability: dict, existing: dict | None = None,
               capacity: dict | None = None, employees: list[int] | None = None,
               cluster_fairness_slack: int = 1, max_shifts_per_day: int = 2) -> DraftResult:
    """availability: {(employee_id, date, shift): bool}. existing: {(date, shift): [employee_id]} giữ nguyên."""
    existing = {k: list(v) for k, v in (existing or {}).items()}
    capacity = capacity or {s: 1 for s in SHIFT_ORDER}
    emps = sorted(employees if employees is not None else {e for (e, _d, _s) in availability})
    counts = {e: 0 for e in emps}
    day_counts: dict = {}
    for (d, _s), people in existing.items():
        for e in people:
            counts[e] = counts.get(e, 0) + 1
            day_counts[(e, d)] = day_counts.get((e, d), 0) + 1

    result = DraftResult()
    for d in sorted(dates):
        for idx, shift in enumerate(SHIFT_ORDER):
            assigned = existing.setdefault((d, shift), [])
            while len(assigned) < capacity.get(shift, 1):
                cands = [e for e in emps
                         if availability.get((e, d, shift), False) is True          # quy tắc 1
                         and e not in assigned
                         and day_counts.get((e, d), 0) < max_shifts_per_day]
                if not cands:
                    break
                low = min(counts[e] for e in cands)                                 # quy tắc 2
                pick = min(cands, key=lambda e: (counts[e], e))
                if idx > 0:                                                         # quy tắc 3
                    prev = existing.get((d, SHIFT_ORDER[idx - 1]), [])
                    cluster = [e for e in cands if e in prev and counts[e] <= low + cluster_fairness_slack]
                    if cluster:
                        pick = min(cluster, key=lambda e: (counts[e], e))
                assigned.append(pick)
                counts[pick] += 1
                day_counts[(pick, d)] = day_counts.get((pick, d), 0) + 1
                result.assignments.append((d, shift, pick))
            if len(assigned) < capacity.get(shift, 1):
                result.unassigned.append((d, shift))
    result.counts = counts
    return result
