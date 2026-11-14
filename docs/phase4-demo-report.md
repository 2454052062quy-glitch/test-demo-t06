# Báo cáo Xây dựng Demo v1 (Nộp ngày 15/11/2026) - Đề tài T06 Cửa hàng A

Tài liệu này tổng hợp hiện trạng triển khai bản Demo v1 của hệ thống quản lý vận hành và tích hợp dữ liệu quán cà phê Cửa hàng A (môn MAIS03010 - Nhóm 08 - IM2402) để nộp đúng hạn ngày 15/11/2026, chuẩn bị cho buổi trình diễn trước lớp ngày 18/11/2026 và thu thập phản hồi người dùng cho vòng hoàn thiện Demo v2.

---

## 1. Kiến trúc và Tech Stack của Demo

Hệ thống được xây dựng theo kiến trúc Web 3 tầng tách biệt hoàn toàn giữa giao diện người dùng, dịch vụ xử lý nghiệp vụ và cơ sở dữ liệu quan hệ tập trung. Toàn bộ ba thành phần được đóng gói bằng Docker Compose để có thể khởi chạy đồng bộ trên máy mới chỉ với một câu lệnh.

| Thành phần | Công nghệ sử dụng | Phiên bản | Vai trò trong hệ thống |
|---|---|---|---|
| Backend API | Python, FastAPI, Uvicorn | Python 3.12, FastAPI 0.115.6, Uvicorn 0.32.1 | Xử lý quy tắc nghiệp vụ, phân quyền theo vai trò, tính toán tài chính, đồng bộ API POS365, xuất báo cáo |
| ORM và Kiểm định dữ liệu | SQLAlchemy, Pydantic, OpenPyXL, Bcrypt, Segno | SQLAlchemy 2.0.36, Pydantic 2.10.3, OpenPyXL 3.1.5, Bcrypt 4.2.1, Segno 1.6.1 | Ánh xạ đối tượng - quan hệ, kiểm tra ràng buộc dữ liệu đầu vào, đọc xuất Excel, băm mật khẩu an toàn, tạo mã QR |
| Frontend Web App | React, Vite, HTML5/CSS3, Nginx | React 19.0.0, Vite 6.0.0, Node.js 22, Nginx 1.27 | Giao diện đáp ứng đa thiết bị (thanh điều hướng cột trái trên máy tính, thanh công cụ dưới đáy trên điện thoại), gọi REST API tới Backend |
| Database Server | PostgreSQL | PostgreSQL 16 (postgres:16-alpine) | Lưu trữ tập trung toàn bộ dữ liệu giao dịch, phân công ca, chấm công, nguyên liệu và sổ kế toán |
| Đóng gói và Triển khai | Docker và Docker Compose | Docker Compose v2 | Tách biệt hoàn toàn môi trường Demo (cổng 3000/8000/5432) và Live (cổng 3001/8001/5433) |

---

## 2. Phạm vi chức năng và Ma trận truy vết (Traceability Matrix)

Hệ thống giải quyết bài toán hợp nhất các ốc đảo dữ liệu rời rạc tại quán (POS365, biên bản giấy giao ca, hóa đơn nhập hàng, bảng tính lịch ca trên Zalo, sổ chi phí Excel) vào một cơ sở dữ liệu duy nhất, đảm bảo thực hiện đầy đủ các thao tác thêm, xem, sửa, xóa (CRUD) và xuất báo cáo quản trị.

| Requirement ID | Tính năng triển khai | Màn hình giao diện | API Endpoint chính | Bảng dữ liệu (PostgreSQL) |
|---|---|---|---|---|
| F00-A, E-01, E-02 | Đăng nhập, quản lý phiên, phân quyền Chủ quán và Nhân viên, ràng buộc mật khẩu mạnh, chuông thông báo hoạt động | Màn hình Đăng nhập, Tài khoản, Chuông thông báo trên thanh đầu trang | POST /api/auth/login, POST /api/auth/setup, POST /api/auth/change-password, GET /api/notifications | users, sessions |
| R01 (F01-A đến F01-F) | Đồng bộ hóa đơn từ API POS365, nạp file Excel hoặc CSV chi tiết doanh thu, chống trùng theo mã chứng từ, lọc đơn hủy và dòng tổng, tổng hợp doanh thu ngày và tháng | Trang Doanh thu POS | POST /api/pos/sync, POST /api/pos/import, GET /api/revenue/daily, GET /api/revenue/monthly, GET /api/pos/sync-logs | pos_orders, pos_sync_logs |
| R03 (F03-A đến F03-C) | Lập biên bản giao ca điện tử, tham chiếu doanh thu POS theo ca, gửi và xác nhận bàn giao, mở khóa chỉnh sửa, bắt buộc giải trình khi lệch trên 10 phần trăm | Trang Giao ca | GET /api/handovers, POST /api/handovers, PUT /api/handovers/{id}, POST /api/handovers/{id}/submit, POST /api/handovers/{id}/confirm, POST /api/handovers/{id}/unlock | shift_handovers |
| R04 (F04-A đến F04-C) | Ghi nhận phiếu nhập hàng theo từng lần, phân loại chứng từ, đính kèm ảnh hóa đơn, tổng hợp chi phí nguyên liệu theo tháng | Trang Nhập hàng | GET /api/purchases, POST /api/purchases, PUT /api/purchases/{id}, DELETE /api/purchases/{id}, POST /api/purchases/{id}/attachments | purchases, purchase_items, purchase_attachments, suppliers |
| R09 (F09-A đến F09-C) | Quản lý danh mục nguyên liệu, tự động cập nhật giá nhập gần nhất từ phiếu nhập, báo tình trạng sắp hết hoặc hết hẳn, theo dõi danh sách cần đặt hàng | Trang Nguyên liệu | GET/POST/PUT/DELETE /api/ingredients, POST /api/ingredient-status, GET /api/ingredient-status/open, GET /api/ingredient-status/history | ingredients, ingredient_status_reports |
| R06 (F06-A đến F06-G), E-13 | Cấu hình khung giờ ca và đơn giá lương, nạp lịch Excel hai định dạng, khai báo lịch rảnh, gợi ý xếp lịch nháp tự động, đổi nguyên ca hoặc nhờ phụ giữa ca, tính và khóa bảng lương | Trang Lịch ca và Đổi ca, Trang Lương tháng, Trang Cài đặt | GET/PUT /api/shift-types, GET/PUT /api/pay-rates, GET/PUT /api/availability, POST /api/schedules/{month}/auto-draft, POST /api/swap-requests, GET /api/payroll/{month}, POST /api/payroll/{month}/lock | shift_types, pay_rates, schedule_months, schedule_assignments, availability_declarations, swap_requests, payroll_months |
| R07 (F07-A đến F07-C), E-05 | Quản lý sổ chi phí cố định và phát sinh, tự động tổng hợp báo cáo Lãi và Lỗ theo tháng từ 4 nguồn dữ liệu, đối chiếu số liệu thủ công, xuất báo cáo Excel, CSV và PDF | Trang Chi phí và Lãi/Lỗ | GET/POST/PUT/DELETE /api/expenses, GET /api/pnl/{month}, PUT /api/pnl/{month}/manual-reference, GET /api/pnl/{month}/export | expenses, pnl_manual_reference |
| E-03, E-04, E-09 | Nhật ký thao tác kiểm toán, gắn cờ bản ghi ngoài lịch phân công, chấm công tại quầy bằng mã QR động và mã PIN dự phòng | Trang Nhật ký thao tác, Trang Nhật ký công, Màn hình Kiosk | GET /api/audit-logs, POST /api/attendance/kiosk/qr, POST /api/attendance/mobile/confirm, POST /api/attendance/kiosk/pin-login | audit_logs, attendance_logs, kiosk_qr_tokens, pos_kiosk_sessions |

Các yêu cầu đã thống nhất loại bỏ khỏi phạm vi hệ thống theo xác nhận của chủ quán: R02 (tự động tính công thức tiền két), R05 (ước tính tồn kho theo định mức pha chế), và R08 (lãi gộp chi tiết theo từng món).

---

## 3. Luồng đi của dữ liệu từ Frontend qua Backend tới Database

Mỗi nghiệp vụ đều tuân theo luồng dữ liệu khép kín và có kiểm soát nhằm hỗ trợ các thành viên giải thích rõ ràng khi trình bày:

1. **Tầng giao diện (Frontend - React)**: Người dùng thao tác trên biểu mẫu (ví dụ: Tạo phiếu nhập hàng, Lập biên bản giao ca, Duyệt đơn đổi ca, hoặc Khóa bảng lương). Trình duyệt đóng gói dữ liệu thành JSON và gửi HTTP request thông qua Nginx Proxy tại đường dẫn /api/... kèm Cookie phiên làm việc t06_session.
2. **Tầng xử lý nghiệp vụ (Backend - FastAPI)**:
   - Bộ kiểm tra phiên và phân quyền (deps.py) xác thực token phiên trong bảng sessions và kiểm tra vai trò owner hoặc staff.
   - Schema Pydantic kiểm tra kiểu dữ liệu, phạm vi số học và ràng buộc định dạng (như độ mạnh mật khẩu, khung giờ ca, giá trị không âm).
   - Tầng dịch vụ thuần Python (thuộc thư mục backend/app/services/) thực thi các quy tắc nghiệp vụ: Quy đổi múi giờ UTC sang GMT+7, kiểm tra chênh lệch giao ca trên 10 phần trăm, gộp đơn vị tính lương, hoặc tính tổng hợp Lãi và Lỗ.
3. **Tầng lưu trữ (Database - PostgreSQL 16)**: SQLAlchemy ORM ghi nhận thay đổi vào các bảng tương ứng trong một giao dịch (transaction) an toàn. Đối với các thao tác thay đổi dữ liệu quan trọng (tạo, sửa, xóa, duyệt, khóa), hệ thống đồng thời ghi lại vết cũ và mới vào bảng audit_logs. Các màn hình tổng hợp như Báo cáo Lãi/Lỗ hoặc Bảng lương truy vấn trực tiếp từ các bảng nguồn sự thật duy nhất (pos_orders, purchases, expenses, schedule_assignments) để đảm bảo không trùng lặp hoặc lệch số liệu.

---

## 4. Dữ liệu giả lập (Mock Data) và Kiểm chứng tính bảo mật thông tin

- **Bảo mật danh tính thật**: Toàn bộ dữ liệu mẫu đều được sinh tự động bằng mã nguồn tại backend/app/seed.py và backend/app/devtools/mockdata.py. Tên nhân sự sử dụng ký hiệu ẩn danh (Nhân viên A, Nhân viên B, Nhân viên C, Nhân viên D), nhà cung cấp và mặt hàng là dữ liệu giả lập phục vụ kiểm thử.
- **Độ phủ và số lượng bản ghi**: Vượt xa ngưỡng tối thiểu 50 bản ghi giao dịch theo quy định, hệ thống hiện cung cấp dữ liệu liên thông xuyên suốt **11 tháng trong năm 2026 (từ tháng 01/2026 đến tháng 11/2026)** với hơn **2.000 hóa đơn POS**, đầy đủ lịch phân công ca, hơn **40 phiếu nhập hàng** kèm chi tiết mặt hàng, sổ chi phí cố định và phát sinh hằng tháng, bảng lương đã chốt từ tháng 01 đến tháng 10/2026, cùng các phiếu giao ca, đơn đổi ca và nhật ký chấm công QR.

---

## 5. Kế hoạch chạy thử ngày 18/11/2026 và Ghi nhận phản hồi người dùng cho Demo v2

Theo lộ trình thực hiện dự án, bản Demo v1 được nộp vào ngày 15/11/2026 với đầy đủ các chức năng cốt lõi, quy trình To-Be và báo cáo quản trị. Trong buổi trình diễn ngày 18/11/2026 và đợt dùng thử thực tế cùng đại diện nhân sự của Cửa hàng A (chủ quán và nhân viên đứng ca), nhóm sẽ trực tiếp ghi nhận phản hồi theo mẫu dưới đây để làm căn cứ điều chỉnh cho bản Demo v2 nộp cùng báo cáo cuối kỳ:

| STT | Đối tượng dùng thử | Phản hồi thực tế ghi nhận | Mức độ ưu tiên | Hướng điều chỉnh dự kiến cho Demo v2 | Trạng thái |
|---|---|---|---|---|---|
| 1 | Chủ quán | Chờ ghi nhận sau buổi chạy thử 18/11/2026 | Đang cập nhật | Tổng hợp yêu cầu thay đổi (Change Request) về báo cáo và phân quyền | Chờ thực hiện |
| 2 | Nhân viên đứng ca | Chờ ghi nhận sau buổi chạy thử 18/11/2026 | Đang cập nhật | Tinh chỉnh thao tác giao ca, nhập hàng, chấm công QR trên thiết bị thực tế tại quán | Chờ thực hiện |

Các kịch bản trọng tâm sẽ kiểm tra cùng người dùng trong buổi dùng thử sắp tới gồm:
- Trải nghiệm giao diện trên hai loại thiết bị: Thanh điều hướng cột trái trên máy tính tại quầy và thanh công cụ đáy gọn trên điện thoại cá nhân.
- Quy trình quét mã QR động và nhập mã PIN dự phòng khi vào ca hoặc ra ca qua mạng nội bộ.
- Độ chính xác và tính trực quan của chuông thông báo hoạt động, bảng lương theo tháng và báo cáo Lãi và Lỗ tổng hợp.

---

## 6. Hướng dẫn cài đặt và Kịch bản trình diễn (Setup Guide)

### Bước 1: Chuẩn bị môi trường
Máy tính cần cài đặt sẵn Docker và Docker Compose (không cần cài đặt thủ công Python, Node.js hay PostgreSQL trên máy chủ).

### Bước 2: Cấu hình biến môi trường
Tại thư mục gốc của dự án, sao chép tệp mẫu cấu hình:
```bash
cp .env.example .env
```
Trong tệp .env, có thể điều chỉnh biến QR_BASE_URL thành địa chỉ IP mạng nội bộ của máy tính (ví dụ http://192.168.2.30:3000) để điện thoại quét được mã QR chấm công. Tuyệt đối không đưa tệp .env thật lên kho lưu trữ mã nguồn.

### Bước 3: Khởi chạy toàn bộ hệ thống bằng một lệnh
```bash
docker compose up -d --build
```
Hệ thống sẽ tự động khởi tạo cơ sở dữ liệu PostgreSQL 16, dựng Backend FastAPI tại cổng 8000, dựng Frontend React tại cổng 3000 và tự động nạp đầy đủ dữ liệu mẫu năm 2026.

### Bước 4: Truy cập và trình diễn quy trình To-Be
1. Truy cập giao diện web tại địa chỉ: http://localhost:3000 (hoặc http://localhost:3000/kiosk cho màn hình máy quầy).
2. Tài liệu API tự động (Swagger UI): http://localhost:8000/docs.
3. Kịch bản trình diễn luồng vận hành chính:
   - Mở màn hình Máy quầy (/kiosk) để quét mã QR hoặc nhập mã PIN vào ca cho Nhân viên A.
   - Ở vai trò Nhân viên: Xem lịch ca, tạo phiếu nhập hàng mới, báo tình trạng nguyên liệu sắp hết, lập biên bản giao ca và gửi bàn giao.
   - Chuyển sang vai trò Chủ quán: Kiểm tra Chuông thông báo, duyệt đơn đổi ca, xác nhận hoặc mở khóa biên bản giao ca, kiểm tra Bảng lương tháng và mở Báo cáo Quản trị Lãi và Lỗ (xuất file Excel hoặc PDF để nghiệm thu).
