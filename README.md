# T06 - Hệ thống quản lý Cửa hàng A

Đồ án MAIS03010, đề tài T06: Tích hợp các ốc đảo dữ liệu và báo cáo lãi/lỗ cho quán cà phê Cửa hàng A. Phạm vi triển khai gồm: R01 Doanh thu POS, R03 Giao ca, R04 Nhập hàng, R06 Lịch ca và lương, R07 Chi phí và lãi/lỗ, R09 Nguyên liệu. Các yêu cầu đã loại bỏ theo xác nhận của chủ quán: R02, R05, R08.

Tài liệu tổng hợp cho bản Demo v1 (nộp ngày 15/11/2026) được lưu tại [docs/phase4-demo-report.md](docs/phase4-demo-report.md).

## Tech Stack của hệ thống

- Backend: Python 3.12, FastAPI 0.115.6, Uvicorn 0.32.1, SQLAlchemy 2.0.36, Pydantic 2.10.3, OpenPyXL 3.1.5, Bcrypt 4.2.1, Segno 1.6.1.
- Frontend: React 19.0.0, Vite 6.0.0, Node.js 22, Nginx 1.27.
- Database: PostgreSQL 16 (chạy tách biệt giữa môi trường Demo và Live).
- Đóng gói và triển khai: Docker và Docker Compose.

## Cấu trúc thư mục

```text
demo_t06/
├─ docker-compose.yaml          # Khởi chạy db + backend + frontend
├─ .env.example                 # Mẫu cấu hình cho môi trường Demo
├─ .env.live.example            # Mẫu cấu hình cho môi trường Live (dữ liệu thật)
├─ .gitignore                   # Chặn commit .env, .env.live, dữ liệu thật và ảnh tải lên
├─ backend/
│  ├─ Dockerfile, requirements.txt
│  ├─ tools_probe_pos365.py     # Công cụ kiểm tra API POS365 thực tế
│  ├─ app/
│  │  ├─ main.py, config.py, db.py, models.py, security.py, deps.py, seed.py
│  │  ├─ routers/               # auth, pos, handovers, purchases, schedule, swaps, payroll, finance, attendance
│  │  ├─ services/              # Tầng xử lý nghiệp vụ thuần Python
│  │  └─ devtools/mockdata.py   # Bộ sinh dữ liệu giả lập doanh thu và lịch ca
│  └─ tests/                    # Bộ kiểm thử tự động unittest/pytest
├─ frontend/                    # Ứng dụng React + Vite, phục vụ qua Nginx
├─ data/mock/                   # Dữ liệu mẫu doanh thu và lịch ca hai định dạng
├─ scripts/                     # Các script hỗ trợ dựng hệ thống và chạy kiểm thử
└─ docs/                        # Tài liệu phân tích, ma trận truy vết và báo cáo Phase 4
```

## 1. Hướng dẫn cài đặt và chạy bản Demo (Dữ liệu giả lập)

### Yêu cầu môi trường
- Đã cài đặt Docker và Docker Compose.

### Các bước thực hiện trên máy mới
1. Tạo tệp cấu hình từ tệp mẫu:
   ```bash
   cp .env.example .env
   ```
   Trên Windows PowerShell:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Khởi chạy toàn bộ cơ sở dữ liệu PostgreSQL 16, Backend và Frontend bằng một lệnh:
   ```bash
   docker compose up -d --build
   ```
3. Truy cập ứng dụng tại địa chỉ: http://localhost:3000 (Tài liệu API Swagger tại: http://localhost:8000/docs).

### Tài khoản Demo mặc định
Màn hình đăng nhập bản Demo hỗ trợ nút đăng nhập nhanh hoặc nhập trực tiếp:

| Tài khoản | Mật khẩu mặc định | Vai trò | Nhân sự liên kết |
|---|---|---|---|
| chuquan | demo12345 | Chủ quán | Toàn quyền quản trị |
| nvA | demo12345 | Nhân viên | Nhân viên A (mã PIN máy quầy: 1111) |
| nvB | demo12345 | Nhân viên | Nhân viên B (mã PIN máy quầy: 2222) |
| nvC | demo12345 | Nhân viên | Nhân viên C |
| nvD | demo12345 | Nhân viên | Nhân viên D |

### Đặc tả dữ liệu giả lập (Mock Data)
- Phủ đều **11 tháng trong năm 2026 (từ tháng 01/2026 đến tháng 11/2026)** với hơn 2.000 đơn hàng POS, biến động doanh thu theo mùa.
- Lịch phân công ca đầy đủ các tháng, tuân thủ ràng buộc tối đa 2 ca mỗi người mỗi ngày.
- Phiếu giao ca đủ mọi trạng thái (nháp, chờ nhận, đã xác nhận, mở khóa sửa lại), có phiếu chênh lệch trên 10 phần trăm kèm giải trình.
- Sổ nhập hàng, danh mục nguyên liệu và chi phí vận hành liên thông trực tiếp sang Báo cáo Lãi và Lỗ từng tháng.
- Bảng lương đã được chốt khóa từ tháng 01 đến tháng 10/2026; tháng 11/2026 giữ ở trạng thái mở để kiểm thử thao tác chốt lương.

## 2. Chạy bản Live (Dữ liệu thật)

```bash
cp .env.live.example .env.live   # Điền DB_PASSWORD, SECRET_KEY, POS365_*
docker compose -p t06-live --env-file .env.live up -d --build
```
Truy cập tại: http://localhost:3001. Bản Live sử dụng cơ sở dữ liệu riêng (t06_live_db), tắt chức năng đăng nhập nhanh và áp dụng bắt buộc quy tắc mật khẩu mạnh.

## 3. Truy cập qua mạng LAN và Chấm công QR

1. Đảm bảo máy tính chạy Docker và điện thoại dùng chung mạng Wi-Fi nội bộ.
2. Cập nhật biến `QR_BASE_URL` trong tệp `.env` theo địa chỉ IP LAN của máy chủ (ví dụ: `QR_BASE_URL=http://192.168.2.30:3000`).
3. Mở màn hình Máy quầy tại: http://localhost:3000/kiosk. Hệ thống sinh mã QR động dùng một lần có hiệu lực 120 giây (tự làm mới mỗi 110 giây) kèm tùy chọn nhập mã PIN dự phòng.

## 4. Chạy kiểm thử tự động (Testing)

```bash
pytest backend/tests -v
```
Bộ kiểm thử bao gồm kiểm tra tính toán tài chính, nghiệp vụ giao ca, phân quyền truy cập, đọc xuất lịch ca, đồng bộ POS365 và bảo vệ ranh giới phạm vi dự án.
