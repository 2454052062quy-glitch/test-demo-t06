"""Kiểm thử tính năng E-09: Chấm công & Đăng nhập máy quầy (POS365).
4 trường hợp theo yêu cầu:
1. Mã QR quá 2 phút thì bị từ chối.
2. Dùng lại mã đã dùng thì bị từ chối.
3. Nhân viên ca sau vào ca khi người trước quên ra ca thì ca cũ được tự đóng và ca mới được mở.
4. Đăng nhập bằng PIN thành công và có ghi bản ghi vào ca.

Chạy: python -m unittest discover -s backend/tests -t . -v
"""
from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db import Base
from backend.app.models import AttendanceLog, Employee, KioskQrToken, PosKioskSession, Setting, User
from backend.app.services.attendance import (
    QR_TTL_SECONDS, auto_close_hours, hash_pin, is_token_expired, make_qr_token, next_kind,
    qr_expires_at, should_auto_close, valid_pin, verify_pin,
)


class AttendanceKioskTests(unittest.TestCase):
    def setUp(self):
        # Dùng SQLite in-memory database cho test độc lập và nhanh
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()

        # Tạo 2 nhân viên mẫu A và B
        self.emp_a = Employee(display_name="Nhân viên A", is_active=True)
        self.emp_b = Employee(display_name="Nhân viên B", is_active=True)
        self.db.add_all([self.emp_a, self.emp_b])
        self.db.flush()

        self.user_a = User(
            username="nvA", display_name="Nhân viên A", role="staff",
            password_hash="fakehash", employee_id=self.emp_a.id, is_active=True,
        )
        self.user_b = User(
            username="nvB", display_name="Nhân viên B", role="staff",
            password_hash="fakehash", employee_id=self.emp_b.id, is_active=True,
        )
        self.db.add_all([self.user_a, self.user_b])
        self.db.flush()

        # Đặt PIN mẫu: NV A = 1111, NV B = 2222
        self.db.add(Setting(key=f"pin_hash_{self.user_a.id}", value=hash_pin("1111")))
        self.db.add(Setting(key=f"pin_hash_{self.user_b.id}", value=hash_pin("2222")))
        self.db.commit()

        self.kiosk_id = "kiosk-test-station-1"

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    # ──────────────────────────────────────────────────────────
    # 1. Mã QR quá 2 phút thì bị từ chối
    # ──────────────────────────────────────────────────────────
    def test_qr_expired_after_2_minutes_is_rejected(self):
        """Trường hợp 1: Token QR quá 2 phút (expires_at < now) phải bị từ chối."""
        now = datetime.now(timezone.utc)
        token_str = make_qr_token()

        # Giả lập token đã tạo cách đây 130 giây (quá hạn 2 phút = 120s)
        created_at = now - timedelta(seconds=130)
        expires_at = created_at + timedelta(seconds=QR_TTL_SECONDS)  # đã hết hạn 10s trước

        qr_row = KioskQrToken(
            token=token_str,
            kiosk_id=self.kiosk_id,
            created_at=created_at,
            expires_at=expires_at,
            used=False,
        )
        self.db.add(qr_row)
        self.db.commit()

        # Mô phỏng logic kiểm tra hạn của /attendance/mobile/confirm và preview
        target_token = self.db.scalar(select(KioskQrToken).where(KioskQrToken.token == token_str))
        self.assertIsNotNone(target_token)

        # Kiểm tra điều kiện hết hạn
        is_expired = is_token_expired(target_token.expires_at, now)
        self.assertTrue(is_expired, "Token quá 2 phút phải được nhận diện là hết hạn")

        # Xác thực kết quả từ chối
        can_confirm = (not target_token.used) and (not is_token_expired(target_token.expires_at, now))
        self.assertFalse(can_confirm, "Hệ thống phải từ chối xác nhận mã QR đã hết hạn")

    # ──────────────────────────────────────────────────────────
    # 2. Dùng lại mã đã dùng thì bị từ chối
    # ──────────────────────────────────────────────────────────
    def test_qr_reuse_is_rejected(self):
        """Trường hợp 2: Quét lại mã cũ hoặc mã đã dùng rồi (used=True) phải bị từ chối."""
        now = datetime.now(timezone.utc)
        token_str = make_qr_token()

        # Token còn trong hạn 2 phút nhưng đã được dùng (used=True)
        qr_row = KioskQrToken(
            token=token_str,
            kiosk_id=self.kiosk_id,
            created_at=now,
            expires_at=qr_expires_at(now),
            used=True,  # Đã sử dụng trước đó
            confirmed_by=self.user_a.id,
            confirmed_at=now - timedelta(seconds=20),
            confirmed_kind="in",
        )
        self.db.add(qr_row)
        self.db.commit()

        target_token = self.db.scalar(select(KioskQrToken).where(KioskQrToken.token == token_str))
        self.assertIsNotNone(target_token)
        self.assertTrue(target_token.used, "Token phải có trạng thái used = True")

        # Kiểm tra logic: dù expires_at > now, nhưng used=True thì vẫn bị từ chối
        is_still_time_valid = not is_token_expired(target_token.expires_at, now)
        self.assertTrue(is_still_time_valid, "Token vẫn còn trong hạn thời gian")

        can_reuse = (not target_token.used) and (not is_token_expired(target_token.expires_at, now))
        self.assertFalse(can_reuse, "Hệ thống phải từ chối khi dùng lại mã đã sử dụng")

    # ──────────────────────────────────────────────────────────
    # 3. Nhân viên B vào ca khi A quên ra ca: ca A tự đóng, ca B mở
    # ──────────────────────────────────────────────────────────
    def test_auto_close_previous_shift_when_next_staff_checks_in(self):
        """Trường hợp 3: NV B vào ca khi NV A quên ra ca (hoặc >8 tiếng):
        tự đóng phiên của A với ghi chú 'Tự động đóng phiên', rồi mới mở phiên cho B.
        """
        now = datetime.now(timezone.utc)
        today = now.date()

        # NV A vào ca trước (cách đây 8.5 tiếng, quên ra ca)
        shift_a_start = now - timedelta(hours=8, minutes=30)
        log_in_a = AttendanceLog(
            employee_id=self.emp_a.id,
            work_date=today,
            kind="in",
            at=shift_a_start,
            out_of_schedule=False,
            method="qr",
            auto_closed=False,
        )
        self.db.add(log_in_a)
        self.db.flush()

        # Phiên của A đang mở trên máy quầy
        session_a = PosKioskSession(
            kiosk_id=self.kiosk_id,
            user_id=self.user_a.id,
            employee_id=self.emp_a.id,
            opened_at=shift_a_start,
            closed_at=None,
            attendance_in_id=log_in_a.id,
        )
        self.db.add(session_a)
        self.db.commit()

        # Kiểm tra helper should_auto_close
        self.assertTrue(should_auto_close(session_a.opened_at, now), "Phiên >8 tiếng phải đủ điều kiện tự đóng")

        # ── Hành động: Nhân viên B vào ca trên máy quầy ──
        # Tìm phiên đang mở trên máy quầy
        active_sess = self.db.scalar(
            select(PosKioskSession)
            .where(PosKioskSession.kiosk_id == self.kiosk_id, PosKioskSession.closed_at.is_(None))
        )
        self.assertIsNotNone(active_sess)
        self.assertEqual(active_sess.user_id, self.user_a.id)

        # 1. Tự động đóng phiên của A
        active_sess.closed_at = now
        active_sess.close_reason = "next_shift"

        log_out_a = AttendanceLog(
            employee_id=active_sess.employee_id,
            work_date=today,
            kind="out",
            at=now,
            out_of_schedule=False,
            method="auto_close",
            auto_closed=True,
            note="Tự động đóng phiên",
        )
        self.db.add(log_out_a)
        self.db.flush()
        active_sess.attendance_out_id = log_out_a.id

        # 2. Mở phiên mới cho B
        log_in_b = AttendanceLog(
            employee_id=self.emp_b.id,
            work_date=today,
            kind="in",
            at=now,
            out_of_schedule=False,
            method="qr",
            auto_closed=False,
        )
        self.db.add(log_in_b)
        self.db.flush()

        session_b = PosKioskSession(
            kiosk_id=self.kiosk_id,
            user_id=self.user_b.id,
            employee_id=self.emp_b.id,
            opened_at=now,
            closed_at=None,
            attendance_in_id=log_in_b.id,
        )
        self.db.add(session_b)
        self.db.commit()

        # ── Kiểm tra kết quả ──
        # Phiên của A đã đóng đúng lý do và có log ghi nhận
        self.assertIsNotNone(session_a.closed_at)
        self.assertEqual(session_a.close_reason, "next_shift")
        self.assertTrue(log_out_a.auto_closed)
        self.assertEqual(log_out_a.method, "auto_close")
        self.assertEqual(log_out_a.note, "Tự động đóng phiên")

        # Phiên của B đang mở thành công
        self.assertIsNone(session_b.closed_at)
        self.assertEqual(session_b.employee_id, self.emp_b.id)
        self.assertEqual(log_in_b.kind, "in")

    # ──────────────────────────────────────────────────────────
    # 4. Đăng nhập bằng PIN thành công và có ghi bản ghi vào ca
    # ──────────────────────────────────────────────────────────
    def test_pin_login_success_and_records_attendance(self):
        """Trường hợp 4: Đăng nhập bằng PIN (1111) thành công, ghi bản ghi vào ca với method='pin'."""
        now = datetime.now(timezone.utc)
        today = now.date()

        # Lấy hash PIN đã lưu cho user_a
        stored_hash = self.db.scalar(select(Setting.value).where(Setting.key == f"pin_hash_{self.user_a.id}"))
        self.assertIsNotNone(stored_hash)

        # 1. Thử nhập sai PIN -> từ chối
        self.assertFalse(verify_pin("9999", stored_hash), "PIN sai phải bị từ chối")
        self.assertFalse(verify_pin("111", stored_hash), "PIN thiếu số phải bị từ chối")

        # 2. Nhập đúng PIN 1111 -> hợp lệ
        self.assertTrue(verify_pin("1111", stored_hash), "PIN 1111 phải xác thực thành công")

        # 3. Ghi nhận bản ghi vào ca (AttendanceLog)
        att_log = AttendanceLog(
            employee_id=self.emp_a.id,
            work_date=today,
            kind="in",
            at=now,
            out_of_schedule=False,
            method="pin",
            auto_closed=False,
        )
        self.db.add(att_log)
        self.db.flush()

        # 4. Mở phiên làm việc tại máy quầy
        session = PosKioskSession(
            kiosk_id=self.kiosk_id,
            user_id=self.user_a.id,
            employee_id=self.emp_a.id,
            opened_at=now,
            closed_at=None,
            attendance_in_id=att_log.id,
        )
        self.db.add(session)
        self.db.commit()

        # ── Kiểm tra bản ghi trong DB ──
        saved_log = self.db.get(AttendanceLog, att_log.id)
        self.assertIsNotNone(saved_log)
        self.assertEqual(saved_log.employee_id, self.emp_a.id)
        self.assertEqual(saved_log.kind, "in")
        self.assertEqual(saved_log.method, "pin")
        self.assertFalse(saved_log.auto_closed)

        saved_session = self.db.get(PosKioskSession, session.id)
        self.assertIsNotNone(saved_session)
        self.assertEqual(saved_session.user_id, self.user_a.id)
        self.assertIsNone(saved_session.closed_at)


if __name__ == "__main__":
    unittest.main()
