# Danh sách kiểm tra: mỗi R0x đã có chức năng + căn cứ + test

Ba mức xác minh, ghi trung thực theo những gì đã **chạy thật**:
- **Logic + test:** Toàn bộ test suite `pytest` (129/129 tests passed 100%) bao gồm kiểm thử logic, nghiệp vụ, tính toán tiền, lịch ca, POS sync dừng sớm/chạm giới hạn, và bảo mật.
- **Giao diện:** Đã chuẩn hóa toàn bộ bố cục theo bộ Wireframe (Mobile & Desktop), build production sạch qua Vite & Docker.
- **API + CSDL:** FastAPI, SQLAlchemy, PostgreSQL 16, Docker Compose. **✔ Đã chạy thực tế trên Docker & PostgreSQL 16** cho cả bản Demo (3000/8000/5432) và bản Live (3001/8001/5433).

| R | Chức năng | Căn cứ chính | Logic + test | Giao diện | API + CSDL |
|---|---|---|---|---|---|
| R01 | F01-A…F: đồng bộ POS365 (dừng sớm theo mốc ngày, giới hạn trang, timeout), nạp file, chống trùng, lọc dòng tổng/hủy, GMT+7, doanh thu ngày/tháng, nhật ký | NC-01 C5; QT1-B1 C.1.10–11; QS02; API §1, §2, §5.1; VG01 | ✔ `test_pos365`, `test_pos_ingest`, `test_timeutil_config`, `test_upgrades` | ✔ trang Doanh thu POS (3 tab, filter 7 cột, popup JSON mock) | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| R03 | F03-A/B/C: biên bản giao ca (không tự tính tiền két), tham chiếu POS theo ngày & ca, xác nhận bàn giao, bắt buộc ghi chú khi lệch >10% | QT1-B1 Bảng H; NV03, NV05; R03; VG03; D01 | ✔ `test_money_logic` (HandoverTests), `test_upgrades` | ✔ trang Giao ca (tách view Chủ quán / Nhân viên, cảnh báo cam lệch >10%) | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| R04 | F04-A/B/C: phiếu nhập, tính tiền, chiết khấu, ảnh chứng từ, tổng chi phí nguyên liệu tháng | QT2-B1 Bảng F; CQ04; R04; VG04 | ✔ `test_upgrades` (PurchaseCalculationTests) | ✔ trang Nhập hàng (2 cột Nhân viên, bảng + popup chi tiết Chủ quán, nút OCR ghi chú rõ) | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| R06 | F06-A…G: ca và hệ số lương, nạp lịch (2 định dạng), lịch rảnh, xếp/công bố, xem lịch, đổi ca, tính lương | NC-01 C1–C2; QT3a-B1; CQ05; NV06; R06; VG06; CĐ-GV | ✔ `test_schedule_logic`, `test_schedule_formats`, `test_money_logic`, `test_upgrades` | ✔ trang Lịch ca (4 tab), Đổi ca (thẻ duyệt trực quan), Lương (7 cột) | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| R07 | F07-A/B/C: sổ chi phí, lãi/lỗ tháng (chuẩn 7 dòng, pro-rate tạm tính D1), đối chiếu với Excel | QT3b-K; CQ04; R07; VG07 | ✔ `test_money_logic` (PnLTests), `test_upgrades` | ✔ trang Quản lý Tài chính & Lãi/lỗ (2 cột, KPI nổi bật, xuất Excel/CSV/Print) | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| R09 | F09-A/B/C: danh mục, giá nhập gần nhất, trạng thái đủ/sắp hết/hết/đã đặt hàng, tự đóng báo cáo khi báo đủ | NC-03 C1, C9; NV09; R09; VG09; D03 | ✔ `test_upgrades` (IngredientStatusCloseTests) | ✔ trang Nguyên liệu (3 bảng Chủ quán, form + lịch sử Nhân viên) | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| nền | F00-A: đăng nhập, phiên, vai trò, quick-login ở Demo (chặn ở Live), "ngoài lịch" gắn cờ | CĐ-GV; D17, D23 | ✔ `test_access`, `test_timeutil_config`, `test_upgrades` | ✔ Đăng nhập (3 nút Demo, toggle hiện mật khẩu, modal Quên mật khẩu) | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| E-13 | Gợi ý lịch nháp (tuân thủ tối đa 2 ca/người/ngày) | NC-01 C1–C2 (gián tiếp); D24 | ✔ `test_schedule_logic`, `test_upgrades` | ✔ nút Gợi ý lịch nháp trên Lịch ca | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |
| E-09 | Chấm công QR (token HMAC 60s, QR động theo LAN IP, không làm đổi lương) | VG06 | ✔ `test_upgrades` (ShiftConstraintsTests) | ✔ trang QR tại quầy và Nhật ký quét 5 cột | ✔ Đã chạy thực tế trên Docker & PostgreSQL 16 |

R02, R05, R08 không xây theo đúng quyết định đã thống nhất của nhóm và chủ quán (VG02, VG05, VG08). Có test bảo vệ ranh giới: `test_timeutil_config.test_removed_extensions_have_no_flags`.

## Kết quả nghiệm thu thực tế
- Khởi chạy đồng thời 2 stack:
  + Bản Demo (ports: 3000, 8000, 5432)
  + Bản Live (ports: 3001, 8001, 5433)
- Kết nối POS365:
  + Dữ liệu probe thực nghiệm đã được làm sạch và lưu tại `docs/pos365-probe-report.json`.
  + Tích hợp đầy đủ cơ chế dừng sớm theo mốc ngày và chặn max pages, loại bỏ hoàn toàn rủi ro nghẽn mạng và timeout request.
- Seed data đồng nhất, khớp số liệu xuyên suốt toàn bộ các màn hình, đảm bảo doanh thu 2,2–2,8 triệu/ngày và kết quả kinh doanh có lãi nhẹ.
