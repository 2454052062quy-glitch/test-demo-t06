# Mô hình cơ sở dữ liệu và nguyên tắc hợp nhất các nguồn dữ liệu rời rạc

Hệ quản trị cơ sở dữ liệu được sử dụng là PostgreSQL 16 tập trung, tách biệt độc lập giữa hai môi trường (`t06_pos_db` cho môi trường Demo và `t06_live_db` cho môi trường Live). Cấu trúc các bảng dưới đây phản ánh chính xác mô hình SQLAlchemy đang vận hành trong mã nguồn của hệ thống.

## 1. Năm nguồn dữ liệu rời rạc tại quán và luồng tích hợp vào hệ thống

| Nguồn dữ liệu hiện trạng | Vị trí lưu trữ trước đây | Người ghi nhận | Luồng tích hợp vào hệ thống mới | Căn cứ khảo sát |
|---|---|---|---|---|
| A. Dữ liệu bán hàng POS365 | Máy bán hàng POS365 và giấy in báo cáo cuối ngày | Nhân viên bấm hóa đơn, Chủ quán gõ lại vào Excel cuối tháng | Đồng bộ qua API `/api/orders` hoặc nạp tệp "Chi tiết doanh thu" | QT1-B1, VII.1, QS02, API Mục 5.1 |
| B. Biên bản giao nhận ca | Sổ biên bản giấy viết tay và ảnh chụp màn hình chuyển khoản trên Zalo | Nhân viên đứng ca | Nhập trực tiếp trên biểu mẫu Giao ca điện tử (F03-A) | QT1-B1 Bảng D, Bảng H, NV03 |
| C. Chứng từ nhập hàng | Hóa đơn giấy, biên lai viết tay tại quầy và ảnh chụp trên Zalo | Nhà cung cấp lập, nhân viên nhận hàng chụp ảnh | Nhập trực tiếp từng lần nhận hàng kèm ảnh chứng từ (F04-A, F04-B) | QT2-B1 Bảng F, Bảng H, CQ04 |
| D. Lịch phân ca và đổi ca | Tệp bảng tính trong nhóm Zalo và tin nhắn cá nhân | Chủ quán xếp lịch, nhân viên tự nhắn tin đổi ca | Nạp tệp bảng tính (F06-B) hoặc khai báo lịch rảnh, xếp lịch và duyệt đổi ca trực tiếp trên web (F06-C đến F06-F) | QT3a-B1, NC-01 C1, C2, CĐ-GV |
| E. Sổ chi phí và bảng tính Lãi/Lỗ | Tệp Excel cá nhân của Chủ quán gồm 4 nhóm chi phí | Chủ quán | Ghi nhận trực tiếp chi phí cố định, phát sinh (F07-A) và nhập số tham chiếu đối chiếu (F07-C) | QT3b-K bước 4, CQ04, VG07 |

Nguồn dữ liệu thứ sáu là thông tin báo hết nguyên liệu qua nhóm Zalo (NC-03 C1, CQ11) được đưa vào hệ thống thông qua chức năng Báo cáo tình trạng nguyên liệu (F09-B).

## 2. Nguyên tắc hợp nhất dữ liệu

1. **Một nguồn sự thật duy nhất cho mỗi chỉ số tài chính:** Doanh thu chỉ lấy từ bảng `pos_orders`. Chi phí nguyên liệu chỉ lấy từ bảng `purchases`. Chi phí nhân công chỉ tính từ bảng phân công lịch ca đã duyệt (`schedule_assignments`) nhân với đơn giá lương. Chi phí cố định và phát sinh chỉ lấy từ bảng `expenses`. Màn hình Báo cáo Lãi/Lỗ hoàn toàn không có ô nhập tay cho chi phí nguyên liệu hay tiền lương nhằm loại bỏ triệt để tình trạng nhập trùng lặp nhiều nơi (QT2-B1 Bảng H).
2. **Khóa liên kết chung theo thời gian kinh doanh:** Các nguồn dữ liệu được liên kết qua ngày kinh doanh `business_date` (tính theo múi giờ GMT+7) và kỳ kế toán `month` (`YYYY-MM`).
3. **Chuẩn hóa múi giờ lưu trữ:** Thời điểm phát sinh giao dịch được lưu dưới dạng `timestamptz` (UTC) và quy đổi sang múi giờ `Asia/Ho_Chi_Minh` khi xác định ngày kinh doanh. Lý do là trường `PurchaseDate` từ API POS365 trả về theo chuẩn UTC (hậu tố Z), trong khi quán mở cửa từ 06:30 sáng giờ Việt Nam (tương ứng 23:30 UTC của ngày hôm trước).
4. **Định dạng tiền tệ:** Toàn bộ số tiền được lưu dưới dạng số nguyên (đồng Việt Nam). Các giá trị thập phân `0.0000` trả về từ POS365 được làm tròn chuẩn xác khi nạp vào cơ sở dữ liệu.

## 3. Cấu trúc bảng dữ liệu và nguồn ánh xạ từng trường

### 3.1 Nhóm bảng doanh thu POS365

**Bảng `pos_orders`**

| Tên cột | Nguồn từ API `/api/orders` | Nguồn từ tệp "Chi tiết doanh thu" | Quy tắc xử lý |
|---|---|---|---|
| `doc_code` (UNIQUE, NOT NULL) | Trường `Code` | Cột Mã chứng từ | Khóa duy nhất dùng để chống nhân đôi hóa đơn (F01-C) |
| `created_at` (timestamptz) | Trường `PurchaseDate` (UTC) | Cột Ngày tạo (giờ địa phương) | Lưu thời điểm tạo đơn chính xác đến phút |
| `business_date` | Quy đổi từ `created_at` theo GMT+7 | Quy đổi tương ứng theo GMT+7 | Có đánh chỉ mục để truy vấn nhanh theo ngày và tháng |
| `total` | Trường `Total` | Cột Tổng cộng | Tổng tiền trước chiết khấu |
| `paid` | Trường `TotalPayment` | Cột Thanh toán | Doanh thu thực nhận dùng để tính tổng doanh thu (D07) |
| `discount` | Trường `Discount` | Cột Chiết khấu | Nếu tệp thiếu cột này thì tính bằng `total - paid` |
| `pos_id` | Trường `Id` | Không có | Lưu để đối soát kỹ thuật với API POS365 |
| `table_name`, `guests` | Trường `Pos`, `NumberOfGuests` | Cột Phòng/Bàn, Số khách | Thông tin bổ trợ hiển thị trên danh sách hóa đơn |
| `source` | Giá trị `'api'` | Giá trị `'file'` | Khi trùng mã chứng từ thì dữ liệu từ API được ưu tiên cập nhật |
| `status` | Trường `Status` | Mặc định hợp lệ | Chỉ tiếp nhận các hóa đơn đã hoàn tất có `Status = 2` (D08) |

Các dòng tổng cộng (`Id = -1` hoặc `Code = "Σ"` trên API, dòng tổng đầu và cuối tệp Excel) cùng các hóa đơn hủy đều bị loại bỏ trước khi ghi vào bảng `pos_orders` và được thống kê riêng trong nhật ký đồng bộ.

**Bảng `pos_sync_logs`**: Lưu trữ lịch sử mỗi lần đồng bộ hoặc nạp tệp, bao gồm `id`, `kind` (`api` hoặc `file`), `started_at`, `finished_at`, `user_id`, `file_name`, `file_sha256`, `rows_read`, `rows_inserted`, `rows_updated`, `rows_duplicate`, `rows_skipped_total`, `rows_skipped_void`, `pos_count_reported`, `sum_paid_reported`, `status` và `error`.

### 3.2 Nhóm bảng biên bản giao ca

**Bảng `shift_handovers`**: Mỗi cặp (`business_date`, `shift_code`) chỉ có duy nhất một biên bản chính thức.

| Tên cột | Nguồn đối chiếu từ biên bản giấy tại quán (QT1-B1 Bảng H) |
|---|---|
| `business_date` | Ngày làm việc |
| `shift_code` (`sang`, `trua`, `toi`) | Ca làm việc |
| `pos_revenue_entered` | Doanh thu hệ thống do nhân viên kiểm tra và nhập |
| `pos_revenue_ref` | Doanh thu tham chiếu tự động lấy từ bảng `pos_orders` tại thời điểm lập phiếu |
| `transfer_total` | Tổng tiền chuyển khoản trong ca do nhân viên cộng từ các ảnh hóa đơn chuyển khoản |
| `shortage_refund` | Khoản tiền thiếu hoặc hoàn trả khách hàng |
| `extra` | Khoản thu chi phát sinh trong ca |
| `cash_handed` | Tiền mặt thực tế kiểm đếm và bàn giao cho ca sau |
| `note` | Ghi chú giải trình (bắt buộc nhập khi có phát sinh hoặc lệch trên 10% so với POS) |
| `giver_id`, `submitted_at`, `receiver_id`, `confirmed_at`, `status` | Thông tin nhân viên ký giao, nhân viên ký nhận và trạng thái biên bản (NV05) |
| `out_of_schedule` | Cờ đánh dấu trường hợp nhân viên lập phiếu không có tên trong lịch phân công ngày hôm đó |

### 3.3 Nhóm bảng nhập hàng và theo dõi nguyên liệu

- **Bảng `suppliers`**: Lưu danh mục nhà cung cấp gồm `id` và `name`.
- **Bảng `ingredients`**: Lưu danh mục nguyên liệu gồm `id`, `name` (duy nhất không phân biệt chữ hoa chữ thường), `unit` và `is_active`.
- **Bảng `purchases`**: Lưu thông tin chung của phiếu nhập gồm `id`, `purchase_date`, `supplier_id`, `doc_type` (`hoa_don`, `bien_lai_viet_tay`, `khong_chung_tu`), `discount`, `total_amount`, `note`, `out_of_schedule`, `created_by` và `created_at`.
- **Bảng `purchase_items`**: Lưu từng dòng mặt hàng trong phiếu nhập gồm `id`, `purchase_id`, `ingredient_id`, `quantity`, `unit`, `unit_price` và `line_total`.
- **Bảng `purchase_attachments`**: Lưu thông tin ảnh chụp chứng từ đính kèm gồm `id`, `purchase_id`, `file_path`, `mime`, `sha256` và `uploaded_by`.
- **Bảng `ingredient_status_reports`**: Lưu lịch sử báo cáo tình trạng kho gồm `id`, `ingredient_id`, `status` (`du`, `sap_het`, `het`, `da_dat`), `note`, `out_of_schedule`, `reported_by`, `reported_at` và `closed_at`.
- **Truy vấn giá nhập gần nhất**: Tự động lấy đơn giá (`unit_price`) từ dòng nhập hàng mới nhất của nguyên liệu đó trong bảng `purchase_items` mà không cần nhân viên nhập lại ở màn hình kho.

### 3.4 Nhóm bảng lịch phân ca, đổi ca, chấm công và tính lương

- **Bảng `employees`**: Lưu hồ sơ nhân sự gồm `id`, `display_name`, `user_id` (liên kết với tài khoản đăng nhập) và `is_active`.
- **Bảng `shift_types`**: Lưu cấu hình 3 ca làm việc (`sang`, `trua`, `toi`), tên ca, số giờ tính lương chuẩn (5,5 giờ cho ca sáng, 5,5 giờ cho ca trưa, 4,0 giờ cho ca tối), giờ bắt đầu `start_time`, giờ kết thúc `end_time` và định biên `capacity`.
- **Bảng `pay_rates`**: Lưu cấu hình đơn giá lương theo giờ gồm `effective_from`, `rate_a` (áp dụng cho ca sáng) và `rate_b` (áp dụng cho ca trưa và ca tối).
- **Bảng `schedule_months`** và **`schedule_assignments`**: Lưu trạng thái lịch tháng (`draft`, `published`, `locked`) và chi tiết phân công từng nhân viên vào từng ngày, từng ca kèm nguồn tạo (`import`, `owner`, `swap`, `auto_draft`).
- **Bảng `availability_declarations`**: Lưu đăng ký lịch rảnh hoặc bận của nhân viên theo từng ca trong tháng.
- **Bảng `swap_requests`**: Lưu yêu cầu đổi nguyên ca (`full_swap`) hoặc nhờ làm phụ giữa ca (`partial_cover`), trạng thái duyệt (`pending`, `approved`, `rejected`, `cancelled`) và người quyết định. Khi Chủ quán duyệt đơn `full_swap`, hệ thống tự động cập nhật trực tiếp người đứng ca trong bảng `schedule_assignments`. Đơn `partial_cover` khi duyệt sẽ giữ nguyên lịch chính và hiển thị ghi chú nhắc Chủ quán trên màn hình bảng lương.
- **Bảng `payroll_months`**: Lưu kết quả tổng hợp số ca sáng, ca trưa, ca tối, tổng tiền lương tháng theo công thức chuẩn và trạng thái khóa sổ lương cuối tháng.
- **Bảng `attendance_logs`**, **`kiosk_qr_tokens`** và **`pos_kiosk_sessions`**: Phục vụ chức năng mở rộng E-09, lưu mã QR dùng 1 lần tại máy quầy, phiên làm việc tại quầy và nhật ký giờ vào/ra thực tế của nhân viên để đối soát.

### 3.5 Nhóm bảng chi phí vận hành và báo cáo Lãi/Lỗ

- **Bảng `expenses`**: Lưu các khoản chi phí cố định (`co_dinh` như tiền thuê mặt bằng, điện, nước, internet) và chi phí phát sinh (`phat_sinh` như sửa chữa thiết bị, mua vật dụng nhỏ) gồm `id`, `expense_date`, `category`, `item`, `amount`, `note` và `created_by`.
- **Bảng `pnl_manual_reference`**: Lưu số liệu do Chủ quán tính thủ công trên Excel theo từng khoản mục của tháng để hệ thống tự động tính độ lệch đối chiếu (F07-C).
- **Công thức tổng hợp Lãi/Lỗ tháng M (F07-B)**:
  Lợi nhuận thuần = Tổng `pos_orders.paid` trong tháng M trừ đi tổng `purchases.total_amount` trong tháng M, trừ đi tổng lương tháng M, trừ đi tổng `expenses.amount` (cả cố định và phát sinh) trong tháng M.

### 3.6 Nhóm bảng quản trị hệ thống và kiểm toán

- **Bảng `users`** và **`sessions`**: Quản lý thông tin tài khoản, vai trò (`owner`, `staff`), mật khẩu đã băm bằng Bcrypt, mã PIN dự phòng tại quầy (`pin_hash`), trạng thái khóa tạm thời khi đăng nhập sai nhiều lần và phiên đăng nhập hiện hành.
- **Bảng `audit_logs`**: Lưu vết toàn bộ các thao tác thêm, sửa, xóa, duyệt và khóa dữ liệu kèm giá trị trước và sau khi thay đổi dưới dạng JSON.

## 4. Cơ chế cô lập hoàn toàn giữa môi trường Demo và Live

| Tiêu chí | Môi trường Demo | Môi trường Live |
|---|---|---|
| Giá trị biến `APP_MODE` | `demo` | `live` |
| Tên cơ sở dữ liệu | `t06_pos_db` | `t06_live_db` |
| Nguồn dữ liệu | Dữ liệu giả lập tự động trong `backend/app/seed.py` | Dữ liệu đồng bộ từ POS365 thật và nhập thực tế tại quán |
| Nhãn nhận diện trên giao diện | `DEMO - MÔ PHỎNG` | `DỮ LIỆU THẬT` (màu đỏ nổi bật) |
| Thư mục lưu tệp đính kèm | Tách riêng cho bản thử nghiệm | Tách riêng ngoài kho mã nguồn (được loại trừ trong `.gitignore`) |