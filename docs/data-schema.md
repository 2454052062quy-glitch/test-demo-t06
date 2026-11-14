# Mô hình dữ liệu và hợp nhất các "ốc đảo"

CSDL: PostgreSQL tập trung (một CSDL riêng cho mỗi môi trường: `t06_pos_db` cho Demo, `t06_live_db` cho Live). Tên bảng/cột là đề xuất, sẽ đối chiếu với mô hình SQLAlchemy hiện có khi nhận lại mã nguồn (D18).

## 1. Năm ốc đảo dữ liệu hiện trạng và cách vào hệ thống

| Ốc đảo | Hiện nằm ở đâu | Ai ghi | Đường vào hệ thống mới | Căn cứ |
|---|---|---|---|---|
| A. POS365 | Máy POS365, giấy in báo cáo cuối ngày | Nhân viên bấm bill; chủ quán nhập lại Excel cuối tháng | API `/api/orders` hoặc file "Chi tiết doanh thu" | QT1-B1; VII.1; QS02; API §5.1 |
| B. Biên bản giao nhận | Giấy viết tay + ảnh bill chuyển khoản trên Zalo | Nhân viên ca | Nhập trực tiếp (F03-A) | QT1-B1 Bảng D, H; NV03 |
| C. Chứng từ nhập hàng | Hóa đơn/biên lai giấy tại quán + ảnh Zalo | NCC lập; nhân viên nhận hàng chụp ảnh | Nhập trực tiếp từng lần (F04-A) | QT2-B1 Bảng F, H; CQ04 |
| D. Lịch ca và đổi ca | File bảng tính trong Zalo nhóm; tin nhắn Zalo/Messenger cá nhân | Chủ quán xếp; nhân viên tự đổi | Nạp file (F06-B) hoặc khai báo/xếp/duyệt trên web (F06-C…F) | QT3a-B1 C.3a.1–3a.3; NC-01 C1–C2; CĐ-GV |
| E. Sổ chi phí và Excel chủ quán | File Excel 4 mục (mặt bằng, nguyên liệu, lương, phát sinh); hóa đơn cố định | Chủ quán | Nhập trực tiếp (F07-A); số tham chiếu cho đối chiếu (F07-C) | QT3b-K bước 4; CQ04; VG07 |

Ốc đảo thứ sáu (báo nguyên liệu qua Zalo nhóm, NC-03 C1; CQ11) đi vào bằng F09-B.

## 2. Nguyên tắc hợp nhất

1. **Một nguồn sự thật cho mỗi loại số liệu.** Doanh thu chỉ từ `pos_orders`; chi phí nguyên liệu chỉ từ `purchases`; lương chỉ từ lịch đã duyệt (`schedule_assignments`) × hệ số; chi phí cố định/phát sinh chỉ từ `expenses`. Báo cáo lãi/lỗ **không có ô nhập riêng cho nguyên liệu và lương** để tránh hai nơi cùng ghi (QT2-B1 Bảng H: lỗi hiện tại là cùng thông tin ở nhiều nơi).
2. **Khóa nối chung theo thời gian:** `business_date` (ngày theo GMT+7) và `month` (YYYY-MM). Hiện không có định danh chung để nối tự động giữa 5 nguồn (VII.2.A, dòng QT3).
3. **Thời gian lưu bằng `timestamptz` (UTC); ngày kinh doanh tính theo `Asia/Ho_Chi_Minh`.** Lý do: `PurchaseDate` của POS365 có hậu tố Z (API §5.1); quán mở 06:30 (CQ09) tức 23:30 UTC của ngày trước.
4. **Tiền lưu dạng `numeric(14,0)` (đồng).** POS365 trả `0.0000` (API §5.1); làm tròn khi nạp, ghi nhật ký nếu có phần thập phân khác 0.

## 3. Bảng dữ liệu và nguồn từng trường

### 3.1 Ốc đảo A: POS365

**`pos_orders`**

| Cột | Từ API `/api/orders` | Từ file "Chi tiết doanh thu" | Ghi chú |
|---|---|---|---|
| `doc_code` (UNIQUE, NOT NULL) | `Code` | Mã chứng từ | Khóa chống nhân đôi (F01-C) |
| `created_at` (timestamptz) | `PurchaseDate` (UTC) | Ngày tạo (giờ địa phương, D10) | File có giờ:phút (QS02) |
| `business_date` | tính từ `created_at` theo GMT+7 | như trên | Cột sinh ra, có chỉ mục |
| `total` | `Total` | Tổng cộng | Ánh xạ file→trường là suy luận (S), kiểm bằng cách so file với API cùng ngày |
| `paid` | `TotalPayment` | Thanh toán | Doanh thu = Σ `paid` (D07) |
| `discount` | `Discount` | Chiết khấu | |
| `pos_id` | `Id` | (không có) | Chỉ để đối soát API |
| `table_name`, `guests` | (không dùng ở lõi) | Phòng/Bàn, Số khách | Lưu nếu có, không dùng tính toán |
| `source` | `api` | `file` | Khi hai nguồn trùng mã: API ghi đè file |
| `status` | `Status` | (không có) | Nhận `Status = 2` (D08) |
| `first_seen_log_id`, `last_seen_log_id` | → `pos_sync_logs` | → `pos_sync_logs` | |

Bị loại trước khi lưu: dòng tổng (`Id = -1` hoặc `Code = "Σ"` ở API; dải tổng và khối tiêu đề ở file), đơn hủy. Đếm riêng trong nhật ký.

**`pos_sync_logs`**: `id`, `kind` (api/file), `started_at`, `finished_at`, `user_id`, `file_name`, `file_sha256`, `rows_read`, `rows_inserted`, `rows_updated`, `rows_duplicate`, `rows_skipped_total`, `rows_skipped_void`, `pos_count_reported` (`__count` hoặc "Số đơn hàng" ở đầu file), `sum_paid_reported` ("Tổng thanh toán" ở đầu file), `status`, `error`.

**Chống trùng (cách hợp nhất):**
- Cùng `doc_code` → không thêm dòng. Nếu `total/paid/discount/created_at` khác → cập nhật và tăng `rows_updated`.
- File đã nạp (cùng `file_sha256`) → cảnh báo, cho phép nạp lại (kết quả vẫn không nhân đôi).
- Hai dòng khác mã nhưng cùng `created_at` đến phút và cùng `paid` → cảnh báo mềm (D19: tiền tố "OFFLI…" thấy trong IMG-QS02).

### 3.2 Ốc đảo B: biên bản giao ca

**`shift_handovers`**: một dòng cho mỗi (`business_date`, `shift_code`) UNIQUE.

| Cột | Nguồn trên biên bản giấy (QT1-B1 Bảng H) |
|---|---|
| `business_date` | Ngày |
| `shift_code` (sang/trua/toi) | Tên ca (QT3a-B1 Bảng F) |
| `pos_revenue_entered` | Doanh thu hệ thống (nhân viên nhập) |
| `pos_revenue_ref` | Snapshot tổng doanh thu ngày từ `pos_orders` lúc lưu, chỉ để tham chiếu |
| `transfer_total` | Bill CK (tổng); nhân viên nhập từ ảnh bill, không có đường tự động (QS02: file không có cột CK) |
| `shortage_refund` | Thiếu/trả |
| `extra` | Phát sinh |
| `cash_handed` | Thực tế giao |
| `note` | Ghi chú/lý do (QT1-B1 Bảng F: "Ghi chú bổ sung của người chốt") |
| `giver_id`, `submitted_at`, `receiver_id`, `confirmed_at`, `status` | Cột "Ký tên" (NV05) |

Không có cột "tiền chênh lệch tự tính" (D01). Thêm `out_of_schedule` (bool): cờ "Ngoài lịch phân công" khi người lập không có phân công trong ngày (D23, E-04). Cột này cũng có ở `purchases`, `ingredient_status_reports`, `attendance_logs`; `purchases` và `ingredient_status_reports` có thêm `shift_code` (chỉ gắn khi xác định được duy nhất một ca của người đó trong ngày).

### 3.3 Ốc đảo C: nhập hàng và nguyên liệu

**`suppliers`**: `id`, `name`.
**`ingredients`**: `id`, `name` (UNIQUE không phân biệt hoa thường), `unit`, `is_active`.
**`purchases`**: `id`, `purchase_date`, `supplier_id`, `doc_type` (hoa_don / bien_lai_viet_tay / khong_chung_tu; QT2-B1 C.2.7), `discount` (chiết khấu, Bảng F), `total_amount`, `note`, `created_by`, `created_at`.
**`purchase_items`**: `id`, `purchase_id`, `ingredient_id`, `quantity`, `unit`, `unit_price`, `line_total`. (Quy cách/đóng gói có trên chứng từ nhưng quy đổi đơn vị chưa quan sát: QT2-B1 C.2.12 là KX, nên chỉ lưu `unit` tự do, không quy đổi.)
**`purchase_attachments`** (F04-B): `id`, `purchase_id`, `file_path`, `mime`, `sha256`, `uploaded_by`.
**`ingredient_status_reports`**: `id`, `ingredient_id`, `status` (du / sap_het / het), `note`, `reported_by`, `reported_at`, `closed_at`.
View **`ingredient_last_price`**: giá dòng nhập mới nhất của từng nguyên liệu (không lưu riêng).

Không có số hóa đơn trên danh sách trường quan sát được (Bảng F), nên **không** dùng số hóa đơn làm khóa chống trùng; chỉ cảnh báo mềm theo (nhà cung cấp, ngày, tổng).
Ảnh chứa tên nhà cung cấp và số tiền: lưu ngoài repo, thư mục riêng từng môi trường.

### 3.4 Ốc đảo D: lịch ca, đổi ca, lương

**`employees`**: `id`, `display_name`, `user_id` (nullable: nhân viên chỉ có trong file lịch chưa có tài khoản), `is_active`.
**`shift_types`**: `code` (sang/trua/toi), `name`, `hours` (5,5 / 5,5 / 4,0), `start_time`, `end_time` (nullable, D05), `capacity` (mặc định 1, NC-01 C2).
**`pay_rates`**: `effective_from`, `rate_a`, `rate_b` (đơn vị tiền/giờ, D06).
**`schedule_months`**: `month`, `status` (draft/published/locked), `published_at`, `published_by`.
**`schedule_assignments`**: `id`, `month`, `work_date`, `shift_code`, `employee_id`, `source` (import/owner/swap/auto_draft), `updated_at`.
**`schedule_import_batches`**: `id`, `month`, `file_name`, `file_sha256`, `rows`, `unmapped_names`, `status`, `user_id`.
**`availability_declarations`** (Đường 2): `id`, `month`, `employee_id`, `work_date`, `shift_code`, `available`, `submitted_at`.
**`swap_requests`** (Đường 2): `id`, `kind` (`full_swap` / `partial_cover`), `work_date`, `shift_code`, `from_employee_id`, `to_employee_id` (người nhận ca hoặc người phụ), `from_time`, `to_time` (chỉ `partial_cover`, tùy chọn), `reason`, `status` (pending/approved/rejected/cancelled), `requested_at`, `decided_by`, `decided_at`, `decision_note`. Chỉ `full_swap` đã duyệt mới đổi `schedule_assignments`; `partial_cover` đã duyệt chỉ hiện thành cờ ở màn hình lương.
**`payroll_months`**: `month`, `employee_id`, `n_sang`, `n_trua`, `n_toi`, `amount`, `computed_at`, `locked_by`, `locked_at`.
**`app_settings`**: `key`, `value` (ví dụ `duty_require_schedule`, `session_hours`, `cluster_fairness_slack`).
**`attendance_logs`** (E-09, chỉ ghi log đối chiếu, **không** đi vào `payroll_months`): `id`, `employee_id`, `work_date`, `shift_code` (nullable), `kind` (in/out), `at`, `qr_window`.
**`schedule_draft_runs`** (E-13): `id`, `month`, `run_at`, `run_by`, `params` (json), `unassigned_count`.

Hợp nhất hai đường vào lịch ca:
- Cả Đường 1 (nạp file) và Đường 2 (xếp trên web) cùng ghi `schedule_assignments`; chỉ khác `source`. Một tháng ở một thời điểm có **một** bản lịch hiệu lực.
- Nạp file lại cho tháng đang `draft` thay thế các dòng `source = import` của tháng, không đụng dòng `owner`/`swap`.
- Duyệt đổi ca: trong **một giao dịch** (a) khóa dòng yêu cầu, (b) kiểm tra trạng thái còn `pending`, (c) đổi `employee_id` của ca tương ứng, (d) ghi `source = swap`, (e) đặt `approved`. Lương đọc từ `schedule_assignments` nên tự theo (cập nhật "ngay" ở mức CSDL; giao diện làm mới định kỳ, D14).
- Công thức: `amount = a × 5,5 × n_sang + b × 5,5 × n_trua + b × 4,0 × n_toi` (CQ05, NV06). Tháng `locked` không tính lại khi đổi `pay_rates`.

### 3.5 Ốc đảo E: chi phí và lãi/lỗ

**`expenses`**: `id`, `expense_date`, `category` (co_dinh / phat_sinh), `item`, `amount`, `note`, `created_by`. Điện, nước xếp `co_dinh` (D11, VII.1). Nguyên liệu và lương **không** nhập ở đây.
**`pnl_manual_reference`** (F07-C): `month`, `revenue`, `ingredients`, `payroll`, `fixed`, `other`, `entered_by`, `entered_at`.

**Lãi/lỗ tháng M** (F07-B):
`profit = Σ pos_orders.paid (business_date ∈ M) − Σ purchases.total_amount (purchase_date ∈ M) − Σ payroll_months.amount (month = M) − Σ expenses.amount (category = co_dinh, M) − Σ expenses.amount (category = phat_sinh, M)`.
Thiếu một nguồn (chưa nạp POS, chưa có lịch, chưa có phiếu) → báo "chưa đủ dữ liệu" cho nguồn đó.

### 3.6 Nền tảng và mở rộng

**`users`**: `id`, `username` (UNIQUE), `display_name`, `role` (`owner`, `staff` đang dùng; `shift_manager`, `accountant` để chỗ, chưa xây), `password_hash`, `is_active`, `failed_attempts`, `locked_until`, `created_at`. **`sessions`**: `token_hash`, `user_id`, `expires_at`. (Hạ tầng F00-A; các cột khóa tài khoản dùng cho E-02.)
**`audit_logs`** (E-03): `id`, `at`, `user_id`, `action`, `entity`, `entity_id`, `old_value` (json), `new_value` (json).
Các bảng của chức năng MỞ RỘNG (`audit_logs`, `attendance_logs`, `schedule_draft_runs`) chỉ tạo khi bật tính năng tương ứng. Bảng cảnh báo (`alert_rules`) **không còn**: E-06, E-07, E-10 đã loại.

## 4. Tách biệt Demo và Live

| | Demo | Live |
|---|---|---|
| `APP_MODE` | `demo` | `live` |
| CSDL | `t06_pos_db` | `t06_live_db` |
| Dữ liệu | Giả lập trong `data/mock/` | Từ POS365 thật và nhập tay của quán |
| Nhãn giao diện | (không) | "DỮ LIỆU THẬT" |
| Thư mục ảnh/tệp tải lên | riêng | riêng, ngoài repo |

Ràng buộc quyền riêng tư theo cam kết của nhóm ở QS02: không commit file xuất thật lên GitHub, không đưa vào công cụ AI/OCR. Vì vậy `data/mock/` chỉ mô phỏng **cấu trúc** (8 cột, bố cục như IMG-QS02), số liệu và tên đều là giả; `.gitignore` loại `.env`, `.env.live`, thư mục tải lên và mọi tệp xuất thật.
