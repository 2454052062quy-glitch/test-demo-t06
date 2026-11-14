# Tích hợp POS365

Mỗi điều dưới đây được gắn một trong ba nhãn nguồn:
- **[PDF]** có trong "API Specification Doc (www.pos365.vn) v1.0" (14/06/2021).
- **[Nhóm]** do nhóm kiểm chứng thực tế, **không có trong PDF**. Chưa có tệp bằng chứng đi kèm; chạy `backend/tools_probe_pos365.py` rồi lưu báo cáo (chỉ chứa cấu trúc) vào `docs/` để có căn cứ.
- **[Chưa biết]** chưa có căn cứ; hệ thống dùng giá trị mặc định ghi ở cột cuối.

## 1. Hai đường đưa doanh thu vào

| Đường | Dùng khi | Mã |
|---|---|---|
| API `/api/orders?format=json` | Bình thường | `services/pos365.py` |
| Nạp file "Chi tiết doanh thu" (.xlsx/.csv) | API lỗi, không có quyền, hoặc nạp bù (phương án dự phòng chính thức) | `services/pos_ingest.py` |

Hai đường dùng chung khóa chống trùng `doc_code`; khi trùng mã mà khác giá trị thì **API thắng file** (file không ghi đè API).

## 2. Xác thực

| Điểm | Nội dung | Nguồn |
|---|---|---|
| Đăng nhập | `GET /api/auth/credentials?Username=&Password=&format=json` trả `SessionId` | [PDF] §1 |
| Gửi phiên | Header `Cookie: ss-id=<SessionId>` | [PDF] §3–§5 |
| Hết hạn | HTTP 401 → đăng nhập lại (client làm tự động 1 lần) | [PDF] §1 |
| Tài khoản | Tài khoản admin của cửa hàng | [PDF] §1; quyền thấp có đủ không: [Chưa biết] (D20) |
| `POS365_AUTH_MODE=none` | Bỏ bước đăng nhập, dùng `POS365_EXTRA_HEADERS='{"Cookie":"ss-id=..."}'` | [Nhóm] |
| Lỗi `JSONDecodeError` | SPA trả HTML khi thiếu/sai Cookie. Client báo "phản hồi không phải JSON" kèm 60 ký tự đầu thay vì ném lỗi giải mã | [Nhóm] |

Lưu ý PDF: ví dụ ở §1 ghi mật khẩu `123456` trong mô tả nhưng `1234567` trong lệnh curl (lỗi chính tả trong tài liệu).

## 3. Phân trang

| Điểm | Nội dung | Nguồn |
|---|---|---|
| Tham số | `$top=a&$skip=(n-1)×a`; phản hồi có `__count` là tổng số dòng | [PDF] §2 |
| Kích thước trang | `POS365_PAGE_SIZE=20` để tránh lỗi đứt kết nối `IncompleteRead`; client còn thử lại tối đa 3 lần mỗi trang | [Nhóm] |
| Escape trong `.env` | Viết `$$top`, `$$skip` vì Docker Compose coi `$` là biến; chương trình tự đổi `$$`→`$` nếu chạy ngoài Docker | [Nhóm] |
| Điều kiện dừng | Trang rỗng hoặc đã đủ `__count` (không tin tuyệt đối `__count`, vì chưa rõ có tính dòng tổng) | thiết kế |
| Lọc theo ngày, thứ tự mặc định | PDF §5.1 không nêu | [Chưa biết] (D09): đồng bộ theo trang rồi lọc phía ứng dụng; `tools_probe_pos365.py --try-filter` thử cú pháp |

## 4. Ánh xạ trường `/api/orders`

| Nội bộ | POS365 | Nguồn |
|---|---|---|
| `doc_code` | `Code` | [PDF] §5.1 |
| `created_at` | `PurchaseDate` (UTC, hậu tố Z, 7 chữ số lẻ giây) | [PDF] §5.1 |
| `paid` | `TotalPayment` (**doanh thu = Σ paid**, D07 đã chốt) | [PDF] §5.1 |
| `total` | `Total` | [PDF] §5.1 |
| `discount` | `Discount` | [PDF] §5.1 |
| `pos_id` | `Id` | [PDF] §5.1 |
| `status` | `Status` (đơn hợp lệ `Status = 2`) | [PDF] §5.1, §5.3 |
| `table_name` | `Pos` hoặc `RoomId` (Tên bàn / Khu vực) | [Nhóm] Đã kiểm chứng thực tế |
| `guests` | `NumberOfGuests` (Số lượng khách) | [Nhóm] Đã kiểm chứng thực tế |

Số tiền trả dạng `96185000.0000`; hệ thống làm tròn về đồng (half-up).

## 4.1. Cơ chế đồng bộ chống treo tại bản Live (Nhóm B)
- **Thứ tự trả về**: API POS365 trả về đơn theo thứ tự **mới đến cũ** (PurchaseDate giảm dần).
- **Mốc cắt ngày (Cutoff Date)**: Dừng quét ngay khi gặp đơn hàng có ngày tạo cũ hơn mốc `POS365_SYNC_FROM_DATE` (mặc định là ngày 1 tháng trước). Không quét toàn bộ 15.829 đơn.
- **Giới hạn số trang (Max Pages)**: Giới hạn `POS365_SYNC_MAX_PAGES` (mặc định 50 trang). Khi chạm ngưỡng giới hạn, tiến trình dừng êm, lưu dữ liệu đã nạp và thông báo rõ ràng cho người dùng.
- **Timeout per-request**: Cấu hình `POS365_REQUEST_TIMEOUT=15` giây, trả về thông báo tiếng Việt ngắn gọn, không làm sập container.
- **Nhật ký đồng bộ**: Lưu thời gian bắt đầu/kết thúc, người thực hiện, số đơn mới, số đơn trùng, số trang đã đọc và thông điệp trạng thái đã được làm sạch bảo mật.

## 5. Làm sạch dữ liệu

| Quy tắc | Nguồn |
|---|---|
| Loại dòng tổng `Id = -1` hoặc `Code = "Σ"` | [Nhóm] |
| Loại đơn hủy: chỉ nhận `Status = 2` | [Nhóm] (giá trị 2 chỉ từ ví dụ PDF; D08) |
| Đổi UTC → GMT+7 để tính ngày kinh doanh (quán mở 06:30 = 23:30 UTC ngày trước, CQ09) | [PDF] hậu tố Z + CQ09 |
| File xuất: bỏ khối tiêu đề, bỏ dải tổng dưới dòng tiêu đề và cuối bảng, đối soát với khối "Số đơn hàng / Tổng thanh toán" ở đầu file | IMG-QS02 |
| "Ngày tạo" của file không có múi giờ: coi là giờ GMT+7 | [Chưa biết] (D10) |
| Mã chứng từ tiền tố "OFFLI…" (đơn tạo offline) có đổi mã khi đồng bộ không | [Chưa biết] (D19); chỉ cảnh báo mềm khi cùng phút và cùng số tiền |

## 6. Endpoint không dùng

`/api/orders/detail`, `/api/products`, `/api/partners` và các thao tác ghi/xóa của POS365 **không** được dùng: lõi chỉ cần tổng từng hóa đơn; ghi vào POS365 nằm ngoài phạm vi (và R08, R05 đã loại). Lưu ý PDF §5.2 mô tả `/api/orders/detail` là POST trong bảng nhưng dùng GET trong lệnh curl.

## 7. Tài khoản và dữ liệu thật

- `SessionId`, mật khẩu chỉ ở `.env.live` (đã `.gitignore`).
- Báo cáo của `tools_probe_pos365.py` chỉ chứa cấu trúc (tên trường, đếm theo Status), không có mã đơn, tên bàn, tên khách.
- Thư mục `data/mock/` chỉ chứa dữ liệu giả (mã `HDMOCK-…`, `OFFLINEMOCK-…`).
