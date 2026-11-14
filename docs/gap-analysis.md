# Phân tích khoảng trống (GAP) – T06 Cửa hàng A

Môn MAIS03010 – Nhóm 08 – IM2402. Phạm vi bản Demo v1 và Live: R01, R03, R04, R06, R07, R09. Đã loại theo xác nhận chủ quán (VG02, VG05, VG08): R02, R05, R08.

## 0. Quy ước

**Mã căn cứ** (chỉ dùng mã có trong bộ tài liệu đầu vào):

| Mã | Nguồn |
|---|---|
| NC-01/02/03 + Cx | Phỏng vấn chủ quán / thu ngân / pha chế-nhận hàng, câu số x |
| QT1-B1, QT2-B1, QT3a-B1, QT3b-K + mục | Biên bản quan sát (mục C.x.y, bước n, Bảng D–H) |
| VII.1, VII.2.A, M11–M17 | Tổng hợp cuối Observation_Notes.md (bản đồ nguồn dữ liệu, đối chiếu lời kể/quan sát, điểm mâu thuẫn) |
| CQ01–CQ11, NV01–NV09 | Câu hỏi bổ sung (follow-up-qa.md) |
| QS01–QS04 | Kiểm tra trực tiếp trên POS365 ngày 07/11/2026 |
| VG01–VG09 | Phản hồi Validation Gate của chủ quán ngày 07/11/2026 |
| R01–R09 | Phụ lục B (requirements-list.md) |
| API §n | "API Specification Doc (www.pos365.vn) v1.0", mục n |
| IMG-QS02 | Ảnh `pos365-qs02-export-columns.png` (file xuất đã che) |
| CĐ-GV | "Chỉ đạo tối ưu hóa tự động hóa từ Giảng viên hướng dẫn" (do nhóm nêu trong yêu cầu; chưa có văn bản kèm theo, xem D04) |

**Loại bằng chứng** theo quy ước của nhóm: T = thấy trực tiếp, N = nghe kể, S = suy luận (không dùng làm căn cứ, chỉ nêu để kiểm chứng).

**Mã quyết định D01–D28**: các điểm "chưa có căn cứ trong tài liệu" cần nhóm quyết, liệt kê ở Phụ lục cuối file.

## 1. Bảng GAP chính

| # | Hiện trạng (AS-IS) | Vấn đề / ốc đảo dữ liệu | Khoảng trống (GAP) | R | Chức năng đề xuất (TO-BE) | Căn cứ |
|---|---|---|---|---|---|---|
| G01 | POS365 ghi từng đơn; cuối ngày nhân viên in báo cáo ra giấy, không xuất file | Doanh thu nằm trên giấy in; POS có nút xuất nhưng quán không dùng | Không có đường đưa dữ liệu doanh thu POS vào hệ thống tổng hợp | R01 | F01-A đồng bộ API POS365; F01-B nạp file "Chi tiết doanh thu" | NC-01 C5: "Quán không xuất dữ liệu ra Excel/CSV, thường in ra giấy"; QT1-B1 C.1.10–1.11 (T); CQ06 (N); QS02 (T: xuất được 8 cột); API §5.1 |
| G02 | Cuối tháng chủ quán nhìn giấy in/biên bản rồi gõ lại doanh thu từng ngày vào Excel | Chép lại lần 2 | Chưa có tổng hợp doanh thu theo ngày/tháng tự động | R01 | F01-E doanh thu theo ngày/tháng | QT3b-K C.3b.4 (N); VII.1 dòng "Doanh thu" (chép lại lần 2); VG01 "1 cần" |
| G03 | Dữ liệu POS có thể đi vào hệ thống bằng hai đường, dễ trùng | Cùng một hóa đơn có thể vào từ API rồi lại vào từ file | Chưa có khóa chống nhân đôi | R01 | F01-C chống trùng theo mã chứng từ (`doc_code`) | API §5.1 (trường `Code`); QS02 (cột "Mã chứng từ"); yêu cầu kỹ thuật của nhóm |
| G04 | Báo cáo/file xuất của POS có dòng tổng và (theo nhóm kiểm chứng) có đơn hủy | Cộng thẳng sẽ lệch số đơn và doanh thu | Chưa có bước làm sạch dữ liệu POS | R01 | F01-D lọc dòng tổng, đơn hủy; đổi UTC → GMT+7 | IMG-QS02 (dải tổng ngay dưới tiêu đề và cuối bảng; khối "Số đơn hàng/Tổng thanh toán" ở đầu file); QT1-B1 Bảng F (dòng "Hóa đơn hủy/Trả hàng"); API §5.1 (`PurchaseDate` có hậu tố Z); dòng `Id = -1`/`Σ`: theo nhóm kiểm chứng, **không có trong PDF** (D08) |
| G05 | Không ai ghi lại lần đồng bộ/nhập nên không biết số liệu lấy lúc nào, từ đâu | Khó đối soát khi số lệch | Thiếu nhật ký nạp dữ liệu | R01 | F01-F nhật ký đồng bộ/nhập (có đối soát `__count`, khối tổng của file) | API §2 (`__count`); IMG-QS02 (khối tổng đầu file). **Căn cứ kỹ thuật, không phải nhu cầu nêu bởi chủ quán** |
| G06 | POS không phân biệt tiền mặt/chuyển khoản khi bán; báo cáo ghi toàn bộ là tiền mặt | Phải đối chiếu qua ảnh bill trên điện thoại | Hệ thống **không** giải quyết (chủ quán bác R02) | (R02 loại) | Không xây. Chuyển khoản chỉ ghi ở biên bản giao ca (F03-A) | NC-02 C1 (N); QT1-B1 Bảng F (T); QS02 (T: file không có cột phương thức); QS04 (T: màn hình có chọn chuyển khoản); M13 (còn mở); VG02 "2 không cần" |
| G07 | Giao ca/kết ca bằng biên bản giấy 7 mục + chụp ảnh gửi Zalo | Chép tay 2 lần (doanh thu POS, tổng chuyển khoản); 4 nơi chứa số liệu | Chưa có biên bản điện tử, chưa có xác nhận bàn giao trên hệ thống | R03 | F03-A biên bản giao ca; F03-B xác nhận bàn giao | QT1-B1 bước 1–5, Bảng H (T: 5 bước, 2 lần chép, 4 nơi); NC-02 C4 (N); NV03, NV05 (N); VG03 "3 cần" |
| G08 | Có lần két thiếu; ca sau phát hiện hoặc người kết ca tự đếm lại; bù bằng quỹ chung hoặc tự bù | Chênh lệch và lý do không được ghi ở đâu có cấu trúc | Chưa có chỗ ghi khoản thiếu/trả, phát sinh, lý do | R03 | F03-A (các cột Thiếu/trả, Phát sinh, ghi chú), **không tự tính công thức tiền két** | CQ02, NV01, NV05 (N, 02/11/2026); NC-02 C4 (N); M15; R03 ("không tự động tính công thức cứng"); VG02 |
| G09 | Doanh thu "theo ca" không có sẵn trên POS (báo cáo theo ngày; POS không có thao tác đóng ca) | Không biết cách tách doanh thu từng ca | Chưa rõ căn cứ để điền sẵn "Doanh thu hệ thống" theo ca | R03 | F03-A: nhân viên nhập số "Hệ thống"; hệ thống chỉ hiển thị tổng ngày từ R01 để tham chiếu | QT1-B1 C.1.6 (KX), Bảng F (T: "Doanh thu theo nhân viên / theo ca: Không"); M12; NV03 (N, chưa trả lời phần tách ca); D05 |
| G10 | Hàng về: nhân viên đếm, đối chiếu hóa đơn/biên lai, chụp ảnh báo Zalo, cất chứng từ giấy | Số lượng, đơn giá chỉ nằm trên giấy và ảnh Zalo; không vào POS/sổ/bảng tính | Chưa có sổ nhập hàng theo từng lần | R04 | F04-A ghi từng lần nhập; F04-C lịch sử và tổng chi phí nguyên liệu | QT2-B1 C.2.4–2.11 (T), Bảng F (T: 10/11 trường có), Bảng H (T: 2 nơi, 30 phút); CQ04 "Mua lần nào nhập vào lần đó luôn, không nhập tổng"; VG04 "4 cần" |
| G11 | Có hàng không hóa đơn (nước thùng) và mua lẻ ở tạp hóa khi hết hàng | Không có chứng từ chuẩn; chỉ nhắn Zalo | Chưa có cách ghi nhận khoản nhập không hóa đơn | R04 | F04-A có trường "loại chứng từ" (hóa đơn / biên lai viết tay / không chứng từ) | CQ03, NV07, NV09, CQ11 (N); QT2-B1 C.2.7 (T: hóa đơn và biên lai viết tay); R04 ("hàng có hóa đơn, nước thùng không có hóa đơn và các khoản mua lẻ") |
| G12 | Cuối tháng chủ quán gom hóa đơn giấy để cộng tay chi phí nguyên liệu | Cộng tay | Chi phí nguyên liệu tháng chưa tự cộng | R04, R07 | F04-C tổng theo tháng, đưa vào F07-B | QT3b-K C.3b.5 (N); M11 (hai lời kể chưa khớp, D11) |
| G13 | Báo thiếu nguyên liệu bằng nhắn nhóm Zalo; chủ quán xem rồi đặt; có lần hết giữa ca (30/10 sữa tươi) | Thông tin báo rời rạc, hết hàng chỉ biết khi pha | Chưa có chỗ ghi tình trạng nguyên liệu để chủ quán theo dõi | R09 | F09-A danh mục nguyên liệu; F09-B báo sắp hết/hết; F09-C bảng theo dõi | NC-03 C1, C9 (N); NV09, CQ11 (N); NC-01 C6 (N); VG09 "9 cần"; R09 ("không tự động tính tồn kho theo định mức") |
| G14 | Tồn kho/hao hụt/hàng hủy không ghi ở đâu; POS: Giá vốn = 0, tồn kho 0 hoặc âm | Không có dữ liệu tồn kho đáng tin | **Không** lấp bằng ước tính tồn kho (chủ quán bác R05 vì số lệch gây hiểu nhầm) | (R05 loại) | Không xây tồn kho ước tính trong lõi (xem D03) | QS03 (T); NV08 (N: điều chỉnh định lượng không ghi); NC-03 C6 (N); VG05 |
| G15 | Nhân viên gửi lịch rảnh cho chủ quán qua Zalo cá nhân ngày 25; chủ quán tổng hợp, xếp, gửi Zalo nhóm để chốt; lịch gốc là file bảng tính | Lịch nằm trên Zalo/bảng tính; không có chỗ xem thống nhất | Chưa có nơi xem thời khóa biểu chính thức; chưa có đường nạp lịch từ Zalo | R06 | **Đường 1**: F06-B nạp file Excel/CSV lịch ca, F06-E xem thời khóa biểu | NC-01 C1, C2 (N); NC-02 C7 (N); QT3a-B1 C.3a.1 (T: thấy file bảng tính lịch trong Zalo nhóm); VG06 |
| G16 | Bước nhân viên gửi lịch rảnh và nhận lịch cuối cùng đều qua tin nhắn | Hiện đã có bước "khai báo lịch rảnh" nhưng bằng tin nhắn riêng | Chưa số hóa khai báo lịch rảnh → xếp lịch → công bố | R06 | **Đường 2**: F06-C khai báo lịch rảnh; F06-D chủ quán xếp/duyệt/công bố (xếp thủ công, không có thuật toán xếp tự động) | Căn cứ nền: NC-01 C2, NC-02 C7 (N). Căn cứ chức năng: **CĐ-GV**. Lưu ý: Phụ lục B mục 2 ghi "Xếp ca tự động" không đưa thành requirement (NC-01 C1) |
| G17 | Đổi ca: nhân viên tự nhắn nhau, tự nhớ, cuối tháng báo chủ quán; xin đi trễ phải báo chủ trước | Chủ quán chỉ biết khi cuối tháng; không có bản ghi | Chưa có yêu cầu đổi ca có người duyệt và lưu vết | R06 | F06-F yêu cầu đổi ca → chủ quán duyệt → cập nhật CSDL ngay | QT3a-B1 C.3a.3 (N), G3; NC-01 C2 (N); CQ05 (N: "cuối tháng anh sẽ hỏi các bạn các ca đổi cho nhau để kiểm soát"); R06; **CĐ-GV** (đổi sang duyệt trước, D04) |
| G18 | Cuối tháng nhân viên tự tính lương theo công thức ca rồi gửi chủ quán qua Zalo cá nhân | Tính tay, dễ sót đổi ca | Chưa tự tính giờ công/lương theo ca | R06 | F06-G tính lương theo công thức a×5,5×(ca sáng) + b×5,5×(ca trưa) + b×4,0×(ca tối) | CQ05, NV06 (N); R06; VG06 "6 cần"; giá trị a, b đã che (D06) |
| G19 | Quán không ghi giờ vào/ra hằng ngày; giờ công dựa lịch | Không có dữ liệu giờ thực | **Không** xây chấm công trong lõi (chỉ "nếu được", mức Low) | R06 | Không xây trong lõi; ghi vào MỞ RỘNG (E-09) | QT3a-B1 G1 "Không ghi giờ làm vào mỗi ngày" (N), C.3a.2 (N); R06 ghi chú; VG06 |
| G20 | Lãi/lỗ cuối tháng: chủ quán mở Excel, gom 5 nguồn rời, 6 bước, khoảng 60 phút, chỉ tổng theo tháng | Không có định danh chung để nối tự động | Chưa có báo cáo lãi/lỗ tháng từ dữ liệu tập trung | R07 | F07-B báo cáo lãi/lỗ tháng | QT3b-K bước 1–6, C.3b.3–3b.11, C.3b.8 (N); VII.2.A dòng QT3; CQ08 "Tính thủ công cao, lâu, mất thời gian."; VG07 "7 cần" |
| G21 | Chi phí mặt bằng/cố định nhập tay từng khoản vào Excel cuối tháng; file Excel có 4 mục: mặt bằng, nguyên liệu, lương, chi phí phát sinh | Không có nơi ghi chi phí cố định và phát sinh trong hệ thống | Chưa có sổ chi phí khác | R07 | F07-A sổ chi phí (nhóm: cố định / phát sinh) | QT3b-K bước 4, C.3b.6 (N); CQ04 (N, Bích tóm tắt); VG07 "nếu thêm được chi phí phát sinh nữa thì tốt" |
| G22 | Chủ quán không có số liệu theo món/theo ca; quyết định dựa kinh nghiệm | — | **Không** xây báo cáo theo món/ca | (R08 loại) | Không xây | QT3b-K C.3b.8 (N); NC-01 C8 (N); CQ07 (N); VG08 "8 không cần" |
| G23 | Hệ thống thay Excel cần chứng minh được | Chưa có phép so sánh hệ thống với cách tính hiện tại | Chưa có bảng đối chiếu | R07 | F07-C bảng đối chiếu số hệ thống với số chủ quán tự tính | **Căn cứ nghiệm thu của nhóm**, không có trong tài liệu khảo sát (D13) |

## 2. Các khoảng trống cố ý không lấp

| Nội dung | Lý do | Căn cứ |
|---|---|---|
| Tự tính tiền két theo công thức (Hệ thống − CK − Thiếu + vốn đầu ngày) | Chủ quán bác (tiền lẻ thay đổi; đổi chế độ thanh toán lúc đông khách gây rối) | R02, VG02 |
| Công thức/định mức pha chế, tồn kho theo định mức | Chủ quán bác (gia giảm theo khách, số lệch dễ gây hiểu nhầm) | R05, VG05 |
| Lãi gộp/giá vốn theo món, theo ca | Chủ quán bác | R08, VG08 |
| Phân tách tiền mặt/chuyển khoản trên POS | Quán chủ động không bấm chọn khi đông khách (S của nhóm); R02 bị bác | M13, QS04, VG02 |
| Kiểm soát bill bị quên, quản lý khách hàng, bán qua app, xếp ca tự động | Chưa đủ căn cứ, nằm ngoài danh sách requirement | Phụ lục B mục 2 |

## 3. Số đo AS-IS dùng làm đường cơ sở nghiệm thu

| Chỉ số | Giá trị AS-IS | Căn cứ |
|---|---|---|
| Chốt ca cuối ngày | 5 bước, 2 lần chép lại, 4 nơi chứa số liệu; khoảng 10 phút (N) | QT1-B1 Bảng H; NC-02 C4 |
| Nhận hàng và ghi chứng từ | khoảng 30 phút; thông tin nằm ở 2 nơi (chứng từ giấy, ảnh Zalo); 0 nơi ghi sổ/POS | QT2-B1 Bảng H |
| Gom lãi/lỗ cuối tháng | 5 nguồn, 6 bước, khoảng 60 phút (ước lượng, N) | QT3b-K Bảng H; M11 lưu ý con số là ước lượng cả buổi |

Mục tiêu số cụ thể (ví dụ "dưới X phút") **chưa có trong tài liệu**; mọi tiêu chí nghiệm thu trong `function-rationale.md` được viết theo dạng so với đường cơ sở này hoặc kiểm tra được bằng test.

## Phụ lục. Các điểm chưa có căn cứ / cần nhóm quyết (D01–D28)

Mỗi mục ghi cách hệ thống sẽ xử lý **tạm thời** nếu chưa có quyết định.

| Mã | Điểm chưa có căn cứ hoặc mâu thuẫn | Xử lý tạm đề xuất |
|---|---|---|
| D01 | Yêu cầu của nhóm viết "đối chiếu doanh thu hệ thống với tiền thực nhận, ghi chênh lệch" ở R03, trong khi R02/VG02 bị bác và R03 ghi "không tự động tính công thức cứng". Tự tính chênh lệch chính là công thức R02 | Không tự tính tiền két. Chỉ lưu các số nhân viên nhập (Hệ thống, CK, Thiếu/trả, Phát sinh, Thực tế giao) + lý do. Cảnh báo chênh lệch (E-06) nếu có, chỉ dựa trên số do nhân viên nhập |
| D02 | Vai trò "Quản lý ca" và "Kế toán/Xem" không có trong hiện trạng (mỗi ca 1 người; chỉ chủ quán theo dõi số liệu). Người giao ca và nhận hàng theo R03/R04 là nhân viên đứng ca, trong khi vai trò Nhân viên theo yêu cầu chỉ xem lịch/khai báo/đổi ca | Quyền theo năng lực (RBAC); gán "giao ca, nhập hàng, báo nguyên liệu" cho tài khoản nhân viên đang đứng ca. Chủ quán quyết vai trò Quản lý ca là ai |
| D03 | R09 trong yêu cầu của nhóm gồm "tồn kho ước tính từ nhập hàng" và "cảnh báo giá tăng bất thường". R09 ghi "không tự động tính tồn kho theo định mức"; chưa có dữ liệu tiêu hao (NV08, NC-03 C6, QS03) nên tồn ước tính từ nhập hàng sẽ chỉ tăng; VG05 cảnh báo số lệch gây hiểu nhầm. Cảnh báo giá tăng chưa có căn cứ trực tiếp (chỉ NC-01 C3 nói giá nguyên liệu lên) và trùng mục f của MỞ RỘNG | Lõi R09: danh mục + đơn vị + giá nhập gần nhất (suy từ R04) + báo trạng thái đủ/sắp hết/hết. Tồn ước tính và cảnh báo giá tăng chuyển sang MỞ RỘNG (E-07, E-08) hoặc bỏ |
| D04 | CĐ-GV (R06 Đường 2) chưa có văn bản trong bộ tài liệu; chủ quán chỉ xác nhận phần tính công/lương (VG06). Hiện chủ quán chỉ được báo đổi ca cuối tháng; yêu cầu mới là duyệt trước, đổi hành vi | Xây theo CĐ-GV, gắn nhãn đúng cụm "Căn cứ: Chỉ đạo tối ưu hóa tự động hóa từ Giảng viên hướng dẫn". Đề nghị lưu bản tin nhắn/biên bản chỉ đạo vào `docs/` để có mã tham chiếu |
| D05 | Ranh giới giờ của ca sáng/trưa/tối chưa có (chỉ có độ dài 5,5/5,5/4,0 giờ; mở 06:30, đóng 21:15; nhân viên đến sớm 06:15) | Không gán đơn POS theo ca; `start/end` của ca để trống, cấu hình được |
| D06 | Giá trị a, b đã che; chưa rõ theo từng người hay chung | Cấu hình chung do chủ quán nhập; dữ liệu demo dùng số giả, ghi rõ |
| D07 | Định nghĩa "doanh thu": `TotalPayment` hay `Total`; cột "Thanh toán" của file xuất là số tiền hay phương thức (M13). Ảnh IMG-QS02 cho thấy cột này canh phải như cột số (S) | Doanh thu = Σ `paid` (TotalPayment/Thanh toán) của đơn hợp lệ; lưu `total` và `discount` để đối chiếu |
| D08 | PDF không liệt kê giá trị `Status` (chỉ có ví dụ `Status: 2`) và không nói về dòng tổng `Id = -1`/`Σ`; nhóm cho biết đã kiểm chứng thực tế | Nhận đơn `Status = 2`; loại dòng tổng và đơn hủy theo mô tả của nhóm. Lưu kết quả `tools_probe_pos365.py` (đã che) vào docs để làm căn cứ |
| D09 | PDF không nêu tham số lọc theo ngày và thứ tự mặc định của `/api/orders`; ví dụ trong PDF ghi năm 2022 (v1.0 14/06/2021) nên hành vi có thể đã đổi | Probe trước; nếu không lọc được theo ngày, đồng bộ theo trang rồi lọc phía ứng dụng |
| D10 | Múi giờ của cột "Ngày tạo" trong file xuất chưa rõ | Coi là giờ địa phương GMT+7; đối chiếu với API cùng ngày để kiểm tra |
| D11 | Điện nước thuộc mục nào trong 4 mục của Excel chủ quán (M11); VII.1 xếp điện, nước vào "Chi phí cố định khác" (N) | Xếp vào nhóm "cố định" |
| D12 | R04 không nêu đính kèm ảnh hóa đơn; chỉ có căn cứ gián tiếp (nhân viên chụp ảnh gửi Zalo, QT2-B1 C.2.6 T). Ảnh chứa tên nhà cung cấp, số tiền | Làm tính năng tùy chọn trong F04-B, ghi rõ căn cứ gián tiếp; ảnh Live không đưa vào repo |
| D13 | Bảng đối chiếu với cách tính thủ công (F07-C) là nhu cầu nghiệm thu của nhóm; chủ quán chưa xác nhận và không cung cấp được chi tiết file Excel (CQ04) | Giữ như công cụ kiểm chứng của nhóm; số tham chiếu do người dùng nhập tay |
| D14 | "Real-time sync" khi duyệt đổi ca: tài liệu không nói mức độ | Hiểu là cập nhật CSDL trong một giao dịch ngay khi duyệt + giao diện tự làm mới định kỳ; đẩy tức thời (WebSocket) để ở MỞ RỘNG |
| D15 | Mức chi tiết đổi ca: nguyên ca hay từng phần (NC-01 C2: đến trễ/về sớm nhờ nhau phụ đứng "khoảng đó") | Chỉ đổi theo nguyên ca; không tính lương theo giờ lẻ |
| D16 | Ai được xem lương: chưa có căn cứ (hiện mỗi người tự tính và gửi riêng chủ quán qua Zalo cá nhân: NC-01 C2) | Nhân viên chỉ xem lương của mình; chủ quán xem tất cả |
| D17 | MỞ RỘNG "bật/tắt được" nhưng đăng nhập và vai trò là điều kiện của R06 Đường 2 (cần biết nhân viên nào khai báo/đổi ca) và của dữ liệu thật ở Live | Phiên đăng nhập + vai trò tối thiểu là hạ tầng bắt buộc; khi `APP_MODE=live` không cho tắt |
| D18 | Thư mục hiện có không nằm trong tệp đính kèm. **Đã chốt 12/11:** nhóm cho phép dựng khung mới | Đã dựng khung mới (xem README) |
| D08 | Bảng mã `Status` của POS365: ví dụ PDF chỉ có giá trị 2 | **ĐÃ ĐÓNG (13/11/2026):** Kiểm chứng thực tế qua probe: `Status = 2` là hóa đơn hoàn tất hợp lệ. Hệ thống chỉ nhận `Status = 2`, bỏ qua các đơn hủy/chưa hoàn tất. |
| D09 | Lọc theo ngày và thứ tự trả về của POS365 | **ĐÃ ĐÓNG (13/11/2026):** API POS365 trả về theo thứ tự **mới đến cũ** (`PurchaseDate` giảm dần). Cơ chế đồng bộ cải tiến dừng quét ngay khi gặp đơn cũ hơn mốc `POS365_SYNC_FROM_DATE` và chặn ở `POS365_SYNC_MAX_PAGES`, khắc phục triệt để lỗi treo request khi kéo 15.829 đơn. |
| D19 | Mã chứng từ có tiền tố "OFFLI…" thấy trong IMG-QS02 (đơn tạo offline); chưa rõ mã có đổi khi đồng bộ, nên chống trùng theo `doc_code` có thể bỏ sót | **ĐÃ ĐÓNG (13/11/2026):** Chống trùng tuyệt đối theo `doc_code`. Hóa đơn offline khi đồng bộ lên hệ thống giữ nguyên mã chứng từ POS365 phát hành; gắn cờ cảnh báo đối soát nếu phát hiện trùng giờ + số tiền. |
| D20 | PDF §1 yêu cầu đăng nhập bằng tài khoản admin của cửa hàng; chưa rõ tài khoản quyền thấp có đủ gọi `/api/orders` không | Tài khoản/SessionId chỉ ở `.env.live`; không commit; probe thử quyền thấp nếu chủ quán cho phép |
| D21 | Chấm công vào/ra (E-09): chủ quán chỉ nói "nếu được" (VG06), R06 xếp mức Low; chưa có quy trình/thiết bị, chưa có quy tắc đi trễ/về sớm | Không xây; chờ nhóm quyết có đưa vào Demo hay không |
| D22 | Khôi phục tài khoản chủ quán khi quên mật khẩu (E-02): chưa có căn cứ về cách làm; POS từng gặp sự cố mật khẩu cuối tháng 8 (NC-01 C11) | Chưa xây; chờ quyết định |

## Kết quả duyệt Bước 1 (11/11/2026)

**Đã chốt:**

| Mã | Quyết định |
|---|---|
| D01 | R03 chỉ lưu số nhân viên nhập (Hệ thống, CK, Thiếu/trả, Phát sinh, Thực tế giao) và lý do; không tự tính |
| D02 | Quyền R03, R04, R09 gắn cho tài khoản Nhân viên đang đứng ca. Quản lý ca và Kế toán/Xem: để sau, chỉ giữ chỗ trong mô hình |
| D03 | Lõi R09: danh mục, giá nhập gần nhất (từ R04), trạng thái đủ/sắp hết/hết. Tồn kho ước tính để sau (E-08 loại) |
| D04 | R06 Đường 2 (duyệt đổi ca trước) vào **lõi**, do nhóm đề xuất phát triển trên gợi ý của giảng viên |
| D05, D06 | Khung giờ ca và a, b do chủ quán tự cấu hình trên giao diện |
| D07 | Doanh thu = `TotalPayment` |
| D15 | Hai loại yêu cầu: đổi nguyên ca (đổi lịch) và phụ giữa ca/vắng nửa ca (chỉ cờ ở F06-G, không đổi lịch/lương). Căn cứ nền của loại 2: NC-01 C2 |
| D17 | E-01 và E-02 bắt buộc, không tắt khi `APP_MODE=live` |
| — | Giữ E-01…E-05, E-11; E-09 thành chấm công QR chỉ log (lương tính theo lịch); loại E-06, E-07, E-08, E-10, E-12; thêm E-13 |

**Điểm mới phát sinh, cần nhóm xác nhận (có xử lý tạm):**

| Mã | Điểm | Xử lý tạm |
|---|---|---|
| D23 | **Đã chốt 12/11:** `duty_require_schedule` mặc định **tắt** ở cả Demo và Live; nhân viên thao tác ngày không có trong lịch vẫn lưu được, bản ghi gắn cờ "Ngoài lịch phân công" (E-04), không 403; chủ quán bật/tắt ở Cài đặt | Như đã chốt |
| D24 | E-13 (xếp lịch nháp): không phải requirement (Phụ lục B mục 2); quy tắc 3 chưa có căn cứ. **Tham số đã chốt 12/11:** `cluster_fairness_slack = 1`, `max_shifts_per_day = 2` (tránh ôm 3 ca) | MỞ RỘNG; hòa thì chọn mã nhỏ hơn; các tham số chỉnh được ở Cài đặt |
| D25 | Phụ giữa ca: chủ quán "tự cộng/trừ tay" nên hệ thống không lưu khoản điều chỉnh | Chỉ hiển thị cờ ở F06-G; không có trường tiền |
| D26 | Chấm công QR: camera trình duyệt không mở được trên HTTP/LAN | QR chứa URL, quét bằng camera điện thoại; token HMAC ngắn hạn |
| D27 | Bộ test và mã Bước 2 hiện chạy được cho phần logic thuần Python; môi trường soạn thảo không có FastAPI/SQLAlchemy/Postgres/Docker | Xem báo cáo Bước 2: phần chưa chạy thử được ghi rõ |
| D28 | Bố cục thật của file lịch ca trên Zalo chưa được quan sát (chỉ biết là bảng tính, QT3a-B1 C.3a.1). **Đã chốt 12/11:** hỗ trợ hai định dạng có nút tải file mẫu (1: lưới Ngày/Thứ + Ca Sáng/Trưa/Tối; 2: phẳng Ngày/Mã ca/Tên nhân viên); file mẫu giả lập `data/mock/sample_schedule_2026_11.xlsx` | Nếu file thật của quán khác hai dạng này, cần thêm bộ đọc |

Còn mở từ trước: D08–D14, D16, D18–D22 (xử lý tạm ở bảng trên).
