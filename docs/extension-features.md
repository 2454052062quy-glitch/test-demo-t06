# Đặc tả các chức năng mở rộng (Extension Features)

Tài liệu này mô tả nhóm chức năng mở rộng được phát triển bổ sung ngoài 6 yêu cầu cốt lõi đã được Chủ quán xác nhận (R01, R03, R04, R06, R07, R09). Mỗi chức năng mở rộng đều có cờ cấu hình riêng để kiểm soát phạm vi, ngoại trừ E-01 và E-02 là tầng bảo mật bắt buộc phải kích hoạt khi chạy ở chế độ dữ liệu thật (`APP_MODE=live`).

| Mã số | Tên chức năng mở rộng | Mức ưu tiên | Quyết định triển khai | Căn cứ khảo sát |
|---|---|---|---|---|
| E-01 | Phân quyền truy cập theo vai trò | Cao | Triển khai và bắt buộc ở bản Live | Căn cứ gián tiếp và chỉ đạo của Giảng viên (CĐ-GV) |
| E-02 | Quản lý phiên đăng nhập và bảo mật tài khoản | Cao | Triển khai và bắt buộc ở bản Live | Căn cứ bảo mật dữ liệu tài chính thực tế |
| E-03 | Nhật ký kiểm toán thao tác hệ thống | Trung bình | Triển khai | NC-02 C2, CQ05 |
| E-04 | Gắn bản ghi với ca làm việc, người nhập và cờ ngoài lịch | Trung bình | Triển khai | NC-02 C4, NC-03 C2 |
| E-05 | Xuất báo cáo ra tệp Excel, CSV và bản in PDF | Trung bình | Triển khai | CQ06, NC-01 C5 |
| E-09 | Xác thực vào/ra ca tại máy quầy bằng mã QR động và PIN | Thấp | Triển khai nâng cấp | VG06 |
| E-11 | Cô lập môi trường chạy thử (Demo) và chạy thật (Live) | Cao | Triển khai | Cam kết bảo mật dữ liệu tại QS02 |
| E-13 | Gợi ý xếp lịch phân ca nháp tự động | Trung bình | Triển khai mới | NC-01 C1, C2 |
| E-06, E-07, E-08, E-10, E-12 | Các cảnh báo tự động ngoài phạm vi khảo sát | Không áp dụng | Đã loại bỏ khỏi hệ thống | Xem chi tiết tại bảng cuối tài liệu |

---

## E-01. Phân quyền truy cập theo vai trò (Role-Based Access Control)
- **Mục tiêu giải quyết:** Đảm bảo mỗi nhân sự tại quán chỉ nhìn thấy và thao tác đúng chức năng thuộc trách nhiệm của mình. Hệ thống thực hiện ẩn các mục điều hướng trên giao diện đồng thời kiểm tra chặt chẽ quyền hạn tại tầng API phía máy chủ.
- **Hai vai trò vận hành thực tế:**
  - **Chủ quán (`owner`):** Có toàn quyền quản trị, bao gồm xem tổng quan tài chính, đồng bộ doanh thu POS, duyệt lịch rảnh, xếp và công bố lịch ca, duyệt đổi ca, chốt bảng lương, xem báo cáo Lãi/Lỗ, quản lý tài khoản, cấp mã PIN và cấu hình máy quầy.
  - **Nhân viên (`staff`):** Xem lịch phân ca đã công bố, đăng ký lịch rảnh, gửi yêu cầu đổi ca hoặc nhờ phụ giữa ca, xem bảng lương cá nhân, thực hiện điểm danh vào/ra ca và thực hiện 3 nghiệp vụ vận hành tại quầy gồm lập biên bản giao ca (R03), ghi nhận phiếu nhập hàng (R04) và báo cáo tình trạng nguyên liệu (R09).
- **Cơ chế xử lý thao tác ngoài lịch phân công (D23):** Khi nhân viên thực hiện giao ca, nhập hàng hoặc báo nguyên liệu vào ngày không có tên mình trong lịch phân công chính thức (ví dụ đi làm thay đột xuất chưa kịp cập nhật lịch), hệ thống mặc định vẫn cho phép lưu bản ghi và tự động gắn nhãn cảnh báo "Ngoài lịch phân công" để Chủ quán hậu kiểm. Nếu muốn siết chặt, Chủ quán có thể bật tùy chọn "Chặn nhân viên thao tác ngoài lịch phân công" (`duty_require_schedule`) trong trang Cài đặt.

## E-02. Quản lý phiên đăng nhập và bảo mật tài khoản
- **Mục tiêu giải quyết:** Bảo vệ dữ liệu doanh thu, tiền lương và chi phí của quán thông qua cơ chế thiết lập tài khoản Chủ quán lần đầu (First-run Setup), quản lý thời hạn phiên đăng nhập (`SESSION_HOURS=12`), bắt buộc độ mạnh mật khẩu, băm mật khẩu bằng thuật toán Bcrypt và tự động khóa tạm thời tài khoản khi đăng nhập sai liên tiếp nhiều lần.
- **Tiện ích cho môi trường trình diễn (Demo):** Ở chế độ `APP_MODE=demo`, màn hình đăng nhập cung cấp thêm các nút chuyển đổi tài khoản nhanh giữa Chủ quán và các Nhân viên để phục vụ việc kiểm thử và trình diễn trước hội đồng (tính năng này tự động bị vô hiệu hóa ở chế độ `live`).

## E-03. Nhật ký kiểm toán thao tác (Audit Log)
- **Mục tiêu giải quyết:** Ghi nhận đầy đủ lịch sử ai đã thực hiện thao tác thêm, sửa, xóa, duyệt hoặc khóa dữ liệu nào, vào thời điểm nào, kèm theo bảng so sánh trực quan giữa giá trị cũ và giá trị mới.
- **Phạm vi truy cập:** Chỉ tài khoản Chủ quán mới có quyền truy cập trang Nhật ký thao tác để phục vụ việc đối soát khi có sai lệch số liệu.

## E-04. Gắn bản ghi vào ca làm việc và người thực hiện
- **Mục tiêu giải quyết:** Mở rộng khả năng truy vết từ biên bản giao ca sang cả phiếu nhập hàng, báo cáo nguyên liệu và sổ chi phí. Mọi bản ghi phát sinh đều lưu định danh người tạo, thời điểm tạo và trạng thái đối chiếu với lịch phân ca trong ngày.

## E-05. Xuất báo cáo ra tệp Excel, CSV và bản in PDF
- **Mục tiêu giải quyết:** Cho phép Chủ quán tải trực tiếp Báo cáo Lãi/Lỗ tháng, Bảng lương và dữ liệu doanh thu ra tệp `.xlsx`, `.csv` hoặc in trực tiếp ra định dạng PDF chuẩn khổ giấy A4 để lưu trữ độc lập ngoài hệ thống.

## E-09. Xác thực vào/ra ca tại máy quầy bằng mã QR động và mã PIN dự phòng
- **Mục tiêu giải quyết:** Giải quyết bài toán chấm công đối chiếu thời gian làm việc thực tế và tự động cấp phiên làm việc cho nhân viên trên máy tính dùng chung tại quầy thu ngân mà không cần chia sẻ mật khẩu của Chủ quán.
- **Thiết kế vận hành:**
  - Màn hình Máy quầy (`/kiosk`) hiển thị mã QR động có hiệu lực trong 2 phút và chỉ sử dụng được một lần duy nhất.
  - Nhân viên dùng điện thoại cá nhân quét mã QR để xác nhận Vào ca hoặc Ra ca. Ngay sau khi xác nhận, hệ thống ghi nhận thời gian vào bảng `attendance_logs` và tự động mở phiên làm việc của nhân viên đó trên màn hình máy quầy.
  - Hỗ trợ nhập mã PIN cá nhân (4 đến 6 chữ số) ngay tại màn hình máy quầy làm phương án dự phòng khi điện thoại nhân viên hết pin hoặc mất kết nối mạng. Khi nhân viên mở `/kiosk` từ tài khoản đã đăng nhập sẵn, hệ thống khóa cố định tên của chính nhân viên đó.
  - Kiểm soát mở phiên làm việc (`has_active_shift`): Nhân viên bắt buộc phải Vào ca bằng QR hoặc PIN mới được thực hiện Ra ca (chặn lỗi HTTP 400 nếu chưa Vào ca) và mới được lập Phiếu giao ca, Nhập hàng hoặc Báo nguyên liệu (nếu chưa mở phiên thì chỉ xem ở chế độ tra cứu và bị chặn HTTP 403).
  - Kiểm tra khung giờ ca (biên độ sớm 60 phút và trễ 60 phút so với giờ ca được phân công), tự động gắn nhãn cảnh báo "Ngoài khung giờ / lịch ca" nếu quét sai khung giờ hoặc ngoài lịch.
  - Tự động đóng phiên làm việc của ca trước nếu nhân viên ca trước quên bấm kết thúc ca khi người ca sau vào nhận ca.
- **Ràng buộc nghiệp vụ:** Dữ liệu chấm công chỉ dùng để Chủ quán theo dõi và đối soát giờ giấc thực tế, hoàn toàn không làm thay đổi công thức tính lương theo ca đã duyệt của quán.

## E-11. Cô lập môi trường Demo và Live
- **Mục tiêu giải quyết:** Đảm bảo an toàn tuyệt đối cho dữ liệu thực tế của quán và tuân thủ cam kết bảo mật thông tin khảo sát (QS02). Môi trường Demo và môi trường Live sử dụng hai tệp cấu hình riêng, hai cơ sở dữ liệu PostgreSQL tách biệt và chạy trên hai cụm cổng mạng độc lập.

## E-13. Gợi ý xếp lịch phân ca nháp tự động
- **Mục tiêu giải quyết:** Hỗ trợ Chủ quán tạo nhanh bản nháp lịch phân ca cho cả tháng dựa trên đăng ký lịch rảnh của nhân viên, giảm thời gian xếp lịch thủ công từ bảng tính.
- **Ba quy tắc thuật toán áp dụng:**
  1. **Tuân thủ lịch rảnh (ràng buộc cứng):** Chỉ phân công nhân viên vào những ca mà nhân viên đó đã đánh dấu có thể làm việc (`available = True`).
  2. **Cân bằng số lượng ca làm việc:** Ưu tiên phân công cho ứng viên đang có tổng số ca được xếp trong tháng ít nhất tính đến thời điểm xét.
  3. **Ưu tiên cụm ca liền kề hợp lý:** Ưu tiên xếp tiếp cho nhân viên vừa làm ca liền trước trong cùng ngày nếu độ lệch số ca nằm trong ngưỡng cho phép (`cluster_fairness_slack = 1`) và không vượt quá số ca tối đa mỗi ngày của một nhân viên (`max_shifts_per_day = 2`).
- **Quyền quyết định cuối cùng:** Kết quả của E-13 chỉ là bản nháp. Chủ quán toàn quyền chỉnh sửa lại từng ô trước khi bấm nút "Công bố lịch" cho nhân viên.

---

## Danh mục các mục mở rộng đã thống nhất loại bỏ (ngày 11/11/2026)

| Mã số | Tên mục đã loại bỏ | Lý do loại bỏ để giữ gọn phạm vi hệ thống |
|---|---|---|
| E-06 | Cảnh báo tự động công thức tiền két | Tránh xung đột với quyết định D01 và xác nhận VG02 của Chủ quán về việc không tự tính công thức tiền két cố định. |
| E-07 | Cảnh báo biến động giá nhập nguyên liệu | Đã hiển thị trực tiếp giá nhập gần nhất trên bảng danh mục nguyên liệu (R09) để Chủ quán theo dõi trực quan. |
| E-08 | Ước tính số lượng tồn kho tự động | Chủ quán đã bác bỏ tại VG05 do định lượng pha chế thực tế có sự gia giảm theo yêu cầu khách hàng. |
| E-10 | Cảnh báo doanh thu ngày thấp bất thường | Không có tiêu chí định lượng trong tài liệu khảo sát thực tế tại quán (NC-01 C8). |
| E-12 | Thông báo đẩy thời gian thực qua WebSocket | Đã được thay thế bằng cơ chế cập nhật cơ sở dữ liệu tức thì kết hợp biểu tượng Chuông thông báo hoạt động trên thanh đầu trang. |