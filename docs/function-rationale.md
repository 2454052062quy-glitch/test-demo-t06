# Lý do tồn tại của từng chức năng lõi

Mã G, D, căn cứ: xem `gap-analysis.md`. Mỗi chức năng có 4 mục: Làm gì / Vì sao có / Nếu không có thì mất gì / Tiêu chí nghiệm thu. Tiêu chí nghiệm thu so với đường cơ sở AS-IS (gap-analysis mục 3) hoặc kiểm tra được bằng test; không đặt mục tiêu số tuyệt đối vì tài liệu chưa có.

Chức năng MỞ RỘNG nằm riêng ở `extension-features.md`.

---

## Nền tảng bắt buộc (không phải R0x)

### F00-A. Đăng nhập, phiên và vai trò tối thiểu
- **Làm gì:** Đăng nhập bằng tài khoản, phiên có hạn, API kiểm tra vai trò ở server. Hai vai trò đang hoạt động: **Chủ quán** và **Nhân viên**. Nhân viên được giao ca (R03), nhập hàng (R04), báo nguyên liệu (R09). Ngày không có phân công trong lịch ca ("ngoài lịch") **vẫn lưu được và bản ghi gắn cờ "Ngoài lịch phân công"** (E-04), không trả 403; chủ quán có thể bật chế độ chặn cứng ở Cài đặt (`duty_require_schedule`, mặc định tắt). Vai trò Quản lý ca và Kế toán/Xem chỉ để chỗ trong mô hình, chưa xây (quyết định 11/11). Các tính năng bảo mật còn lại thuộc E-01, E-02.
- **Vì sao có:** R06 Đường 2 và R03 cần biết *ai* khai báo lịch, đổi ca, giao ca (G07, G16, G17). Dữ liệu Live là dữ liệu thật (lương, doanh thu). Căn cứ chức năng: CĐ-GV, VG03 ("nhân viên các ca nhập số liệu bàn giao và ký xác nhận"). **Quyết định 11/11:** F00-A (E-01, E-02) bắt buộc, không tắt được khi `APP_MODE=live` (D17 đã chốt). D23 đã chốt 12/11/2026: mặc định không chặn, chỉ gắn cờ, ở cả Demo và Live.
- **Nếu không có:** Không phân biệt được người nhập, không xác nhận bàn giao, mọi người xem được lương.
- **Nghiệm thu:** Gọi API không phiên → 401. Nhân viên gọi API chỉ dành cho chủ quán → 403 dù không có menu. Nhân viên giao ca/nhập hàng ngoài lịch → lưu được kèm cờ; khi chủ quán bật chặn cứng → 403.

---

## R01. Doanh thu POS

### F01-A. Đồng bộ hóa đơn qua API POS365
- **Làm gì:** Gọi `/api/orders?format=json` theo trang (`$top`, `$skip`, kích thước trang 20), xác thực bằng `SessionId` truyền qua `Cookie: ss-id=…`; ánh xạ `Code→doc_code`, `PurchaseDate→created_at`, `TotalPayment→paid`, `Total→total`, `Discount→discount`; gặp 401 thì đăng nhập lại.
- **Vì sao có:** G01. API §1, §2, §5.1; VG01 "1 cần". Cách xử lý lỗi `IncompleteRead`, `JSONDecodeError` là kết quả thực nghiệm của nhóm (không có trong PDF, D08).
- **Nếu không có:** Doanh thu tiếp tục chép tay từ giấy in vào Excel (QT3b-K C.3b.4).
- **Nghiệm thu:** Với dữ liệu giả lập POS (mock server) trả nhiều trang: số bản ghi lưu = số đơn hợp lệ; số dòng đọc khớp `__count`; mất `SessionId` giữa chừng thì đăng nhập lại và tiếp tục.

### F01-B. Nạp file "Chi tiết doanh thu" (.xlsx/.csv)
- **Làm gì:** Nhận file xuất của POS365, tự tìm dòng tiêu đề theo tên cột (8 cột: Mã chứng từ, Ngày tạo, Khách hàng, Phòng/Bàn, Số khách, Chiết khấu, Tổng cộng, Thanh toán), bỏ phần tiêu đề/khối tổng đầu file, đối soát với khối "Số đơn hàng / Tổng thanh toán" ở đầu file nếu có.
- **Vì sao có:** Phương án dự phòng chính thức khi API lỗi hoặc không có quyền. QS02 (T), IMG-QS02, R01 ("thông tin trên Biên bản giao nhận... hạn chế nhập tay").
- **Nếu không có:** Mất đường dự phòng; phụ thuộc hoàn toàn vào API chưa được tài liệu hóa đầy đủ (D09).
- **Nghiệm thu:** File mẫu giả lập đúng bố cục IMG-QS02 nạp được; sai thiếu cột → báo lỗi nêu tên cột thiếu, không lưu gì; tổng nạp khớp khối tổng của file.

### F01-C. Chống nhân đôi theo mã hóa đơn
- **Làm gì:** `doc_code` duy nhất. Nạp lại cùng file hoặc đồng bộ chồng lên file đã nạp không tạo thêm dòng; khác giá trị thì cập nhật và ghi vào nhật ký. Cảnh báo nếu hai dòng trùng giờ và tổng tiền nhưng khác mã (D19).
- **Vì sao có:** G03. Hai đường vào cùng nguồn; chủ quán thường nạp theo kỳ chồng nhau.
- **Nếu không có:** Doanh thu tháng bị cộng đôi, kết quả lãi/lỗ sai mà không biết.
- **Nghiệm thu:** Nạp 2 lần → số dòng không đổi, nhật ký ghi `duplicate = n`. Chạy API sau file → không nhân đôi.

### F01-D. Làm sạch: dòng tổng, đơn hủy, múi giờ
- **Làm gì:** Loại dòng tổng (`Id = -1` hoặc `Code = "Σ"` ở API; dải tổng ở file) và đơn hủy; quy đổi `PurchaseDate` (UTC, hậu tố Z) sang GMT+7 để xác định ngày kinh doanh.
- **Vì sao có:** G04. Quán mở 06:30 (CQ09) = 23:30 UTC ngày hôm trước, nên dùng ngày UTC sẽ đẩy đơn buổi sáng sang ngày trước.
- **Nếu không có:** Số đơn và doanh thu lệch; doanh thu từng ngày sai.
- **Nghiệm thu:** Test có đơn lúc 23:30Z → rơi đúng ngày hôm sau theo giờ VN; dòng tổng và đơn hủy không vào bảng; số đơn khớp khối tổng của file mẫu.

### F01-E. Doanh thu theo ngày/tháng
- **Làm gì:** Bảng và biểu đồ doanh thu theo ngày trong tháng, tổng tháng.
- **Vì sao có:** G02; R01 ("tổng hợp doanh thu tháng từ dữ liệu doanh thu POS theo ngày"); QT3b-K C.3b.8 (chỉ tính theo tháng).
- **Nếu không có:** Chủ quán vẫn phải cộng tay từng ngày.
- **Nghiệm thu:** Tổng tháng = Σ doanh thu ngày = Σ `paid` của đơn hợp lệ trong tháng (D07).

### F01-F. Nhật ký đồng bộ/nhập
- **Làm gì:** Mỗi lần đồng bộ/nhập ghi: thời điểm, người làm, nguồn (API/file, tên và mã băm file), số dòng đọc / thêm / trùng / bỏ (tổng, hủy) / cập nhật, kết quả đối soát, lỗi.
- **Vì sao có:** G05. Căn cứ kỹ thuật (API §2; IMG-QS02), không phải nhu cầu chủ quán nêu (D13 tương tự về tính chất).
- **Nếu không có:** Không truy được vì sao số doanh thu lệch giữa hai lần.
- **Nghiệm thu:** Mỗi thao tác tạo đúng 1 bản ghi nhật ký; tổng các cột số dòng khớp số dòng đọc.

---

## R03. Giao ca

### F03-A. Biên bản giao ca điện tử
- **Làm gì:** Nhân viên (D02; ngoài lịch thì gắn cờ, D23) nhập ngày, ca, Doanh thu hệ thống, Tổng chuyển khoản, Thiếu/trả, Phát sinh, Tiền thực tế giao, ghi chú/lý do; hệ thống hiển thị tổng doanh thu ngày từ R01 bên cạnh để tham chiếu. **Không** tự tính tiền két, không cố định tiền lẻ để lại.
- **Vì sao có:** G07, G08, G09. Biên bản giấy có 7 mục (QT1-B1 Bảng H); R03; VG03 "3 cần". Không tính công thức: R02/VG02 bị bác; D01 đã chốt ngày 11/11: chỉ lưu số nhân viên nhập và lý do.
- **Nếu không có:** Tiếp tục chép tay 2 lần, ảnh Zalo rời rạc; chênh lệch và lý do không có bản ghi.
- **Nghiệm thu:** Lưu đúng 5 số + ghi chú; mỗi (ngày, ca) chỉ một biên bản; thay đổi số liệu sau khi đã xác nhận bị chặn (cần chủ quán mở khóa).

### F03-B. Xác nhận bàn giao
- **Làm gì:** Người giao gửi biên bản; người nhận (nhân viên ca sau hoặc chủ quán, với ca tối) xác nhận; lưu giờ và người ở từng bước.
- **Vì sao có:** NV05 (cả hai ký tên); QT1-B1 bước 5 (chủ quán nhận bàn giao); VG03.
- **Nếu không có:** Không có bằng chứng ai giao, ai nhận (cột "Ký tên" của biên bản giấy mất tác dụng).
- **Nghiệm thu:** Người giao ≠ người nhận; không xác nhận được biên bản của chính mình; trạng thái chuyển đúng: nháp → đã giao → đã xác nhận.

### F03-C. Tra cứu biên bản
- **Làm gì:** Danh sách theo tháng/ca/người, lọc biên bản có Thiếu/trả hoặc ghi chú.
- **Vì sao có:** CQ02/NV01: chênh lệch ngày 02/11 hiện không truy lại được.
- **Nếu không có:** Điều tra chênh lệch phải lục ảnh Zalo.
- **Nghiệm thu:** Lọc theo tháng trả đúng số biên bản; biên bản có Thiếu/trả ≠ 0 lọc ra được.

---

## R04. Nhập hàng

### F04-A. Ghi từng lần nhập
- **Làm gì:** Nhân viên hoặc chủ quán ghi ngày, nhà cung cấp, từng dòng hàng (nguyên liệu, đơn vị, số lượng, đơn giá, thành tiền), chiết khấu (nếu có), loại chứng từ (hóa đơn / biên lai viết tay / không chứng từ), người ghi.
- **Vì sao có:** G10, G11. QT2-B1 Bảng F (các trường có trên chứng từ); CQ04 "Mua lần nào nhập vào lần đó luôn, không nhập tổng"; R04; VG04 "4 cần".
- **Nếu không có:** Chi phí nguyên liệu chỉ có trên giấy; cuối tháng cộng tay.
- **Nghiệm thu:** Thành tiền dòng = SL × đơn giá; tổng phiếu = Σ dòng − chiết khấu; nhập được phiếu "không chứng từ"; cảnh báo mềm khi trùng (NCC, ngày, tổng).

### F04-B. Đính kèm ảnh hóa đơn (tùy chọn)
- **Làm gì:** Đính kèm 1 hay nhiều ảnh vào phiếu nhập; kiểm tra định dạng/dung lượng; lưu mã băm để cảnh báo ảnh trùng.
- **Vì sao có:** Căn cứ gián tiếp: nhân viên đang chụp ảnh gửi Zalo (QT2-B1 C.2.6, bước 5). R04 không yêu cầu trực tiếp (D12).
- **Nếu không có:** Ảnh tiếp tục nằm trong Zalo, không gắn với dòng sổ.
- **Nghiệm thu:** Tệp không phải ảnh bị từ chối; tải lại ảnh đúng phiếu; ảnh không nằm trong repo.

### F04-C. Lịch sử nhập và chi phí nguyên liệu theo tháng
- **Làm gì:** Danh sách phiếu theo tháng, tổng chi phí nguyên liệu tháng (tính theo ngày nhập), cung cấp cho F07-B.
- **Vì sao có:** G12; R04 ("theo dõi lịch sử nhập hàng và tổng hợp chi phí nguyên liệu cuối tháng").
- **Nếu không có:** R07 phải nhập tay chi phí nguyên liệu.
- **Nghiệm thu:** Tổng tháng khớp tổng các phiếu trong tháng; sửa/xóa phiếu cập nhật ngay tổng (có nhật ký nếu bật audit).

---

## R09. Nguyên liệu

### F09-A. Danh mục nguyên liệu
- **Làm gì:** Tên, đơn vị; hiển thị **giá nhập gần nhất** suy từ R04 (không nhập riêng).
- **Vì sao có:** Nền cho F04-A, F09-B; NC-03 C3 (chủ quán theo dõi giá). Giá gần nhất là số đã có ở R04, không phải ước tính.
- **Nếu không có:** Tên nguyên liệu gõ tự do, khó gộp lịch sử.
- **Nghiệm thu:** Không tạo trùng tên (không phân biệt hoa thường); giá gần nhất = giá dòng nhập mới nhất của nguyên liệu đó.

### F09-B. Báo tình trạng nguyên liệu (đủ / sắp hết / hết)
- **Làm gì:** Nhân viên chọn nguyên liệu và tình trạng, ghi chú; lưu người và giờ báo. Lõi R09 chốt ngày 11/11 chỉ gồm danh mục, giá nhập gần nhất, trạng thái (D03).
- **Vì sao có:** G13; NC-03 C1 (rà soát còn đủ khoảng 2 ngày thì báo), C9; NV09; R09; VG09 "9 cần". Không có ngưỡng tự động (R09: không tính tồn kho).
- **Nếu không có:** Báo thiếu vẫn qua Zalo, chủ quán không có danh sách tập trung.
- **Nghiệm thu:** Báo mới ghi đúng người/giờ; báo "đủ" đóng báo cáo trước đó của nguyên liệu.

### F09-C. Bảng theo dõi cho chủ quán
- **Làm gì:** Danh sách nguyên liệu đang sắp hết/hết, sắp theo thời điểm báo.
- **Vì sao có:** CQ11: chủ quán nắm lượng nguyên liệu qua báo cáo Zalo.
- **Nếu không có:** Chủ quán vẫn phải đọc lại tin nhắn nhóm.
- **Nghiệm thu:** Chỉ hiện nguyên liệu có báo cáo mới nhất là sắp hết/hết.

---

## R06. Lịch ca và lương

### F06-A. Cấu hình ca và hệ số lương
- **Làm gì:** Ba ca (sáng 5,5 h; trưa 5,5 h; tối 4,0 h), khung giờ bắt đầu/kết thúc của từng ca và hai mức a, b do **chủ quán tự cấu hình trên giao diện** (D05, D06 đã chốt 11/11). Khung giờ để trống được.
- **Vì sao có:** CQ05, NV06, R06 (ghi chú: "tối" = "chiều" 4,0 h). a, b đã che nên không có số trong tài liệu (D06).
- **Nếu không có:** Công thức lương cứng trong code; đổi mức phải sửa chương trình.
- **Nghiệm thu:** Đổi a hoặc b → lương tháng chưa chốt tính lại đúng; tháng đã chốt không đổi.

### F06-B. Đường 1 – Nạp file Excel/CSV lịch ca đã chốt từ Zalo
- **Làm gì:** Nạp file bảng tính lịch ca theo **hai định dạng** (chốt 12/11): (1) lưới của quán: cột Ngày (hoặc Thứ) + Ca Sáng, Ca Trưa, Ca Tối; (2) danh sách phẳng: Ngày (YYYY-MM-DD hoặc DD/MM/YYYY), Mã ca (Sáng/Trưa/Tối), Tên nhân viên. Có nút "Tải file mẫu .xlsx" cho cả hai ngay trên giao diện. Ánh xạ tên nhân viên trong file với danh sách nhân viên (cho chọn khi tên lạ); báo lỗi theo dòng; nạp lại cùng tháng thay các ca đã nạp từ file, không nhân đôi.
- **Vì sao có:** G15. QT3a-B1 C.3a.1 (T: lịch là file bảng tính trong Zalo nhóm); NC-01 C1. Giữ tương thích hiện trạng, không bắt buộc dùng Đường 2.
- **Nếu không có:** Phải nhập tay lịch cả tháng mới tính được lương.
- **Nghiệm thu:** File mẫu giả lập nạp đúng số ca; tên lạ → không lưu cho đến khi ánh xạ; nạp lại → số ca không đổi; mỗi ca vượt sức chứa (mặc định 1 người, NC-01 C2) bị báo.

### F06-C. Đường 2 – Nhân viên khai báo lịch rảnh
- **Làm gì:** Nhân viên đánh dấu ca rảnh cho tháng tới trước hạn; xem lại bản của mình; chủ quán xem tổng hợp.
- **Vì sao có:** Căn cứ chức năng: CĐ-GV. Căn cứ nền: hiện nhân viên đã gửi lịch rảnh cho chủ quán qua Zalo cá nhân ngày 25 (NC-01 C2; NC-02 C7).
- **Nếu không có:** Khai báo lịch tiếp tục bằng tin nhắn, chủ quán phải tự gom.
- **Nghiệm thu:** Nhân viên chỉ sửa được lịch rảnh của mình, và chỉ trước khi khóa kỳ; chủ quán thấy đủ mọi người.

### F06-D. Chủ quán xếp lịch, duyệt, công bố
- **Làm gì:** Chủ quán xếp từng ca (kéo thả/chọn tay, thấy ai rảnh), công bố; sau công bố nhân viên chỉ đọc. Bản nháp có thể do E-13 (gợi ý xếp lịch, MỞ RỘNG) sinh sẵn; lõi không phụ thuộc E-13.
- **Vì sao có:** CĐ-GV; NC-01 C1, C2 (chủ quán tổng hợp và chia lịch cho đồng đều). "Xếp ca tự động" không phải requirement (Phụ lục B mục 2).
- **Nếu không có:** Đường 2 không có đầu ra.
- **Nghiệm thu:** Chưa công bố → nhân viên không thấy lịch; sau công bố chỉ chủ quán sửa; xếp người không rảnh vẫn được nhưng có cảnh báo.

### F06-E. Xem thời khóa biểu (chỉ đọc)
- **Làm gì:** Lịch tháng của cả quán, đánh dấu ca của chính mình; mở được trên điện thoại qua mạng LAN.
- **Vì sao có:** Hiện lịch gửi Zalo nhóm để cả quán xem (NC-01 C1); CĐ-GV.
- **Nếu không có:** Lịch tiếp tục nằm ở Zalo, không phản ánh các lần đổi ca.
- **Nghiệm thu:** Không có thao tác sửa nào cho Nhân viên; lịch hiện đúng sau khi duyệt đổi ca.

### F06-F. Yêu cầu đổi ca và chủ quán duyệt
- **Làm gì:** Hai loại yêu cầu (D15 đã chốt 11/11). (1) **Đổi nguyên ca:** nhân viên A gửi yêu cầu đổi/nhường một ca cho nhân viên B kèm lý do; chủ quán duyệt hoặc từ chối; khi duyệt, **cùng một giao dịch** cập nhật phân công để tính lương. (2) **Nhờ làm phụ giữa ca / vắng nửa ca:** nhân viên nêu người phụ, khoảng thời gian và lý do; khi chủ quán duyệt, hệ thống **không đổi người đứng ca** (giữ nguyên công thức lương), chỉ tạo cờ cảnh báo ở F06-G. Từ chối thì giữ nguyên.
- **Vì sao có:** G17; CĐ-GV; QT3a-B1 C.3a.3; CQ05. Hành vi mới: duyệt trước thay vì báo cuối tháng (D04, đã đưa vào lõi 11/11). Loại (2) có căn cứ nền ở NC-01 C2 (đến trễ/về sớm nhờ nhau phụ đứng "khoảng đó").
- **Nếu không có:** Đổi ca tiếp tục trôi trong tin nhắn, lương phụ thuộc trí nhớ (NV06).
- **Nghiệm thu:** Duyệt → lịch và số ca tính lương của A, B đổi ngay; hai lần duyệt đồng thời cùng một yêu cầu → chỉ một lần có hiệu lực; A không đổi được ca không phải của mình; duyệt yêu cầu loại "phụ giữa ca" **không** làm đổi `schedule_assignments` và **không** đổi số tiền lương, chỉ tạo cờ. Việc B có phải xác nhận đồng ý trước khi chủ quán duyệt: tài liệu chỉ cho biết nhân viên tự thỏa thuận với nhau (NC-01 C2), chưa có căn cứ quy định bước này nên mặc định không bắt buộc.

### F06-G. Tính giờ công và lương tháng
- **Làm gì:** Đếm số ca sáng/trưa/tối của từng người từ lịch đã duyệt và đổi ca; lương = a×5,5×(số ca sáng) + b×5,5×(số ca trưa) + b×4,0×(số ca tối); chủ quán chốt tháng; nhân viên xem lương của mình (D16). Hiển thị danh sách cờ "phụ giữa ca/vắng nửa ca" đã duyệt trong tháng (ngày, ca, người, người phụ, khoảng giờ, lý do) để chủ quán tự cộng/trừ tay cuối tháng; hệ thống không tính và không lưu khoản điều chỉnh này.
- **Vì sao có:** G18; CQ05, NV06; R06; VG06 "6 cần".
- **Nếu không có:** Nhân viên tự tính tay cuối tháng rồi gửi Zalo.
- **Nghiệm thu:** Ví dụ có số: a=10, b=12, 3 ca sáng, 2 ca trưa, 1 ca tối → 10×5,5×3 + 12×5,5×2 + 12×4×1 = 165 + 132 + 48 = 345 (đơn vị: nghìn đồng, dữ liệu giả). Đổi ca đã duyệt chuyển ca sang đúng người.

---

## R07. Chi phí và lãi/lỗ

### F07-A. Sổ chi phí khác
- **Làm gì:** Ghi từng khoản thuộc nhóm cố định (mặt bằng, điện, nước…) hoặc phát sinh: ngày, nội dung, số tiền, người ghi.
- **Vì sao có:** G21; CQ04; QT3b-K bước 4; VG07 ("nếu thêm được chi phí phát sinh nữa thì tốt"); điện nước thuộc "cố định" (D11).
- **Nếu không có:** Hai nhóm chi phí này vẫn phải gõ vào Excel ngoài hệ thống.
- **Nghiệm thu:** Tổng theo nhóm/tháng đúng; khoản ngày 31 tính vào tháng đó.

### F07-B. Báo cáo lãi/lỗ tháng
- **Làm gì:** Doanh thu (= Σ `TotalPayment`, D07 đã chốt) (F01-E) − nguyên liệu (F04-C) − lương (F06-G) − cố định − phát sinh = lãi/lỗ; thể hiện đủ 4 nhóm chi phí; chỉ theo tháng.
- **Vì sao có:** G20; R07; VG07 "7 cần"; QT3b-K C.3b.8 (không theo món/ca).
- **Nếu không có:** Chủ quán tiếp tục dành khoảng 60 phút (N) gom 5 nguồn vào Excel.
- **Nghiệm thu:** Test tính tay một tháng dữ liệu giả khớp đến từng đồng; tháng thiếu dữ liệu (ví dụ chưa có lịch) hiện cảnh báo "chưa đủ dữ liệu" thay vì hiện số.

### F07-C. Bảng đối chiếu với cách tính thủ công
- **Làm gì:** Người dùng nhập số do cách tính Excel hiện tại cho từng nhóm; hệ thống hiện chênh lệch theo nhóm.
- **Vì sao có:** G23, căn cứ nghiệm thu của nhóm (D13).
- **Nếu không có:** Không chứng minh được hệ thống thay thế Excel.
- **Nghiệm thu:** Chênh lệch từng nhóm = số hệ thống − số nhập tay; để trống nếu chưa nhập.
