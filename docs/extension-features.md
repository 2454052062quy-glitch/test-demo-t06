# Chức năng MỞ RỘNG (tách khỏi lõi)

Cập nhật theo quyết định của nhóm ngày 11/11/2026.

Nguyên tắc: mục dưới đây mang nhãn **MỞ RỘNG**, nằm ngoài 6 yêu cầu chủ quán đã xác nhận (R01, R03, R04, R06, R07, R09). Mỗi mục có cờ cấu hình riêng; tắt thì không có menu, route, bảng phát sinh. Ngoại lệ đã chốt: **E-01 và E-02 bắt buộc, không tắt được khi `APP_MODE=live`** (D17) vì R06 Đường 2 cần định danh người dùng và dữ liệu Live là dữ liệu thật. Ở Demo, hai mục này vẫn có cờ để kiểm thử.

Mức ưu tiên do nhóm đề xuất, chưa được chủ quán xác nhận.

| Mã | Chức năng | Ưu tiên | Quyết định | Căn cứ |
|---|---|---|---|---|
| E-01 | Phân quyền theo vai trò | High | Giữ, bắt buộc ở Live | gián tiếp + CĐ-GV |
| E-02 | Phiên đăng nhập và bảo mật tài khoản | High | Giữ, bắt buộc ở Live | gián tiếp |
| E-03 | Nhật ký thao tác | Medium | Giữ | gián tiếp |
| E-04 | Gắn bản ghi vào ca và người nhập | Medium | Giữ | gián tiếp |
| E-05 | Xuất báo cáo Excel/CSV/PDF | Medium | Giữ | gián tiếp |
| E-09 | Chấm công QR (chỉ log đối chiếu) | Low | Giữ, nâng cấp | VG06 (tùy chọn) |
| E-11 | Cô lập môi trường Demo/Live | High | Giữ | gián tiếp |
| E-13 | Gợi ý xếp lịch nháp | Medium | **Mới** (xem D24) | gián tiếp (NC-01 C1, C2) |
| E-06, E-07, E-08, E-10, E-12 | cảnh báo chênh lệch / giá nhập / tồn kho ước tính / doanh thu thấp / đẩy tức thời | — | **Loại** | xem mục cuối |

---

## E-01. Phân quyền theo vai trò
- **Giải quyết:** Mỗi người chỉ thấy và làm đúng việc. Ẩn menu **và** chặn API ở server (dependency kiểm tra vai trò và trạng thái đứng ca).
- **Vai trò đang hoạt động (đã chốt 11/11):**
  - **Chủ quán:** toàn quyền; duyệt lịch rảnh, đổi ca, phụ giữa ca; xem lãi/lỗ; quản lý tài khoản; cấu hình ca và hệ số lương.
  - **Nhân viên:** xem thời khóa biểu chỉ đọc; khai báo lịch rảnh; gửi yêu cầu đổi ca / phụ giữa ca; xem lương của mình; và khi **đang đứng ca**: giao ca (R03), nhập hàng (R04), báo nguyên liệu (R09). Truy cập qua IP LAN trên điện thoại.
  - **Quản lý ca** và **Kế toán/Xem:** chỉ giữ chỗ trong mô hình (`users.role`), chưa xây, chờ nâng cấp theo quy mô quán.
- **"Ngoài lịch phân công" (D23, chốt 12/11):** nhân viên thao tác giao ca/nhập hàng/báo nguyên liệu vào ngày không có tên trong lịch vẫn **được lưu**, bản ghi gắn cờ "Ngoài lịch phân công" cho chủ quán xem (phục vụ E-04), không trả 403. Lý do: có ngày đổi ca miệng chưa kịp duyệt trên web, và Demo cần cho giảng viên thử ở ngày bất kỳ. Chủ quán bật/tắt chế độ chặn cứng ở Cài đặt (`duty_require_schedule`, mặc định **tắt** ở cả Demo và Live).
- **Căn cứ gián tiếp:** POS365 hiện đã có tài khoản chủ quán riêng để theo dõi, nhân viên thao tác trên máy (NC-01 C5); lương hiện gửi riêng qua Zalo cá nhân (NC-01 C2); CĐ-GV cần định danh người dùng.
- **Rủi ro:** Không chặn nên nhân viên có thể thao tác ngoài lịch; giảm rủi ro bằng cờ cảnh báo và nhật ký (E-03). Thêm thao tác lúc đông khách (bài học VG02).

## E-02. Phiên đăng nhập và bảo mật tài khoản
- **Giải quyết:** First-run Setup tạo chủ quán khi `OWNER_USERNAME` để trống; phiên hết hạn theo `SESSION_HOURS=12`; đăng xuất; đổi mật khẩu; khóa tài khoản sau nhiều lần sai; mật khẩu băm bcrypt/argon2.
- **Căn cứ gián tiếp:** Dữ liệu Live là dữ liệu thật (lương, doanh thu); POS365 cũng dùng phiên `SessionId` có hạn (API §1). **Chưa có căn cứ nghiệp vụ trực tiếp** trong phỏng vấn/quan sát.
- **Rủi ro:** Quên mật khẩu chủ quán (POS từng không nhận mật khẩu đúng, NC-01 C11) cần quy trình khôi phục; chưa có căn cứ về cách làm (D22). Ngưỡng khóa tài khoản đặt cấu hình được.

## E-03. Nhật ký thao tác (audit log)
- **Giải quyết:** Ai sửa/xóa/nhập/duyệt đổi ca gì, lúc nào, giá trị cũ → mới; chủ quán xem được.
- **Căn cứ gián tiếp:** POS365 lưu dấu vết xóa món (NC-02 C2); chủ quán hiện hỏi lại nhân viên các ca đổi để kiểm soát lương (CQ05).
- **Rủi ro:** Nhật ký chứa số liệu lương/tiền nên chỉ chủ quán đọc; dung lượng tăng.

## E-04. Gắn bản ghi vào ca và người nhập
- **Giải quyết:** Biên bản giao ca đã có ca và người; mục này mở rộng sang phiếu nhập, báo nguyên liệu, chi phí để truy vết.
- **Căn cứ gián tiếp:** Chênh lệch hiện do ca sau phát hiện rồi báo lại ca trước (NC-02 C4); nhân viên đứng ca chịu trách nhiệm khi nhận hàng (NC-03 C2).
- **Rủi ro:** POS không có khái niệm ca (D05) nên "ca" lấy từ lịch ca; có thể gán sai khi đổi ca chưa duyệt.

## E-05. Xuất báo cáo Excel/CSV/PDF
- **Giải quyết:** Xuất lãi/lỗ, lịch ca, doanh thu.
- **Căn cứ gián tiếp:** Chủ quán thấy file Excel hiện dùng tiện hơn file xuất của POS (CQ06); quán quen in giấy (NC-01 C5).
- **Rủi ro:** File xuất chứa lương và lãi/lỗ thật; thư mục xuất nằm ngoài repo và trong `.gitignore`.

## E-09. Chấm công QR (chỉ lưu log đối chiếu)
- **Giải quyết:** Tạo và quét QR để ghi giờ Vào/Ra, dùng đối chiếu khi cần. **Ràng buộc đã thống nhất:** lương vẫn tính chẵn theo lịch ca đã duyệt (F06-G), log chấm công **không** đi vào công thức lương, để không phá quy chế hiện tại của quán.
- **Thiết kế:**
  - Trang `/attendance/qr` (chủ quán mở trên máy ở quán) hiển thị QR chứa URL `http://<IP_LAN>:<cổng>/attendance/scan?t=<token>`; token ký HMAC theo cửa sổ thời gian ngắn và tự làm mới.
  - Nhân viên quét bằng **ứng dụng camera có sẵn của điện thoại** (không dùng camera trong trình duyệt, vì trình duyệt chỉ cho mở camera trên HTTPS, còn LAN nội bộ dùng HTTP). Trang mở ra yêu cầu đăng nhập, kiểm tra token còn hạn, rồi ghi Vào hoặc Ra xen kẽ.
  - Chỉ nhân viên có phân công trong ngày mới ghi được.
- **Căn cứ:** Chủ quán nói "nếu được thì có chấm công tốt hơn nữa" (VG06); R06 xếp ở mức Low; hiện quán không ghi giờ (QT3a-B1 G1, C.3a.2).
- **Rủi ro:** Quét hộ (nhờ người khác quét) chỉ giảm được nhờ token ngắn hạn và việc URL chỉ truy cập được trong LAN; chưa có quy tắc đi trễ/về sớm (NC-01 C2) nên log chỉ để xem, không tính tiền; thêm thao tác cho nhân viên.

## E-11. Cô lập môi trường Demo/Live
- **Giải quyết:** Demo (`APP_MODE=demo`, `.env`, `t06_pos_db`, cổng 3000/8000/5432) dùng dữ liệu giả để kiểm thử và làm phương án dự phòng offline khi bảo vệ; Live (`APP_MODE=live`, `.env.live`, `t06_live_db`, cổng 3001/8001/5433, project Compose `t06-live`) kết nối dữ liệu thật, có nhãn "DỮ LIỆU THẬT".
- **Căn cứ gián tiếp:** Cam kết của nhóm ở QS02 (không commit dữ liệu thật, không đưa vào công cụ AI); quy tắc quan sát về ảnh/ghi chép chưa che.
- **Rủi ro:** Cổng 5432 xung đột với PostgreSQL cài sẵn trên Windows (xử lý ghi trong README). Nhầm môi trường: nhãn nổi bật giảm rủi ro.

## E-13. Gợi ý xếp lịch nháp (mới)
- **Giải quyết:** Sinh sẵn bản nháp lịch tháng để chủ quán đỡ xếp tay; chủ quán xem, kéo thả chỉnh các ô trống (Unassigned), rồi bấm "Công bố" (F06-D) để chốt vào CSDL. Không công bố thì nhân viên không thấy.
- **Vì sao nằm ở MỞ RỘNG:** "Xếp ca tự động" **không được đưa thành requirement** (Phụ lục B mục 2; chỉ nghe kể ở NC-01 C1), và CĐ-GV chỉ nói khai báo lịch rảnh, xem thời khóa biểu, đổi ca, duyệt. Thuật toán là đề xuất của nhóm. Lõi (F06-D) vẫn dùng được khi không có E-13.
- **Ba quy tắc (đề xuất của nhóm, 11/11):**
  1. **Khớp lịch rảnh (ràng buộc cứng):** chỉ xếp người có `available = true` tại (ngày, ca). Không khai báo = không rảnh. Người đánh dấu bận bị bỏ qua.
  2. **Công bằng:** ưu tiên ứng viên có tổng số ca đã xếp trong tháng ít nhất, tính đến thời điểm xử lý ô đó (xử lý theo thứ tự ngày, rồi sáng → trưa → tối).
  3. **Cụm ca liền kề:** nếu người vừa làm ca liền trước trong cùng ngày (sáng → trưa, trưa → tối) và vẫn rảnh ca này, tăng ưu tiên để xếp tiếp cho người đó.
- **Tham số tôi đề xuất để quy tắc 3 không phá quy tắc 2 (cần xác nhận, D24):**
  - `cluster_fairness_slack` (mặc định 1): quy tắc 3 chỉ thắng khi số ca của người đó không vượt mức thấp nhất quá ngưỡng này.
  - `max_shifts_per_day` (mặc định 2): tránh một người làm cả 3 ca (5,5 + 5,5 + 4,0 = 15 giờ).
  - Hòa nhau: chọn theo mã nhân viên nhỏ hơn, để chạy lại cho kết quả giống nhau.
- **Căn cứ gián tiếp:** Chủ quán hiện tổng hợp lịch rảnh và chia ca (NC-01 C1, C2). Quy tắc 1 và 2 bám việc chia lịch đồng đều đó. **Quy tắc 3 chưa có căn cứ** trong tài liệu.
- **Rủi ro:** Ca ít người rảnh để trống nhiều; ca tối cuối tháng khó đều; sức chứa ca mặc định 1 người (NC-01 C2) có thể đổi.

---

## Đã loại theo quyết định 11/11/2026 (không xây, không có route/bảng)

| Mã | Chức năng | Ghi chú giữ lại để truy vết |
|---|---|---|
| E-06 | Cảnh báo chênh lệch giao ca vượt ngưỡng | Liên quan D01 (không tự tính tiền két) |
| E-07 | Cảnh báo giá nhập tăng | Giá nhập gần nhất vẫn hiển thị ở R09 (lấy từ R04) |
| E-08 | Tồn kho ước tính | Hướng phát triển sau; mô hình định lượng dễ sai và hao hụt (VG05) |
| E-10 | Cảnh báo doanh thu ngày thấp | Chưa có căn cứ (NC-01 C8) |
| E-12 | Đẩy tức thời khi duyệt đổi ca | Lõi cập nhật CSDL ngay khi duyệt; giao diện làm mới định kỳ (D14) |

## Thuộc lõi, không phải MỞ RỘNG

F06-C, F06-D, F06-E, F06-F (R06 Đường 2, căn cứ CĐ-GV; đưa vào lõi ngày 11/11/2026, D04). Gồm cả loại yêu cầu "Nhờ làm phụ giữa ca / Vắng nửa ca".
