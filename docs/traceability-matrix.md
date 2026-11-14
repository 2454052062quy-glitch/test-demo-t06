# Ma trận truy vết: Yêu cầu - Căn cứ - Chức năng - Màn hình - API - Bảng dữ liệu - Kiểm thử

Trạng thái hiện tại: Đã hoàn thiện và kiểm chứng thực tế trên bản Demo v1 (nộp ngày 15/11/2026, chạy trên Docker và PostgreSQL 16).
Tiền tố API ứng dụng: /api. Các API bên ngoài của POS365 được ghi chú riêng.

## 1. Chức năng lõi

| Mã R | Căn cứ chính | Chức năng | Màn hình | API Endpoint | Bảng dữ liệu | Kiểm thử (Test case) |
|---|---|---|---|---|---|---|
| R01 | NC-01 C5, QT1-B1, QS02, CQ06, VG01, API Mục 5.1 | F01-A: Đồng bộ API POS365 | Trang Doanh thu POS | POST /api/pos/sync | pos_orders, pos_sync_logs | TC-R01-01 phân trang đủ bản ghi, dừng sớm theo mốc ngày; TC-R01-02 tự đăng nhập lại khi 401 |
| R01 | QS02, IMG-QS02 | F01-B: Nạp file doanh thu | Trang Doanh thu POS | POST /api/pos/import | pos_orders, pos_sync_logs | TC-R01-03 file mẫu đủ 8 cột; TC-R01-04 từ chối khi thiếu cột; TC-R01-05 đối soát khối tổng |
| R01 | API Mục 5.1, QS02 | F01-C: Chống trùng dữ liệu | Trang Doanh thu POS | Xử lý trong sync và import | pos_orders (doc_code UNIQUE) | TC-R01-06 nạp 2 lần không trùng; TC-R01-07 đồng bộ API sau file; TC-R01-08 cảnh báo trùng giờ và tổng tiền |
| R01 | API Mục 5.1, IMG-QS02, CQ09 | F01-D: Làm sạch và chuyển đổi múi giờ | Trang Doanh thu POS | Xử lý trong sync và import | pos_orders | TC-R01-09 lọc dòng tổng; TC-R01-10 loại đơn hủy; TC-R01-11 quy đổi UTC sang GMT+7 |
| R01 | G02, R01, VG01 | F01-E: Thống kê doanh thu ngày và tháng | Trang Doanh thu POS | GET /api/revenue/daily, GET /api/revenue/monthly | pos_orders | TC-R01-12 tổng tháng bằng tổng các ngày |
| R01 | G05, API Mục 2 | F01-F: Nhật ký đồng bộ và nhập file | Trang Doanh thu POS (tab Nhật ký) | GET /api/pos/sync-logs | pos_sync_logs | TC-R01-13 số dòng log khớp số dòng đã đọc |
| R03 | QT1-B1 Bảng H, NV03, VG03 | F03-A: Biên bản giao ca điện tử | Trang Giao ca | POST /api/handovers, PUT /api/handovers/{id} | shift_handovers | TC-R03-01 lưu đủ 5 số liệu; TC-R03-02 một biên bản cho mỗi ngày và ca; TC-R03-03 không tự tính tiền két; TC-R03-04 khóa sau khi xác nhận |
| R03 | NV05, QT1-B1 bước 5, VG03 | F03-B: Xác nhận và mở khóa bàn giao | Trang Giao ca | POST /api/handovers/{id}/submit, POST /api/handovers/{id}/confirm, POST /api/handovers/{id}/unlock | shift_handovers | TC-R03-05 người giao không tự xác nhận; TC-R03-06 chuyển đúng trạng thái nháp, chờ nhận, đã xác nhận, yêu cầu xem lại |
| R03 | CQ02, NV01 | F03-C: Tra cứu biên bản giao ca | Trang Giao ca | GET /api/handovers | shift_handovers | TC-R03-07 lọc theo tháng, ca, trạng thái và sai lệch |
| R04 | QT2-B1 Bảng F, CQ04, VG04 | F04-A: Ghi nhận phiếu nhập hàng | Trang Nhập hàng | POST /api/purchases, PUT /api/purchases/{id}, DELETE /api/purchases/{id} | purchases, purchase_items, suppliers | TC-R04-01 tính đúng thành tiền dòng và phiếu; TC-R04-02 nhập phiếu không chứng từ; TC-R04-03 cho phép nhân viên sửa và xóa phiếu do mình tạo |
| R04 | QT2-B1 C.2.6, D12 | F04-B: Đính kèm ảnh hóa đơn | Trang Nhập hàng | POST /api/purchases/{id}/attachments, GET /api/purchases/{id}/attachments/{att_id} | purchase_attachments | TC-R04-04 từ chối tệp không phải ảnh; TC-R04-05 cảnh báo trùng mã băm |
| R04 | R04, QT3b-K C.3b.5 | F04-C: Lịch sử và tổng chi phí nguyên liệu tháng | Trang Nhập hàng | GET /api/purchases, GET /api/purchases/summary | purchases | TC-R04-06 tổng tháng khớp tổng phiếu theo ngày nhập; ẩn KPI tổng tháng với nhân viên |
| R09 | NC-03 C3, NC-01 C6 | F09-A: Danh mục nguyên liệu và giá nhập gần nhất | Trang Nguyên liệu | GET/POST/PUT/DELETE /api/ingredients | ingredients, purchase_items | TC-R09-01 không trùng tên; TC-R09-02 hiển thị đúng giá gần nhất; hỗ trợ sửa và xóa danh mục |
| R09 | NC-03 C1, C9, NV09, VG09 | F09-B: Báo cáo tình trạng nguyên liệu | Trang Nguyên liệu | POST /api/ingredient-status | ingredient_status_reports | TC-R09-03 lưu người báo và thời gian; TC-R09-04 báo đủ sẽ đóng cảnh báo trước đó |
| R09 | CQ11 | F09-C: Bảng theo dõi nguyên liệu cần đặt | Trang Nguyên liệu | GET /api/ingredient-status/open, GET /api/ingredient-status/history | ingredient_status_reports | TC-R09-05 hiển thị đúng danh sách sắp hết hoặc hết và lịch sử báo cáo |
| R06 | CQ05, NV06, R06 | F06-A: Cấu hình khung giờ ca và đơn giá lương | Trang Cài đặt, Trang Lương | GET/PUT /api/shift-types, GET/PUT /api/pay-rates | shift_types, pay_rates | TC-R06-01 đổi đơn giá tính lại tháng chưa chốt; TC-R06-02 tháng đã chốt giữ nguyên đơn giá tại thời điểm khóa |
| R06 | QT3a-B1 C.3a.1, NC-01 C1 | F06-B: Nạp lịch ca từ Excel hoặc CSV hai định dạng | Trang Lịch ca (tab Nạp file) | POST /api/schedules/{month}/import, GET /api/schedules/template.xlsx | schedule_import_batches, schedule_assignments, employees | TC-R06-03 file mẫu đúng số ca; TC-R06-04 ánh xạ tên nhân viên; TC-R06-05 nạp lại không nhân đôi |
| R06 | NC-01 C2, NC-02 C7, CĐ-GV | F06-C: Khai báo lịch rảnh | Trang Lịch ca (tab Lịch rảnh) | GET/PUT /api/availability | availability_declarations | TC-R06-07 nhân viên chỉ sửa lịch rảnh của mình |
| R06 | NC-01 C1, C2, CĐ-GV | F06-D: Xếp lịch và công bố | Trang Lịch ca | PUT /api/schedules/{month}/assignments, POST /api/schedules/{month}/publish | schedule_assignments, schedule_months | TC-R06-09 chưa công bố nhân viên không thấy; TC-R06-10 công bố xong chỉ chủ quán chỉnh sửa |
| R06 | NC-01 C1, CĐ-GV | F06-E: Xem thời khóa biểu | Trang Lịch ca | GET /api/schedules/{month} | schedule_assignments | TC-R06-12 hiển thị ca của tôi và toàn quán; TC-R06-13 cập nhật ngay sau khi duyệt đổi ca |
| R06 | QT3a-B1 C.3a.3, NC-01 C2, CQ05, CĐ-GV | F06-F: Đổi nguyên ca và nhờ phụ giữa ca | Trang Đổi ca và Lịch ca | POST /api/swap-requests, POST /api/swap-requests/{id}/approve, POST /api/swap-requests/{id}/reject | swap_requests, schedule_assignments | TC-R06-14 duyệt đổi nguyên ca cập nhật lịch ngay; TC-R06-21 nhờ phụ giữa ca kiểm tra chặt khung giờ chuẩn của ca và chỉ gắn cờ lương |
| R06 | CQ05, NV06, VG06 | F06-G: Tính lương và chốt lương tháng | Trang Lương tháng | GET /api/payroll/{month}, POST /api/payroll/{month}/lock | payroll_months | TC-R06-18 tính đúng công thức ca sáng, trưa, tối; TC-R06-20 nhân viên chỉ xem lương cá nhân |
| R07 | CQ04, QT3b-K bước 4, VG07 | F07-A: Sổ chi phí vận hành | Trang Chi phí và Lãi/Lỗ | GET/POST/PUT/DELETE /api/expenses | expenses | TC-R07-01 phân nhóm cố định và phát sinh; TC-R07-02 lọc đúng ranh giới tháng |
| R07 | QT3b-K, CQ08, VG07 | F07-B: Báo cáo Lãi và Lỗ tháng | Trang Chi phí và Lãi/Lỗ | GET /api/pnl/{month} | Tổng hợp từ pos_orders, purchases, payroll_months, expenses | TC-R07-03 tính đúng 7 dòng chuẩn theo tháng |
| R07 | G23, D13 | F07-C: Đối chiếu số liệu thủ công | Trang Chi phí và Lãi/Lỗ (tab Đối chiếu) | PUT /api/pnl/{month}/manual-reference, GET /api/pnl/{month}/reconcile | pnl_manual_reference | TC-R07-05 tính chính xác chênh lệch từng khoản mục |
| Nền tảng | CĐ-GV, VG03, D17 | F00-A: Đăng nhập, phiên, vai trò và thông báo | Trang Đăng nhập, Thanh đầu trang | POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me, GET /api/notifications | users, sessions | TC-AUTH-01 thiếu phiên trả 401; TC-AUTH-02 sai vai trò trả 403 |

## 2. Yêu cầu đã loại bỏ khỏi phạm vi

| Mã R | Kết luận | Căn cứ |
|---|---|---|
| R02 | Không xây dựng | VG02 (chủ quán xác nhận không tự tính công thức tiền két) |
| R05 | Không xây dựng | VG05 (chủ quán xác nhận không ước tính tồn kho theo định mức) |
| R08 | Không xây dựng | VG08 (chủ quán xác nhận không tách lãi gộp theo từng món) |

Kiểm thử bảo vệ ranh giới: TC-SCOPE-01 xác nhận hệ thống không chứa route hoặc bảng cho công thức pha chế, định mức tồn kho hay tự tính tiền két.

## 3. Chức năng mở rộng đã triển khai

| Mã | Chức năng | Màn hình và API chính | Bảng dữ liệu | Kiểm thử |
|---|---|---|---|---|
| E-01 | Phân quyền theo vai trò và quy tắc đang đứng ca | Bảo vệ API phía server và ẩn menu giao diện | users.role | TC-E01-01 kiểm tra từng vai trò; TC-E01-02 ghi nhận kèm cờ ngoài lịch |
| E-02 | Quản lý phiên, cài đặt lần đầu, đổi mật khẩu, khóa tài khoản khi nhập sai nhiều lần, ràng buộc mật khẩu mạnh | Trang Thiết lập lần đầu, Trang Đăng nhập, Trang Tài khoản | users, sessions | TC-E02-01 đến TC-E02-04 |
| E-03 | Nhật ký kiểm toán thao tác | Trang Nhật ký thao tác | audit_logs | TC-E03-01 ghi giá trị cũ và mới; TC-E03-02 chỉ chủ quán xem |
| E-04 | Gắn bản ghi vào ca làm việc và người nhập | Cột hiển thị trên các màn hình nghiệp vụ | shift_code, created_by | TC-E04-01 |
| E-05 | Xuất báo cáo Excel, CSV và PDF | Nút xuất ở Báo cáo Lãi/Lỗ, Lịch ca, Doanh thu | Không lưu riêng | TC-E05-01 số liệu xuất khớp hoàn toàn màn hình |
| E-09 | Chấm công tại quầy bằng mã QR động và mã PIN dự phòng | Trang Máy quầy Kiosk, Trang Quét QR điện thoại, Trang Nhật ký công | attendance_logs, kiosk_qr_tokens, pos_kiosk_sessions | TC-E09-01 token hết hạn bị từ chối; TC-E09-02 log chấm công dùng để đối chiếu, không làm sai lệch công thức lương theo lịch |
| E-11 | Cô lập môi trường Demo và Live | Biến APP_MODE, huy hiệu DỮ LIỆU THẬT | Hai CSDL tách biệt t06_pos_db và t06_live_db | TC-E11-01 cô lập hoàn toàn dữ liệu giữa hai môi trường |
| E-13 | Gợi ý xếp lịch nháp tự động theo 3 quy tắc | Nút Gợi ý lịch nháp tại Trang Lịch ca | schedule_assignments (source auto_draft) | TC-E13-01 đến TC-E13-05 |

## 4. Kiểm tra tính nhất quán ma trận

- Mọi yêu cầu trong phạm vi (R01, R03, R04, R06, R07, R09) đều có đầy đủ chức năng tương ứng, màn hình thao tác thực tế, endpoint API, bảng lưu trữ trên PostgreSQL 16 và kiểm thử tự động.
- Toàn bộ chức năng lõi và chức năng mở rộng đã được kiểm chứng thực tế trên cả giao diện máy tính (Sidebar cột trái) và điện thoại (thanh công cụ đáy).
