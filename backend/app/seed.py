"""Khởi tạo mặc định (cả Demo và Live) và dữ liệu GIẢ LẬP HỢP NHẤT (chỉ Demo, DEMO_SEED=true).

Phần II: Dữ liệu mẫu sống động, liên kết chặt chẽ giữa mọi màn hình.
- R01: Doanh thu 2,2–2,8 triệu/ngày (D2), trải đều theo ca (D3: Tối ~40%, Sáng ~30%, Trưa ~30%).
- R03: Biên bản giao ca đủ trạng thái, tham chiếu POS thực tế theo ca (D3), có phiếu lệch >10%.
- R04: Nhập hàng 4-5 phiếu đủ loại chứng từ, tự động đổ vào P&L.
- R06: Lịch ca tháng 10 & 11 không ai quá 2 ca/ngày (D5), ca ghép liền kề, lịch rảnh tháng này & sau (D6).
- R09: Nguyên liệu đủ trạng thái Hết, Sắp hết, Đã đặt, Đủ và lịch sử báo gần đây.
- E-09: Log chấm công QR tối thiểu 4 lượt (D7).
- R07: Chi phí cố định & phát sinh, tháng 11 tạm tính theo ngày đã qua (D1), cả 2 tháng đều có lãi nhẹ.
- E1: Chốt lương tháng 10 lưu 2 mức đơn giá rate_a_at_lock & rate_b_at_lock.
"""
from __future__ import annotations

import io
import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import AppConfig
from .deps import get_setting, month_days, set_setting, today_vn
from .models import (Assignment, AttendanceLog, Availability, Employee, Expense, HandoverRow, ImportBatch,
                     Ingredient, IngredientStatusRow, KioskQrToken, PayRate, PayrollMonth, PnlManualRef,
                     PosKioskSession, PosOrder, PosSyncLog, Purchase, PurchaseAttachment, PurchaseItem,
                     ScheduleMonth, SessionToken, Setting, ShiftType, Supplier, SwapRow, User, utcnow)
from .security import hash_password
from .services.timeutil import VN_TZ
from .devtools.mockdata import fake_orders

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo12345")
DEMO_SEED_VERSION = "v3_full_2026"
NAMES = ["Nhân viên A", "Nhân viên B", "Nhân viên C", "Nhân viên D"]

# C5: Giờ ca mặc định chuẩn
SHIFT_DEFAULTS = {
    "sang": ("Sáng", 5.5, "06:30", "12:00"),
    "trua": ("Trưa", 5.5, "12:00", "17:30"),
    "toi": ("Tối", 4.0, "17:30", "21:30"),
}


def ensure_defaults(db: Session, cfg: AppConfig) -> None:
    """Khởi tạo mặc định cần thiết cho cả Demo và Live."""
    for code, (name, hours, start, end) in SHIFT_DEFAULTS.items():
        st = db.get(ShiftType, code)
        if st is None:
            db.add(ShiftType(code=code, name=name, hours=hours, start_time=start, end_time=end, capacity=1))
        else:
            if not st.start_time or not st.end_time:
                st.start_time = start
                st.end_time = end
                st.hours = hours

    owner_exists = db.scalar(select(func.count()).select_from(User).where(User.role == "owner")) > 0
    if cfg.owner_username and os.environ.get("OWNER_PASSWORD") and not owner_exists:
        db.add(User(username=cfg.owner_username, display_name="Chủ quán", role="owner",
                    password_hash=hash_password(os.environ["OWNER_PASSWORD"])))

    # PIN mẫu cho Demo: Nhân viên A = 1111, Nhân viên B = 2222 (E-09)
    if not cfg.is_live:
        from .services.attendance import hash_pin
        from .deps import get_setting, set_setting
        u_nva = db.scalar(select(User).where(User.username == "nvA"))
        if u_nva and not get_setting(db, f"pin_hash_{u_nva.id}"):
            set_setting(db, f"pin_hash_{u_nva.id}", hash_pin("1111"))
        u_nvb = db.scalar(select(User).where(User.username == "nvB"))
        if u_nvb and not get_setting(db, f"pin_hash_{u_nvb.id}"):
            set_setting(db, f"pin_hash_{u_nvb.id}", hash_pin("2222"))

    db.commit()


def seed_demo(db: Session, cfg: AppConfig) -> bool:
    """Nạp dữ liệu mẫu hợp nhất chỉ cho Demo. Idempotent và tự động nâng cấp dữ liệu mẫu cũ."""
    if cfg.is_live or os.environ.get("DEMO_SEED", "true").lower() not in ("1", "true", "yes"):
        return False
    if db.scalar(select(func.count()).select_from(Employee)) > 0:
        if get_setting(db, "demo_seed_version") == DEMO_SEED_VERSION:
            return False
        is_demo_db = db.scalar(select(func.count()).select_from(User).where(User.username == "chuquan")) > 0
        if not is_demo_db:
            return False
        # Làm mới dữ liệu mẫu cũ (trước bản sửa lỗi đồng bộ lịch ca / giao ca / lương)
        for tbl in (PosKioskSession, KioskQrToken, AttendanceLog, SwapRow, Availability, ImportBatch,
                    Assignment, ScheduleMonth, PayrollMonth, PayRate, PurchaseAttachment, PurchaseItem,
                    Purchase, IngredientStatusRow, Ingredient, Supplier, HandoverRow, PosOrder,
                    PosSyncLog, Expense, PnlManualRef, SessionToken, User, Employee):
            db.execute(delete(tbl))
        db.flush()

    # 1. Nhân viên và Tài khoản (chuquan, nvA, nvB, nvC, nvD)
    emps = [Employee(display_name=n) for n in NAMES]
    db.add_all(emps)
    db.flush()
    emp_map = {e.display_name: e.id for e in emps}

    owner_user = User(username="chuquan", display_name="Chủ quán (demo)", role="owner",
                      password_hash=hash_password(DEMO_PASSWORD))
    db.add(owner_user)
    staff_users = {}
    for e, uname in zip(emps, ["nvA", "nvB", "nvC", "nvD"]):
        u = User(username=uname, display_name=e.display_name, role="staff", employee_id=e.id,
                 password_hash=hash_password(DEMO_PASSWORD))
        db.add(u)
        staff_users[e.display_name] = u
    db.flush()
    user_id_map = {name: u.id for name, u in staff_users.items()}
    user_id_map["Chủ quán (demo)"] = owner_user.id

    # 2. Đơn giá lương mặc định (a = 22k/h, b = 25k/h)
    db.add(PayRate(effective_from=date(2026, 1, 1), rate_a=22000, rate_b=25000))

    # Ngày chốt dữ liệu mẫu: hỗ trợ đầy đủ đến ngày hiện tại trong tháng 11/2026 (tối thiểu 13/11/2026)
    system_today = today_vn()
    demo_ref_date = date(2026, 11, 13)
    if system_today.strftime("%Y-%m") == "2026-11":
        current_cutoff = max(system_today, demo_ref_date)
    else:
        current_cutoff = demo_ref_date

    # 3. Doanh thu POS R01 (Tháng 01/2026 -> Tháng 11/2026 đa dạng theo mùa)
    oct_days = month_days("2026-10")
    nov_all_days = month_days("2026-11")
    nov_active_days = [d for d in nov_all_days if d <= current_cutoff]

    log_sync = PosSyncLog(kind="api", finished_at=utcnow(), rows_read=2400, rows_inserted=2400, status="ok")
    db.add(log_sync)
    db.flush()

    pos_seq = 1
    season_per_day = {1: 6, 2: 6, 3: 5, 4: 5, 5: 6, 6: 7, 7: 7, 8: 5, 9: 5, 10: 8, 11: 8}
    all_months_days: dict[str, list[date]] = {}
    for m_num in range(1, 12):
        m_str = f"2026-{m_num:02d}"
        m_days = month_days(m_str)
        all_months_days[m_str] = m_days
        active_days = nov_active_days if m_num == 11 else m_days
        orders = fake_orders(active_days, per_day=season_per_day[m_num], seed=m_num * 17)
        for idx, o in enumerate(orders):
            db.add(PosOrder(
                doc_code=f"HD-2026{m_num:02d}-{idx+1:05d}",
                created_at=o["local"].astimezone(timezone.utc),
                business_date=o["local"].date(),
                total=o["total"],
                paid=o["paid"],
                discount=o["discount"],
                pos_id=100000 + pos_seq,
                source="api" if (idx + m_num) % 2 == 0 else "file",
                table_name=o["table"],
                guests=o["guests"],
                last_seen_log_id=log_sync.id
            ))
            pos_seq += 1
    db.flush()

    # 4. Lịch ca R06: Tháng 01/2026 -> Tháng 11/2026 (Published)
    # Tuân thủ D5: Ràng buộc không ai quá 2 ca/ngày; có ngày ghép liền kề Sáng + Trưa
    emp_list = [emp_map["Nhân viên A"], emp_map["Nhân viên B"], emp_map["Nhân viên C"], emp_map["Nhân viên D"]]
    for m_num in range(1, 12):
        m = f"2026-{m_num:02d}"
        days = all_months_days[m]
        db.add(ScheduleMonth(month=m, status="published", published_at=utcnow()))
        for day_idx, d in enumerate(days):
            if m == "2026-11":
                # Căn chỉnh lịch ca tháng 11 khớp 100% với Giao ca, Đổi ca và Chấm công QR:
                if d == date(2026, 11, 11):
                    s_emp, tr_emp, t_emp = emp_map["Nhân viên C"], emp_map["Nhân viên D"], emp_map["Nhân viên B"]
                elif d == date(2026, 11, 12):
                    s_emp, tr_emp, t_emp = emp_map["Nhân viên A"], emp_map["Nhân viên A"], emp_map["Nhân viên B"]
                elif d == date(2026, 11, 13):
                    s_emp, tr_emp, t_emp = emp_map["Nhân viên C"], emp_map["Nhân viên A"], emp_map["Nhân viên D"]
                elif d == date(2026, 11, 14):
                    s_emp, tr_emp, t_emp = emp_map["Nhân viên A"], emp_map["Nhân viên B"], emp_map["Nhân viên C"]
                elif d.day % 2 == 0:
                    s_emp, tr_emp, t_emp = emp_list[0], emp_list[0], emp_list[1]
                else:
                    s_emp, tr_emp, t_emp = emp_list[2], emp_list[3], emp_list[3]
                db.add(Assignment(month=m, work_date=d, shift_code="sang", employee_id=s_emp, source="owner"))
                db.add(Assignment(month=m, work_date=d, shift_code="trua", employee_id=tr_emp, source="owner"))
                db.add(Assignment(month=m, work_date=d, shift_code="toi", employee_id=t_emp, source="owner"))
            else:
                if (day_idx + m_num) % 2 == 0:
                    db.add(Assignment(month=m, work_date=d, shift_code="sang", employee_id=emp_list[0], source="owner"))
                    db.add(Assignment(month=m, work_date=d, shift_code="trua", employee_id=emp_list[0], source="owner"))
                    db.add(Assignment(month=m, work_date=d, shift_code="toi", employee_id=emp_list[1], source="owner"))
                else:
                    db.add(Assignment(month=m, work_date=d, shift_code="sang", employee_id=emp_list[2], source="owner"))
                    db.add(Assignment(month=m, work_date=d, shift_code="trua", employee_id=emp_list[3], source="owner"))
                    db.add(Assignment(month=m, work_date=d, shift_code="toi", employee_id=emp_list[3], source="owner"))

    # 5. Khai báo lịch rảnh Availability (D6): Tháng 11/2026 & Tháng 12/2026
    dec_days = month_days("2026-12")
    for m, days in [("2026-11", nov_all_days), ("2026-12", dec_days)]:
        for day_idx, d in enumerate(days):
            for e_idx, e_id in enumerate(emp_list):
                # Khai báo rảnh hợp lý để auto_draft chạy ra > 0 ca
                is_free = (day_idx + e_idx) % 3 != 0
                for s_code in ("sang", "trua", "toi"):
                    db.add(Availability(month=m, employee_id=e_id, work_date=d, shift_code=s_code,
                                        available=is_free, submitted_at=utcnow()))

    # 6. Yêu cầu đổi ca SwapRow
    # Đã duyệt: ngày 12/11 Ca Trưa, NV A (đứng ca Trưa 12/11) nhờ NV B làm phụ (partial_cover) 13:30–15:00 (D4)
    db.add(SwapRow(
        kind="partial_cover", work_date=date(2026, 11, 12), shift_code="trua",
        from_employee_id=emp_map["Nhân viên A"], to_employee_id=emp_map["Nhân viên B"],
        from_time="13:30", to_time="15:00", reason="Đi đón con nửa buổi ca trưa",
        status="approved", decided_at=utcnow(), decision_note="Chủ quán đồng ý"
    ))
    # Chờ duyệt: ngày 14/11 Ca Tối, NV C (đứng ca Tối 14/11) đổi nguyên ca với NV D (full_swap)
    db.add(SwapRow(
        kind="full_swap", work_date=date(2026, 11, 14), shift_code="toi",
        from_employee_id=emp_map["Nhân viên C"], to_employee_id=emp_map["Nhân viên D"],
        reason="Trùng lịch thi học phần cuối tuần", status="pending"
    ))

    # 7. Chấm công QR AttendanceLog (D7) — khớp lịch ca 12/11 và 13/11
    db.add_all([
        AttendanceLog(employee_id=emp_map["Nhân viên A"], work_date=date(2026, 11, 12), kind="in",
                      at=datetime(2026, 11, 12, 6, 25, tzinfo=VN_TZ).astimezone(timezone.utc)),
        AttendanceLog(employee_id=emp_map["Nhân viên A"], work_date=date(2026, 11, 12), kind="out",
                      at=datetime(2026, 11, 12, 17, 32, tzinfo=VN_TZ).astimezone(timezone.utc)),
        AttendanceLog(employee_id=emp_map["Nhân viên B"], work_date=date(2026, 11, 12), kind="in",
                      at=datetime(2026, 11, 12, 17, 28, tzinfo=VN_TZ).astimezone(timezone.utc)),
        AttendanceLog(employee_id=emp_map["Nhân viên B"], work_date=date(2026, 11, 12), kind="out",
                      at=datetime(2026, 11, 12, 21, 35, tzinfo=VN_TZ).astimezone(timezone.utc)),
        AttendanceLog(employee_id=emp_map["Nhân viên C"], work_date=date(2026, 11, 13), kind="in",
                      at=datetime(2026, 11, 13, 6, 28, tzinfo=VN_TZ).astimezone(timezone.utc)),
        AttendanceLog(employee_id=emp_map["Nhân viên C"], work_date=date(2026, 11, 13), kind="out",
                      at=datetime(2026, 11, 13, 12, 5, tzinfo=VN_TZ).astimezone(timezone.utc)),
    ])

    # 8. Giao ca HandoverRow (R03, D3: tính số POS thực tế theo ca)
    def calc_pos(d: date, s_code: str) -> int:
        st = SHIFT_DEFAULTS[s_code]
        sh, sm = map(int, st[2].split(":"))
        eh, em = map(int, st[3].split(":"))
        s_dt = datetime(d.year, d.month, d.day, sh, sm, tzinfo=VN_TZ).astimezone(timezone.utc)
        e_dt = datetime(d.year, d.month, d.day, eh, em, tzinfo=VN_TZ).astimezone(timezone.utc)
        return int(db.scalar(select(func.coalesce(func.sum(PosOrder.paid), 0))
                             .where(PosOrder.business_date == d, PosOrder.created_at >= s_dt, PosOrder.created_at < e_dt)) or 0)

    # Phiếu 1: 11/11 Tối (NV B đứng ca Tối -> Chủ quán nhận) - Confirmed
    pos_11_toi = calc_pos(date(2026, 11, 11), "toi")
    ck_11_toi = int(pos_11_toi * 0.35)
    cash_11_toi = pos_11_toi - ck_11_toi
    db.add(HandoverRow(
        business_date=date(2026, 11, 11), shift_code="toi",
        pos_revenue_entered=pos_11_toi, pos_revenue_ref=pos_11_toi,
        transfer_total=ck_11_toi, shortage_refund=0, extra=0, cash_handed=cash_11_toi,
        status="confirmed", giver_id=user_id_map["Nhân viên B"], giver_name="Nhân viên B",
        receiver_id=user_id_map["Chủ quán (demo)"], receiver_name="Chủ quán (demo)",
        submitted_at=utcnow(), confirmed_at=utcnow()
    ))

    # Phiếu 2: 12/11 Sáng (NV A đứng ca Sáng -> NV B nhận bàn giao khi vào phụ/ca tiếp) - Confirmed
    pos_12_sang = calc_pos(date(2026, 11, 12), "sang")
    ck_12_sang = int(pos_12_sang * 0.4)
    cash_12_sang = pos_12_sang - ck_12_sang
    db.add(HandoverRow(
        business_date=date(2026, 11, 12), shift_code="sang",
        pos_revenue_entered=pos_12_sang, pos_revenue_ref=pos_12_sang,
        transfer_total=ck_12_sang, shortage_refund=0, extra=0, cash_handed=cash_12_sang,
        status="confirmed", giver_id=user_id_map["Nhân viên A"], giver_name="Nhân viên A",
        receiver_id=user_id_map["Nhân viên B"], receiver_name="Nhân viên B",
        submitted_at=utcnow(), confirmed_at=utcnow()
    ))

    # Phiếu 3: 12/11 Tối (NV B đứng ca Tối -> Chủ quán nhận) - Lệch > 10% (đánh dấu cam + có ghi chú bắt buộc theo D3)
    pos_12_toi = calc_pos(date(2026, 11, 12), "toi")
    entered_12_toi = int(pos_12_toi * 1.15)  # lệch +15%
    ck_12_toi = int(entered_12_toi * 0.3)
    cash_12_toi = entered_12_toi - ck_12_toi
    db.add(HandoverRow(
        business_date=date(2026, 11, 12), shift_code="toi",
        pos_revenue_entered=entered_12_toi, pos_revenue_ref=pos_12_toi,
        transfer_total=ck_12_toi, shortage_refund=0, extra=entered_12_toi - pos_12_toi,
        cash_handed=cash_12_toi,
        note="Khách đoàn sinh nhật tip thêm và thanh toán gộp tiền nước mang về bằng tiền mặt",
        status="confirmed", giver_id=user_id_map["Nhân viên B"], giver_name="Nhân viên B",
        receiver_id=user_id_map["Chủ quán (demo)"], receiver_name="Chủ quán (demo)",
        submitted_at=utcnow(), confirmed_at=utcnow()
    ))

    # Phiếu 4: 13/11 Sáng - Submitted (Chờ nhận): NV C đứng ca Sáng 13/11 bàn giao cho NV A (đứng ca Trưa 13/11)
    pos_13_sang = calc_pos(date(2026, 11, 13), "sang")
    ck_13_sang = int(pos_13_sang * 0.35)
    cash_13_sang = pos_13_sang - ck_13_sang
    db.add(HandoverRow(
        business_date=date(2026, 11, 13), shift_code="sang",
        pos_revenue_entered=pos_13_sang, pos_revenue_ref=pos_13_sang,
        transfer_total=ck_13_sang, shortage_refund=0, extra=0, cash_handed=cash_13_sang,
        note="Đã kiểm đếm đủ tiền lẻ đầu ca cho ca trưa",
        status="submitted", giver_id=user_id_map["Nhân viên C"], giver_name="Nhân viên C",
        submitted_at=utcnow()
    ))

    # 9. Nhà cung cấp và Nguyên liệu R04, R09
    suppliers = {
        "vinamilk": Supplier(name="Công ty Sữa Vinamilk"),
        "tracafe": Supplier(name="NCC Cà phê & Trà Bảo Lộc"),
        "taphoa": Supplier(name="Tạp hóa & Bao bì Minh Phát"),
        "chodaumoi": Supplier(name="Mua lẻ Chợ đầu mối Thủ Đức"),
    }
    db.add_all(suppliers.values())
    db.flush()

    ingredients = {
        "sua": Ingredient(name="Sữa tươi thanh trùng", unit="hộp 1L"),
        "cafe": Ingredient(name="Cà phê hạt Robusta Blend", unit="kg"),
        "tra": Ingredient(name="Trà lài búp đặc biệt", unit="kg"),
        "duong": Ingredient(name="Đường cát trắng", unit="kg"),
        "ly": Ingredient(name="Ly nhựa nắp tim 500ml", unit="cây 50 cái"),
        "syrup": Ingredient(name="Syrup Đào Monin", unit="chai"),
    }
    db.add_all(ingredients.values())
    db.flush()

    # Nhập hàng Tháng 01..09/2026 đa dạng để xem báo cáo & P&L cả năm 2026
    for m_num in range(1, 10):
        early_plan = [
            (date(2026, m_num, 3), "vinamilk", "hoa_don", "Chủ quán (demo)", [("sua", 75 + (m_num % 3) * 10, 31000), ("duong", 35, 22000)]),
            (date(2026, m_num, 11), "tracafe", "hoa_don", "Chủ quán (demo)", [("cafe", 22 + (m_num % 4) * 3, 210000), ("tra", 10, 180000)]),
            (date(2026, m_num, 19), "taphoa", "bien_lai_viet_tay", "Nhân viên A" if m_num % 2 else "Nhân viên B", [("ly", 30, 45000), ("syrup", 6 + (m_num % 3), 185000)]),
            (date(2026, m_num, 25), "chodaumoi", "khong_chung_tu", "Nhân viên C" if m_num % 2 else "Nhân viên D", [("duong", 20, 22000), ("ly", 15, 45000)]),
        ]
        for p_date, s_key, doc_t, creator_name, items in early_plan:
            tot = sum(q * pr for _, q, pr in items)
            p = Purchase(purchase_date=p_date, supplier_id=suppliers[s_key].id, doc_type=doc_t,
                         total_amount=tot, created_by=user_id_map.get(creator_name), created_by_name=creator_name,
                         note=f"Đợt nhập {p_date.strftime('%d/%m/%Y')}")
            db.add(p)
            db.flush()
            for ing_k, q, pr in items:
                db.add(PurchaseItem(purchase_id=p.id, ingredient_id=ingredients[ing_k].id, quantity=q,
                                    unit=ingredients[ing_k].unit, unit_price=pr, line_total=q * pr))

    # Nhập hàng Tháng 10 (~25 triệu đồng)
    oct_purchases_plan = [
        (date(2026, 10, 2), "vinamilk", "hoa_don", "Chủ quán (demo)", [("sua", 100, 31000), ("duong", 50, 22000)]),
        (date(2026, 10, 8), "tracafe", "hoa_don", "Chủ quán (demo)", [("cafe", 30, 210000), ("tra", 15, 180000)]),
        (date(2026, 10, 15), "taphoa", "bien_lai_viet_tay", "Nhân viên A", [("ly", 40, 45000), ("syrup", 10, 185000)]),
        (date(2026, 10, 22), "vinamilk", "hoa_don", "Chủ quán (demo)", [("sua", 80, 31000), ("duong", 40, 22000)]),
        (date(2026, 10, 28), "chodaumoi", "khong_chung_tu", "Nhân viên B", [("cafe", 15, 210000), ("ly", 20, 45000)]),
    ]
    for p_date, s_key, doc_t, creator_name, items in oct_purchases_plan:
        tot = sum(q * pr for _, q, pr in items)
        p = Purchase(purchase_date=p_date, supplier_id=suppliers[s_key].id, doc_type=doc_t,
                     total_amount=tot, created_by=user_id_map.get(creator_name), created_by_name=creator_name,
                     note=f"Đợt nhập {p_date.strftime('%d/%m')}")
        db.add(p)
        db.flush()
        for ing_k, q, pr in items:
            db.add(PurchaseItem(purchase_id=p.id, ingredient_id=ingredients[ing_k].id, quantity=q,
                                unit=ingredients[ing_k].unit, unit_price=pr, line_total=q * pr))

    # Nhập hàng Tháng 11 (~10,2 triệu đồng đến 13/11)
    nov_purchases_plan = [
        (date(2026, 11, 2), "vinamilk", "hoa_don", "Chủ quán (demo)", [("sua", 80, 31000), ("duong", 30, 22000)]),  # 3.140.000
        (date(2026, 11, 5), "tracafe", "hoa_don", "Chủ quán (demo)", [("cafe", 15, 210000), ("tra", 6, 180000)]),    # 4.230.000
        (date(2026, 11, 8), "taphoa", "bien_lai_viet_tay", "Nhân viên B", [("ly", 25, 45000), ("syrup", 5, 185000)]), # 2.050.000
        (date(2026, 11, 12), "chodaumoi", "khong_chung_tu", "Nhân viên A", [("duong", 20, 22000), ("ly", 10, 45000)]), # 890.000
    ]
    for p_date, s_key, doc_t, creator_name, items in nov_purchases_plan:
        tot = sum(q * pr for _, q, pr in items)
        p = Purchase(purchase_date=p_date, supplier_id=suppliers[s_key].id, doc_type=doc_t,
                     total_amount=tot, created_by=user_id_map.get(creator_name), created_by_name=creator_name,
                     note=f"Đợt nhập {p_date.strftime('%d/%m')}")
        db.add(p)
        db.flush()
        for ing_k, q, pr in items:
            db.add(PurchaseItem(purchase_id=p.id, ingredient_id=ingredients[ing_k].id, quantity=q,
                                unit=ingredients[ing_k].unit, unit_price=pr, line_total=q * pr))

    # Tình trạng nguyên liệu R09: Sắp hết, Đã hết, Đã đặt, Đủ
    db.add(IngredientStatusRow(
        ingredient_id=ingredients["sua"].id, status="sap_het", note="Còn 3 hộp tại tủ mát quầy pha chế, dự kiến hết trước ca tối",
        reported_by=user_id_map["Nhân viên A"], reported_by_name="Nhân viên A",
        reported_at=datetime(2026, 11, 13, 9, 15, tzinfo=VN_TZ).astimezone(timezone.utc)
    ))
    db.add(IngredientStatusRow(
        ingredient_id=ingredients["tra"].id, status="het", note="Kiểm tra hũ trà tại quầy đã hết sạch từ sáng, tạm ngưng món trà lài",
        reported_by=user_id_map["Nhân viên C"], reported_by_name="Nhân viên C",
        reported_at=datetime(2026, 11, 13, 10, 30, tzinfo=VN_TZ).astimezone(timezone.utc)
    ))
    db.add(IngredientStatusRow(
        ingredient_id=ingredients["cafe"].id, status="da_dat", note="Đã liên hệ nhà cung cấp giao 20kg trong chiều nay",
        reported_by=user_id_map["Chủ quán (demo)"], reported_by_name="Chủ quán (demo)",
        reported_at=datetime(2026, 11, 13, 11, 0, tzinfo=VN_TZ).astimezone(timezone.utc)
    ))
    # Lịch sử báo nguyên liệu trước đó đã đóng (closed_at != None)
    db.add(IngredientStatusRow(
        ingredient_id=ingredients["duong"].id, status="sap_het", note="Còn khoảng 1kg đường tại quầy cuối ca tối",
        reported_by=user_id_map["Nhân viên B"], reported_by_name="Nhân viên B",
        reported_at=datetime(2026, 11, 11, 20, 0, tzinfo=VN_TZ).astimezone(timezone.utc),
        closed_at=datetime(2026, 11, 12, 8, 30, tzinfo=VN_TZ).astimezone(timezone.utc)
    ))

    # 10. Chi phí vận hành R07 (Tháng 01..11/2026)
    extra_items = [
        "Thay lõi lọc nước RO quầy pha chế",
        "In lại thực đơn & standee khuyến mãi",
        "Sửa khóa cửa & bóng đèn khu vực khách",
        "Mua máy xay sinh tố dự phòng",
        "Vệ sinh máy lạnh định kỳ",
        "Mua khay đá & bình lắc shaker mới",
        "Sửa ống xả bồn rửa quầy bar",
        "Trang trí góc check-in theo mùa",
        "Bảo trì quạt hút & tủ đông",
    ]
    for m_num in range(1, 10):
        elec = 1_850_000 + (m_num % 4) * 180_000
        db.add_all([
            Expense(expense_date=date(2026, m_num, 1), category="co_dinh", item=f"Tiền thuê mặt bằng tháng {m_num}", amount=8_000_000),
            Expense(expense_date=date(2026, m_num, 5), category="co_dinh", item=f"Tiền điện & nước tháng {m_num}", amount=elec),
            Expense(expense_date=date(2026, m_num, 5), category="co_dinh", item="Internet & thu gom rác", amount=350_000),
            Expense(expense_date=date(2026, m_num, 16), category="phat_sinh", item=extra_items[m_num - 1], amount=350_000 + (m_num % 3) * 150_000),
        ])

    # Tháng 10
    db.add_all([
        Expense(expense_date=date(2026, 10, 1), category="co_dinh", item="Tiền thuê mặt bằng tháng 10", amount=8_000_000),
        Expense(expense_date=date(2026, 10, 5), category="co_dinh", item="Tiền điện & nước tháng 10", amount=2_250_000),
        Expense(expense_date=date(2026, 10, 5), category="co_dinh", item="Internet & thu gom rác", amount=350_000),
        Expense(expense_date=date(2026, 10, 15), category="phat_sinh", item="Bảo dưỡng định kỳ máy pha cà phê", amount=750_000),
        Expense(expense_date=date(2026, 10, 22), category="phat_sinh", item="Mua thêm muỗng inox & khay bưng", amount=320_000),
    ])
    # Tháng 11
    db.add_all([
        Expense(expense_date=date(2026, 11, 1), category="co_dinh", item="Tiền thuê mặt bằng tháng 11", amount=8_000_000),
        Expense(expense_date=date(2026, 11, 5), category="co_dinh", item="Tiền điện & nước tháng 11", amount=2_100_000),
        Expense(expense_date=date(2026, 11, 5), category="co_dinh", item="Internet & thu gom rác", amount=350_000),
        Expense(expense_date=date(2026, 11, 9), category="phat_sinh", item="Thay ron cao su máy pha cà phê", amount=350_000),
    ])

    # 11. Chốt lương Tháng 01..10/2026 (E1: lưu rate_a_at_lock & rate_b_at_lock)
    db.flush()
    for m_num in range(1, 11):
        m_str = f"2026-{m_num:02d}"
        m_assigns = list(db.scalars(select(Assignment).where(Assignment.month == m_str)))
        counts: dict[int, dict[str, int]] = {eid: {"sang": 0, "trua": 0, "toi": 0} for eid in emp_list}
        for a in m_assigns:
            if a.employee_id in counts and a.shift_code in counts[a.employee_id]:
                counts[a.employee_id][a.shift_code] += 1
        lock_dt = datetime(2026, m_num + 1, 2, 10, 0, tzinfo=VN_TZ).astimezone(timezone.utc)
        for eid in emp_list:
            ns, ntr, nt = counts[eid]["sang"], counts[eid]["trua"], counts[eid]["toi"]
            amt = ns * int(5.5 * 22000) + ntr * int(5.5 * 25000) + nt * int(4.0 * 25000)
            db.add(PayrollMonth(
                month=m_str, employee_id=eid, n_sang=ns, n_trua=ntr, n_toi=nt,
                amount=amt, rate_a_at_lock=22000, rate_b_at_lock=25000, locked_at=lock_dt
            ))

    # 12. PIN mẫu cho NV A (1111) và NV B (2222) — E-09 Mã PIN dự phòng
    from .services.attendance import hash_pin
    nv_a_user = db.scalar(select(User).where(User.username == "nvA"))
    nv_b_user = db.scalar(select(User).where(User.username == "nvB"))
    if nv_a_user:
        set_setting(db, f"pin_hash_{nv_a_user.id}", hash_pin("1111"))
    if nv_b_user:
        set_setting(db, f"pin_hash_{nv_b_user.id}", hash_pin("2222"))
    set_setting(db, "demo_seed_version", DEMO_SEED_VERSION)

    db.commit()
    return True
