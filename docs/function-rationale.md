# Cơ sở thiết kế và tiêu chí nghiệm thu từng chức năng lõi

Tài liệu này giải trình lý do tồn tại của từng chức năng trong hệ thống dựa trên kết quả phân tích khoảng trống (`gap-analysis.md`). Mỗi chức năng được làm rõ qua 4 khía cạnh: Nội dung thực hiện, Căn cứ hình thành, Hệ quả nếu thiếu vắng và Tiêu chí nghiệm thu thực tế.

---

## Nền tảng bắt buộc

### F00-A. Đăng nhập, quản lý phiên, vai trò và thông báo
- **Nội dung thực hiện:** Cung cấp cơ chế đăng nhập bằng tài khoản, kiểm soát thời hạn phiên làm việc, chuông thông báo sự kiện mới kèm thao tác đánh dấu đã đọc và kiểm tra phân quyền tại máy chủ cho hai vai trò chính là Chủ quán và Nhân viên. Đối với nhân viên, hệ thống phân tách rõ quyền tra cứu khi đăng nhập từ xa với quyền thao tác nghiệp vụ ca sau khi đã mở phiên Vào ca bằng QR/PIN tại quầy. Khi nhân viên thực hiện giao ca, nhập hàng hoặc báo kho vào ngày không có tên trong lịch phân công, hệ thống mặc định vẫn cho lưu và gắn cờ "Ngoài lịch phân công" (trừ khi Chủ quán bật chế độ chặn cứng trong Cài đặt).
- **Căn cứ hình thành:** Các nghiệp vụ giao ca (R03), nhập hàng (R04) và đổi ca (R06) đều bắt buộc phải định danh chính xác nhân sự thực hiện (G07, G16, G17, VG03, CĐ-GV).
- **Hệ quả nếu thiếu vắng:** Không thể xác định trách nhiệm khi bàn giao ca, không biết ai đã tạo phiếu nhập hàng và không bảo mật được bảng lương cũng như báo cáo Lãi/Lỗ của Chủ quán.
- **Tiêu chí nghiệm thu:** Truy cập API khi chưa đăng nhập sẽ bị từ chối với mã lỗi 401. Tài khoản Nhân viên gọi các API quản trị của Chủ quán sẽ bị chặn với mã lỗi 403. Các thao tác ngoài lịch phân công được gắn nhãn cảnh báo chính xác.

---

## R01. Quản lý và tích hợp doanh thu POS365

### F01-A. Đồng bộ hóa đơn tự động qua API POS365
- **Nội dung thực hiện:** Kết nối tới endpoint `/api/orders?format=json` của POS365 theo cơ chế phân trang, dừng quét sớm khi gặp hóa đơn cũ hơn mốc ngày quy định và tự động đăng nhập lại nếu phiên hết hạn. Hệ thống ánh xạ mã chứng từ, thời gian tạo, tổng tiền, chiết khấu và thực thu vào bảng `pos_orders`.
- **Căn cứ hình thành:** Giải quyết khoảng trống G01 theo tài liệu đặc tả API POS365 (Mục 1, 2, 5.1) và xác nhận VG01 của Chủ quán.
- **Hệ quả nếu thiếu vắng:** Chủ quán phải tiếp tục đọc từng tờ giấy in báo cáo cuối ngày để gõ tay doanh thu vào bảng tính Excel vào cuối tháng (QT3b-K).
- **Tiêu chí nghiệm thu:** Đồng bộ chính xác toàn bộ hóa đơn hợp lệ từ dịch vụ POS365, tự động dừng khi chạm mốc ngày cấu hình mà không gây treo kết nối.

### F01-B. Nạp tệp bảng tính "Chi tiết doanh thu" (.xlsx và .csv)
- **Nội dung thực hiện:** Tiếp nhận tệp xuất từ trang quản trị POS365, tự động nhận diện dòng tiêu đề gồm 8 cột chuẩn, loại bỏ khối tiêu đề phụ ở đầu tệp và đối soát tổng số đơn cũng như tổng tiền thanh toán.
- **Căn cứ hình thành:** Đóng vai trò là phương án dự phòng chính thức khi kết nối mạng hoặc API POS365 gặp sự cố (QS02, IMG-QS02, R01).
- **Hệ quả nếu thiếu vắng:** Hệ thống bị phụ thuộc hoàn toàn vào kết nối API trực tuyến.
- **Tiêu chí nghiệm thu:** Nạp thành công tệp mẫu đúng cấu trúc 8 cột của POS365. Nếu tệp tải lên bị thiếu cột bắt buộc, hệ thống từ chối nạp và thông báo rõ tên cột bị thiếu.

### F01-C. Chống nhân đôi dữ liệu theo mã chứng từ
- **Nội dung thực hiện:** Ràng buộc tính duy nhất của trường mã chứng từ (`doc_code`). Khi người dùng nạp lại cùng một tệp hoặc chạy đồng bộ API chồng lên khoảng thời gian đã nạp tệp trước đó, hệ thống không tạo bản ghi trùng lặp mà chỉ cập nhật nếu có thay đổi và ghi nhận số dòng trùng vào nhật ký.
- **Căn cứ hình thành:** Giải quyết khoảng trống G03 khi hệ thống hỗ trợ đồng thời hai đường nạp dữ liệu doanh thu.
- **Hệ quả nếu thiếu vắng:** Doanh thu tháng bị cộng trùng dẫn đến báo cáo Lãi/Lỗ cuối tháng bị sai lệch.
- **Tiêu chí nghiệm thu:** Thực hiện nạp cùng một tệp dữ liệu 2 lần liên tiếp hoặc chạy đồng bộ API ngay sau khi nạp tệp thì tổng số hóa đơn và tổng doanh thu trong tháng vẫn giữ nguyên chính xác.

### F01-D. Làm sạch dòng tổng, đơn hủy và chuẩn hóa múi giờ GMT+7
- **Nội dung thực hiện:** Tự động loại bỏ các dòng tổng cộng (`Id = -1` hoặc `Code = "Σ"`) và các đơn hàng đã hủy (chỉ nhận đơn có `Status = 2`), đồng thời chuyển đổi thời gian `PurchaseDate` từ múi giờ UTC sang múi giờ Việt Nam (GMT+7) để gán đúng ngày kinh doanh.
- **Căn cứ hình thành:** Giải quyết khoảng trống G04. Quán mở cửa lúc 06:30 sáng giờ Việt Nam (tức 23:30 UTC ngày hôm trước), nếu giữ nguyên ngày UTC sẽ làm các đơn hàng đầu ca sáng bị đẩy lùi về ngày hôm trước (CQ09).
- **Hệ quả nếu thiếu vắng:** Báo cáo doanh thu theo ngày bị lệch số đơn và sai tổng tiền.
- **Tiêu chí nghiệm thu:** Các hóa đơn phát sinh từ 06:30 sáng giờ Việt Nam được xếp đúng vào ngày kinh doanh hiện tại, các dòng tổng cộng trong tệp xuất không bị tính gộp thành hóa đơn bán hàng.

### F01-E. Báo cáo tổng hợp doanh thu theo ngày và tháng
- **Nội dung thực hiện:** Hiển thị biểu đồ trực quan, các chỉ số tổng hợp và bảng doanh thu chi tiết của từng ngày trong tháng kèm tính năng lọc xem danh sách hóa đơn của ngày đó.
- **Căn cứ hình thành:** Giải quyết khoảng trống G02 theo yêu cầu R01 và QT3b-K.
- **Hệ quả nếu thiếu vắng:** Chủ quán vẫn phải tự cộng tay doanh thu của 30 ngày trong tháng.
- **Tiêu chí nghiệm thu:** Tổng doanh thu tháng bằng đúng tổng doanh thu của các ngày trong tháng và bằng tổng cột `paid` của các hóa đơn hợp lệ.

### F01-F. Nhật ký đồng bộ và nạp tệp doanh thu
- **Nội dung thực hiện:** Ghi nhận chi tiết thời điểm thực hiện, người thao tác, nguồn dữ liệu, số dòng đã đọc, số đơn thêm mới, số đơn trùng lặp và thông báo lỗi (nếu có) sau mỗi lần đồng bộ hoặc tải tệp.
- **Căn cứ hình thành:** Giải quyết khoảng trống G05 nhằm đảm bảo tính minh bạch khi đối soát dữ liệu tích hợp.
- **Hệ quả nếu thiếu vắng:** Không thể kiểm tra nguyên nhân khi có sự chênh lệch số lượng đơn hàng giữa các lần nạp.
- **Tiêu chí nghiệm thu:** Mỗi lượt bấm đồng bộ hoặc nạp tệp đều sinh ra một dòng nhật ký đầy đủ thông số đối soát trên giao diện.

---

## R03. Quản lý chốt ca và bàn giao ca

### F03-A. Lập biên bản giao ca điện tử
- **Nội dung thực hiện:** Nhân viên đứng ca nhập ngày làm việc, ca làm việc, doanh thu hệ thống của ca (có nút tự động lấy số tham chiếu từ POS365), tổng tiền chuyển khoản, các khoản thiếu hoặc trả khách, khoản phát sinh, tiền mặt thực tế kiểm đếm bàn giao và ghi chú giải trình. Hệ thống không tự động áp đặt công thức tính tiền két cố định.
- **Căn cứ hình thành:** Giải quyết các khoảng trống G07, G08, G09 dựa trên cấu trúc biên bản giấy 7 mục tại quán (QT1-B1 Bảng H, VG03, D01).
- **Hệ quả nếu thiếu vắng:** Nhân viên tiếp tục phải viết giấy tay và chụp ảnh gửi qua Zalo, gây thất lạc thông tin khi cần tra cứu lại các ca có chênh lệch.
- **Tiêu chí nghiệm thu:** Lưu đầy đủ các trường thông tin biên bản. Khi doanh thu nhân viên nhập lệch trên 10% so với doanh thu POS tham chiếu hoặc có khoản phát sinh, hệ thống bắt buộc phải nhập lý do giải trình mới cho phép ký giao ca.

### F03-B. Xác nhận nhận bàn giao ca và mở khóa chỉnh sửa
- **Nội dung thực hiện:** Nhân viên ca trước ký gửi biên bản, nhân viên ca tiếp theo (hoặc Chủ quán) kiểm tra tiền mặt thực tế và bấm xác nhận tiếp quản ca (hoặc đánh dấu yêu cầu xem lại). Sau khi đã xác nhận, biên bản bị khóa chỉnh sửa và chỉ Chủ quán mới có quyền mở khóa khi cần sửa sai sót.
- **Căn cứ hình thành:** Phản ánh đúng quy trình hai bên ký tên xác nhận trên sổ bàn giao của quán (NV05, QT1-B1 bước 5, VG03).
- **Hệ quả nếu thiếu vắng:** Không xác định được thời điểm và trách nhiệm chuyển giao tiền mặt giữa hai ca.
- **Tiêu chí nghiệm thu:** Người lập biên bản không thể tự bấm xác nhận nhận ca của chính mình. Trạng thái biên bản chuyển đổi tuần tự từ Nháp sang Chờ nhận và Đã xác nhận.

### F03-C. Tra cứu và lọc lịch sử biên bản giao ca
- **Nội dung thực hiện:** Cho phép Chủ quán lọc danh sách biên bản theo khoảng ngày, theo ca làm việc, theo trạng thái xác nhận và nhận diện nhanh các biên bản có cảnh báo lệch trên 10%.
- **Căn cứ hình thành:** Khắc phục sự cố thực tế ngày 02/11/2026 tại quán khi phát hiện lệch tiền nhưng không thể tra cứu lại biên bản cũ (CQ02, NV01).
- **Hệ quả nếu thiếu vắng:** Mất nhiều thời gian tìm kiếm lại tin nhắn và hình ảnh cũ trong nhóm chat.
- **Tiêu chí nghiệm thu:** Bộ lọc trả về chính xác danh sách biên bản theo điều kiện tìm kiếm và hiển thị đầy đủ chi tiết chữ ký thời gian của cả người giao lẫn người nhận.

---

## R04. Quản lý nhập hàng và chi phí nguyên liệu

### F04-A. Ghi nhận phiếu nhập hàng theo từng lần phát sinh
- **Nội dung thực hiện:** Nhân viên nhận hàng hoặc Chủ quán ghi nhận ngay từng đợt hàng về gồm ngày nhập, nhà cung cấp, loại chứng từ (hóa đơn, biên lai viết tay hoặc không chứng từ), danh sách mặt hàng (tên nguyên liệu, số lượng, đơn vị, đơn giá, thành tiền) và chiết khấu.
- **Căn cứ hình thành:** Giải quyết khoảng trống G10, G11 và đáp ứng trực tiếp yêu cầu của Chủ quán tại CQ04 ("Mua lần nào nhập vào lần đó luôn, không nhập tổng") cũng như VG04.
- **Hệ quả nếu thiếu vắng:** Hóa đơn giấy bị dồn lại đến cuối tháng mới cộng thủ công, dễ thất lạc các khoản mua lẻ không có hóa đơn như nước đá, nước đóng bình hoặc mua gấp ngoài chợ.
- **Tiêu chí nghiệm thu:** Hệ thống tự động tính chính xác thành tiền từng dòng và tổng thanh toán của phiếu nhập, hỗ trợ lưu cả các khoản mua lẻ không có chứng từ.

### F04-B. Đính kèm hình ảnh hóa đơn và biên lai nhận hàng
- **Nội dung thực hiện:** Cho phép tải lên một hoặc nhiều ảnh chụp hóa đơn, biên lai giấy gắn trực tiếp vào phiếu nhập hàng tương ứng, kiểm tra định dạng ảnh và cảnh báo nếu tải lên bức ảnh đã từng được sử dụng ở phiếu khác.
- **Căn cứ hình thành:** Số hóa và gắn kết thao tác chụp ảnh báo cáo nhận hàng trên Zalo hiện tại của nhân viên (QT2-B1 C.2.6, D12) vào thẳng bản ghi chi phí.
- **Hệ quả nếu thiếu vắng:** Hình ảnh chứng từ nằm rời rạc trên điện thoại cá nhân hoặc trôi mất trên Zalo, không thể đối chiếu ngay khi kiểm tra phiếu nhập.
- **Tiêu chí nghiệm thu:** Tệp tải lên đúng định dạng ảnh được hiển thị trực tiếp trong cửa sổ chi tiết phiếu nhập của Chủ quán.

### F04-C. Tổng hợp lịch sử nhập hàng và chi phí nguyên liệu tháng
- **Nội dung thực hiện:** Tự động cộng tổng giá trị các phiếu nhập hàng phát sinh trong tháng để hiển thị trên thẻ chỉ số quản trị và kết chuyển trực tiếp sang dòng Chi phí nguyên liệu của Báo cáo Lãi/Lỗ tháng (F07-B).
- **Căn cứ hình thành:** Giải quyết khoảng trống G12 và yêu cầu R04.
- **Hệ quả nếu thiếu vắng:** Chủ quán vẫn phải tự cộng tay từng tờ hóa đơn nguyên liệu vào cuối tháng.
- **Tiêu chí nghiệm thu:** Tổng chi phí nguyên liệu tháng luôn khớp tuyệt đối với tổng tiền các phiếu nhập hàng trong tháng đó sau mọi thao tác thêm, sửa hoặc xóa phiếu.

---

## R09. Theo dõi danh mục và tình trạng nguyên liệu

### F09-A. Quản lý danh mục nguyên liệu và tự động cập nhật giá nhập gần nhất
- **Nội dung thực hiện:** Lưu trữ danh mục tên nguyên liệu, đơn vị tính chuẩn và tự động trích xuất đơn giá cùng ngày nhập từ phiếu nhập hàng mới nhất của nguyên liệu đó để hiển thị cho Chủ quán.
- **Căn cứ hình thành:** Chuẩn hóa tên gọi nguyên liệu dùng chung cho cả phân hệ Nhập hàng và Báo kho, đồng thời giúp Chủ quán theo dõi biến động giá mua (NC-03 C3, D03).
- **Hệ quả nếu thiếu vắng:** Nhân viên gõ tên nguyên liệu tự do gây trùng lặp danh mục và Chủ quán không nắm được mức giá mua gần nhất.
- **Tiêu chí nghiệm thu:** Hệ thống ngăn chặn tạo trùng tên nguyên liệu và cập nhật tức thì cột "Giá nhập gần nhất" ngay khi có phiếu nhập hàng mới được lưu.

### F09-B. Báo cáo tình trạng nguyên liệu (Đủ / Sắp hết / Hết)
- **Nội dung thực hiện:** Nhân viên kiểm tra quầy pha chế và gửi báo cáo trạng thái nguyên liệu (`Sắp hết`, `Hết hẳn` hoặc `Đã đủ`) kèm ghi chú số lượng ước lượng còn lại.
- **Căn cứ hình thành:** Giải quyết khoảng trống G13 dựa trên quy trình nhân viên rà soát nguyên liệu còn đủ dùng khoảng 2 ngày thì báo cho Chủ quán (NC-03 C1, C9, NV09, VG09).
- **Hệ quả nếu thiếu vắng:** Tin nhắn báo hết hàng bị trôi trên nhóm chat dẫn đến tình trạng đứt gãy nguyên liệu giữa ca bán hàng (như sự cố hết sữa tươi ngày 30/10).
- **Tiêu chí nghiệm thu:** Lưu chính xác người báo, thời gian báo và cập nhật trạng thái hiện hành của nguyên liệu trên toàn hệ thống.

### F09-C. Bảng theo dõi tiến độ đặt hàng nguyên liệu cho Chủ quán
- **Nội dung thực hiện:** Phân tách rõ 3 bảng quản lý cho Chủ quán gồm: Danh mục cần đặt hàng ngay (đang sắp hết hoặc đã hết), Danh mục đã đặt đang chờ giao về quán, và Toàn bộ danh mục nguyên liệu. Đồng thời hiển thị danh sách rút gọn ngay trên trang Tổng quan.
- **Căn cứ hình thành:** Giúp Chủ quán kiểm soát tập trung toàn bộ chu trình từ lúc nhân viên báo thiếu đến lúc gọi nhà cung cấp và nhận đủ hàng (CQ11).
- **Hệ quả nếu thiếu vắng:** Chủ quán dễ quên mất mặt hàng nào đã gọi nhà cung cấp, mặt hàng nào chưa gọi.
- **Tiêu chí nghiệm thu:** Khi Chủ quán bấm "Đánh dấu đã đặt", nguyên liệu chuyển sang bảng chờ hàng về. Khi bấm "Đã nhận đủ" (hoặc nhân viên báo Đủ), nguyên liệu tự động rút khỏi danh sách cảnh báo cần đặt.

---

## R06. Quản lý lịch phân ca, đổi ca và tính lương tháng

### F06-A. Cấu hình khung giờ ca và đơn giá lương theo giờ
- **Nội dung thực hiện:** Cho phép Chủ quán thiết lập số giờ tính lương, giờ bắt đầu, giờ kết thúc của 3 ca (Sáng, Trưa, Tối) và hai mức đơn giá lương theo giờ (`a` cho ca sáng, `b` cho ca trưa và ca tối).
- **Căn cứ hình thành:** Phản ánh đúng công thức tính lương đặc thù của quán tại CQ05, NV06 và R06.
- **Hệ quả nếu thiếu vắng:** Đơn giá lương bị gắn cứng trong mã nguồn, khi quán điều chỉnh mức lương theo giờ sẽ không thể tự cập nhật trên giao diện.
- **Tiêu chí nghiệm thu:** Thay đổi đơn giá `a` hoặc `b` sẽ tự động tính lại bảng lương của các tháng đang mở, trong khi các tháng đã khóa sổ lương vẫn bảo toàn nguyên vẹn mức đơn giá tại thời điểm chốt.

### F06-B. Nạp tệp bảng tính lịch phân ca theo hai định dạng (Đường 1)
- **Nội dung thực hiện:** Hỗ trợ tải lên tệp lịch ca `.xlsx` hoặc `.csv` theo cả dạng lưới của quán (Ngày, Ca Sáng, Ca Trưa, Ca Tối) lẫn dạng danh sách phẳng, kèm nút tải tệp mẫu và công cụ ghép tên nhân viên nếu tên trong tệp chưa khớp với hồ sơ nhân sự.
- **Căn cứ hình thành:** Giải quyết khoảng trống G15, đảm bảo tính tương thích với thói quen lập lịch trên bảng tính rồi gửi qua Zalo của Chủ quán (QT3a-B1, D28).
- **Hệ quả nếu thiếu vắng:** Chủ quán buộc phải tích chọn thủ công từng ô lịch cho cả tháng ngay cả khi đã có sẵn tệp bảng tính bên ngoài.
- **Tiêu chí nghiệm thu:** Nạp đúng số lượng ca làm việc từ tệp mẫu, không gây nhân đôi ca khi nạp lại cùng một tháng.

### F06-C, F06-D, F06-E. Khai báo lịch rảnh, xếp lịch và công bố thời khóa biểu (Đường 2)
- **Nội dung thực hiện:** Nhân viên tích chọn các ca có thể đi làm trong tháng. Chủ quán xem tổng hợp, sử dụng tính năng gợi ý lịch nháp (E-13) hoặc xếp tay từng ô, sau đó bấm "Công bố lịch" để toàn bộ nhân viên xem lịch chính thức trên điện thoại hoặc máy tính.
- **Căn cứ hình thành:** Giải quyết khoảng trống G16 theo định hướng tối ưu hóa quy trình tự động của Giảng viên hướng dẫn (CĐ-GV) và hiện trạng nhân viên gửi lịch rảnh ngày 25 hằng tháng (NC-01 C2).
- **Hệ quả nếu thiếu vắng:** Chủ quán vẫn phải gom từng tin nhắn đăng ký lịch rảnh rời rạc của từng nhân viên trên Zalo cá nhân.
- **Tiêu chí nghiệm thu:** Trước khi công bố, bản nháp chỉ hiển thị với Chủ quán. Sau khi công bố, nhân viên xem được toàn bộ lịch và thấy nổi bật các ca của chính mình.

### F06-F. Gửi và phê duyệt yêu cầu đổi ca hoặc nhờ phụ giữa ca
- **Nội dung thực hiện:** Hỗ trợ hai hình thức: (1) Đổi nguyên ca (`full_swap`): khi Chủ quán bấm duyệt, hệ thống tự động hoán đổi người đứng ca trong lịch chính thức và cập nhật ngay số công tính lương; (2) Nhờ làm phụ giữa ca (`partial_cover`): khi Chủ quán duyệt, hệ thống giữ nguyên lịch phân công gốc và tạo ghi chú nhắc Chủ quán trên màn hình bảng lương tháng.
- **Căn cứ hình thành:** Giải quyết khoảng trống G17 dựa trên thực tế nhân viên đổi ca hoặc nhờ nhau đứng phụ vài tiếng khi bận việc đột xuất (NC-01 C2, CQ05, CĐ-GV, D15).
- **Hệ quả nếu thiếu vắng:** Cuối tháng Chủ quán phải nhắn hỏi lại từng nhân viên xem trong tháng có ai đổi ca cho ai không để tính lại tiền lương.
- **Tiêu chí nghiệm thu:** Duyệt đơn đổi nguyên ca cập nhật tức thì bảng lịch và bảng lương trong cùng một giao dịch cơ sở dữ liệu. Duyệt đơn nhờ phụ giữa ca hiển thị đúng thẻ ghi chú điều chỉnh ở cuối trang Lương tháng.

### F06-G. Tổng hợp giờ công, tính lương tự động và chốt bảng lương tháng
- **Nội dung thực hiện:** Tự động đếm tổng số ca sáng, ca trưa, ca tối của từng nhân viên trong tháng từ lịch đã công bố (bao gồm cả các ca đã đổi hợp lệ) để tính thành tiền theo công thức: `Lương = (a × 5,5 × số ca sáng) + (b × 5,5 × số ca trưa) + (b × 4,0 × số ca tối)`. Hỗ trợ Chủ quán khóa bảng lương cuối tháng và kết chuyển tổng quỹ lương sang Báo cáo Lãi/Lỗ.
- **Căn cứ hình thành:** Giải quyết khoảng trống G18 theo đúng công thức của quán tại CQ05, NV06 và xác nhận VG06.
- **Hệ quả nếu thiếu vắng:** Nhân viên và Chủ quán phải tự đếm số ca và bấm máy tính tay vào cuối tháng, dễ xảy ra nhầm lẫn.
- **Tiêu chí nghiệm thu:** Kết quả tính lương khớp tuyệt đối với công thức toán học, nhân viên chỉ xem được dòng lương của chính mình trong khi Chủ quán xem và khóa được toàn bộ bảng lương của quán.

---

## R07. Quản lý chi phí vận hành và Báo cáo Lãi/Lỗ tháng

### F07-A. Sổ ghi nhận chi phí cố định và chi phí phát sinh
- **Nội dung thực hiện:** Cho phép Chủ quán ghi nhận, chỉnh sửa và xóa các khoản chi phí cố định (mặt bằng, điện, nước, internet) và chi phí phát sinh trong tháng.
- **Căn cứ hình thành:** Giải quyết khoảng trống G21 dựa trên cấu trúc tệp Excel 4 nhóm chi phí hiện tại của Chủ quán (QT3b-K bước 4, CQ04, VG07).
- **Hệ quả nếu thiếu vắng:** Hệ thống thiếu mất 2 trong 4 cấu phần chi phí nên không thể lập được báo cáo Lãi/Lỗ hoàn chỉnh.
- **Tiêu chí nghiệm thu:** Phân loại và cộng tổng chính xác từng nhóm chi phí cố định và phát sinh theo đúng tháng được chọn.

### F07-B. Báo cáo Lãi/Lỗ tháng tự động hợp nhất 7 dòng chuẩn
- **Nội dung thực hiện:** Tự động hợp nhất số liệu từ 4 nguồn độc lập để hiển thị bảng báo cáo tài chính 7 dòng gồm: (1) Doanh thu POS, (2) Chi phí nguyên liệu, (3) Chi phí nhân công, (4) Chi phí cố định, (5) Chi phí phát sinh, (6) Tổng chi phí và (7) Lợi nhuận thuần. Đối với tháng hiện tại đang diễn ra, hệ thống hỗ trợ tính toán tạm tính phân bổ theo số ngày thực tế đã qua.
- **Căn cứ hình thành:** Giải quyết khoảng trống G20, giúp Chủ quán loại bỏ quy trình 6 bước gom dữ liệu thủ công mất khoảng 60 phút mỗi cuối tháng (QT3b-K, CQ08, VG07).
- **Hệ quả nếu thiếu vắng:** Các nguồn dữ liệu vẫn nằm tách biệt, không tự động ra được kết quả kinh doanh cuối cùng của cửa hàng.
- **Tiêu chí nghiệm thu:** Con số trên cả 7 dòng khớp tuyệt đối với dữ liệu gốc tại các màn hình Doanh thu, Nhập hàng, Lương tháng và Sổ chi phí.

### F07-C. Bảng đối chiếu tự động với số liệu tính thủ công (Excel)
- **Nội dung thực hiện:** Cung cấp cửa sổ cho phép Chủ quán nhập các con số tự tính trên bảng Excel cá nhân theo từng khoản mục để hệ thống tự động so sánh và hiển thị mức chênh lệch (hoặc xác nhận "Khớp").
- **Căn cứ hình thành:** Giải quyết khoảng trống G23, đóng vai trò là công cụ kiểm chứng độ chính xác khi chuyển đổi từ phương pháp quản lý thủ công sang hệ thống phần mềm tập trung.
- **Hệ quả nếu thiếu vắng:** Chủ quán khó kiểm tra nhanh xem số liệu tự động của phần mềm đã khớp với sổ sách tay hiện tại ở khoản mục nào.
- **Tiêu chí nghiệm thu:** Tính toán và hiển thị chính xác mức chênh lệch (`Số hệ thống - Số tính tay`) cho cả 5 khoản mục doanh thu và chi phí.