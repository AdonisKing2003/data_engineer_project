# Slide phần Project: cần làm những gì

Mô tả từng slide cho phần **Project** (file PDF + video 20–30 phút có demo ứng dụng), bám theo file yêu cầu môn
CO5173 học kỳ 1 năm 2026–2027. Lời nói cho từng slide nằm ở [presentation_script.md](presentation_script.md).
Số liệu lấy từ báo cáo (`report/`) và [overview_and_demo.md](overview_and_demo.md); đừng đổi số trên slide mà không
đổi ở báo cáo.

---

## 1. Yêu cầu của đề và cách slide đáp ứng

### Nộp gì

| Sản phẩm | Điểm | Ghi chú |
|---|---|---|
| Báo cáo kỹ thuật (PDF) | 10% | Bắt buộc mới được chấm phần Project |
| File trình bày (PDF) | 5% | Phải thể hiện giải pháp kỹ thuật dữ liệu **và** ứng dụng chứng minh giải pháp hiệu quả |
| Video (mp4/webm) | 5% | Trình bày + demo ứng dụng, **20–30 phút** |
| Bằng chứng ứng dụng chạy được | 15% | Demo ứng dụng chạy và đánh giá được |

Mọi file nộp phải đặt tên theo **mã nhóm**.

### Tiêu chí chấm slide và video

| Tiêu chí | Trọng số | Cách đạt mức cao nhất |
|---|---|---|
| Cấu trúc slide | 2/10 | **4 đến 7 phần**, phần nào cũng có cấu trúc con hợp lý. Bộ slide dưới đây có 6 phần |
| Nội dung slide | 6/10 | Chi tiết, có thảo luận lý do, **có ví dụ minh họa phù hợp**. Mỗi phần nên có ít nhất một con số thật hoặc một ví dụ cụ thể |
| Hình thức slide | 2/10 | Gần như không lỗi chữ, màu, bảng, hình. Rà chính tả và cỡ chữ trước khi xuất PDF |
| Thiết kế giao diện (UI) | 2/10 | Giao diện hợp ngữ cảnh, **có tính đến đặc điểm người dùng**, trình bày và tương tác hài hòa. Có slide riêng nói điều này (slide 16) |
| **Hiện thực ứng dụng** | **8/10** | Mỗi yêu cầu nghiệp vụ demo thành công kèm kết quả khai thác dữ liệu được 4/n/10 điểm (n = 3 thành viên). Cần ít nhất 2n = 6 BR; nhóm có 8 BR nên **demo đủ cả 8** |
| Nội dung video | 5/10 | Video khớp với **85–100% slide**: nói theo đúng thứ tự slide, không nhảy cóc, không bỏ slide |
| Trình bày video | 4/10 | Tự tin, mạch lạc, phối hợp tốt, **có tương tác**: chuyển lượt có nối ý, vài câu hỏi đáp ngắn giữa các thành viên |
| Thời lượng video | 1/10 | Nhắm khoảng 25 phút, nằm giữa khoảng 20–30 |

Điểm cộng nhóm: thêm phương án thay thế có đánh giá tốt, nhiều BR với nhiều nhóm người dùng, thảo luận có kết quả đo.
Project đã có sẵn cả ba thứ này (benchmark star / 3NF / bảng rộng, 8 BR cho 4 nhóm người dùng, số đo tối ưu), nên
cần nói rõ trên slide.

### Ánh xạ nội dung bắt buộc của đề sang slide

| Nội dung đề yêu cầu | Slide |
|---|---|
| Bối cảnh đề tài | 3 |
| Bên liên quan (nhất là người dùng), yêu cầu nghiệp vụ, nhu cầu dùng dữ liệu | 4, 5 |
| Nguồn dữ liệu và đặc điểm dữ liệu cần lưu ý | 6, 7 |
| Giải pháp kỹ thuật dữ liệu + **ít nhất một phương án thay thế** để so sánh | 8, 11, 12, 13, 14 |
| Công nghệ quản lý dữ liệu, công nghệ xử lý, cách tận dụng cho ứng dụng | 9, 10, 15 |
| Phát triển ứng dụng | 16–21 |
| Đánh giá: độ đúng dữ liệu, hiệu năng, hiệu quả khai thác qua ứng dụng | 22, 23, 24 |
| Kết luận | 25 |

---

## 2. Bố cục chung

6 phần, 26 slide, khoảng 25 phút video.

| Phần | Slide | Người trình bày | Thời lượng |
|---|---|---|---|
| Mở đầu | 1–2 | TV3 | 0:30 |
| 1. Bối cảnh và người dùng | 3–5 | TV3 | 3:00 |
| 2. Dữ liệu nguồn | 6–7 | TV1 | 2:30 |
| 3. Giải pháp kỹ thuật dữ liệu | 8–15 | TV1 (riêng slide 14: TV3) | 7:30 |
| 4. Ứng dụng và demo 8 BR | 16–21 | TV2 (BR1, 4, 5, 7), TV3 (BR2, 3, 6, 8), TV1 (stream) | 8:00 |
| 5. Đánh giá | 22–24 | TV2, TV1 | 3:00 |
| 6. Kết luận | 25–26 | TV2 | 1:00 |

Thời gian mỗi người khoảng 8–9 phút; đề chấm cả việc "có thành viên nói quá ít hoặc quá nhiều".

**Quy ước hình thức:**
- Một mẫu slide cho cả bộ. Góc dưới mỗi slide ghi tên phần đang trình bày và số trang.
- Mỗi slide một ý chính, đặt ngay ở tiêu đề (ví dụ "Cảnh báo ở tuần 4 đúng 80,6%", không phải "Kết quả BR4").
- Số viết theo kiểu Việt Nam như trong báo cáo: 1.342.949 dòng, 80,6%.
- Ảnh chụp dashboard dùng lại 4 ảnh trong `report/Images/` để slide khớp báo cáo.
- Bảng tối đa khoảng 6 dòng; dài hơn thì chỉ giữ dòng tiêu biểu, ghi "chi tiết trong báo cáo mục ...".

---

## 3. Từng slide

### Mở đầu

**Slide 1. Trang bìa**
- Tên đề tài: Kho dữ liệu phân tích học tập và cảnh báo sớm trên bộ dữ liệu OULAD.
- Mã nhóm, môn CO5173, giảng viên, học kỳ 1 năm 2026–2027.
- 3 thành viên kèm vai trò: TV1 Nguyễn Hoàng Vương (môi trường, ETL, kho, stream, Airflow, kiểm thử, tối ưu);
  TV2 Lê Đức Tài (BR1, BR4, BR5, BR7); TV3 Vũ Nguyễn Mai Linh (BR2, BR3, BR6, BR8, data mart, benchmark).

**Slide 2. Nội dung**
- 6 phần ở bảng trên, kèm tên người trình bày từng phần.

### Phần 1. Bối cảnh và người dùng

**Slide 3. Bối cảnh**
- Trường đào tạo từ xa: sinh viên học trên hệ thống trực tuyến (VLE), giảng viên không gặp trực tiếp, nên phát hiện
  sinh viên sắp rớt hay bỏ môn thường quá muộn.
- Dữ liệu có sẵn nhưng nằm rời ở nhiều file: đăng ký, bài nộp, click học liệu.
- Mục tiêu: dựng kho dữ liệu trả lời 8 yêu cầu nghiệp vụ và 20 câu hỏi mẫu, hiển thị trên dashboard theo vai trò.
- Ngoài phạm vi: không dựng CSDL vận hành (nguồn là bản xuất tĩnh); cảnh báo dùng quy tắc, không dùng học máy.

**Slide 4. Người dùng và 8 yêu cầu nghiệp vụ**
- Bảng 4 nhóm người dùng → BR (lấy từ Bảng "Nhóm người dùng" và "Tám yêu cầu nghiệp vụ" ở chương 1 và 3 của báo cáo):
  giảng viên BR1–3, cố vấn học tập BR4–5, lãnh đạo khoa BR6, sinh viên BR7–8.
- Mỗi BR một câu hỏi ngắn bằng lời người dùng, ví dụ BR4: "Tính đến cuối tuần này, sinh viên nào có dấu hiệu nguy
  cơ?".
- Ghi chú nhỏ: 8 BR ≥ 2n = 6 theo yêu cầu đề.

**Slide 5. Nhu cầu dùng dữ liệu**
- Bảng: nhóm người dùng | cần dữ liệu gì | mức chi tiết | tần suất | ràng buộc.
  - Giảng viên: click theo tuần và loại học liệu, bài nộp, điểm; theo đợt học; mỗi tuần.
  - Cố vấn: tiến độ từng sinh viên tại tuần đang xét; **chỉ dùng dữ liệu đến hết tuần đó** (không nhìn trước tương lai).
  - Lãnh đạo khoa: tỷ lệ đạt theo nhóm IMD qua 4 kỳ; chỉ báo ở mức nhóm.
  - Sinh viên: vị trí của mình so với phân vị lớp; nhóm dưới 30 người thì ẩn phân vị để tránh đoán ra số của người khác.
- Ý cần nhấn: các ràng buộc này quyết định thiết kế kho ở phần 3 (bảng ảnh chụp sinh viên–tuần, cờ chất lượng).

### Phần 2. Dữ liệu nguồn

**Slide 6. Bộ dữ liệu OULAD**
- Bảng 7 file và số dòng (Bảng "Bảy file CSV" ở chương 3 báo cáo). Nhấn `studentVle`: 10.655.280 dòng, 39.605.099 click.
- 22 đợt học, 28.785 sinh viên, 32.593 lượt đăng ký. Giấy phép CC BY 4.0, đã ẩn danh.

**Slide 7. Đặc điểm dữ liệu cần xử lý**
- Bảng vấn đề → ảnh hưởng → cách xử lý (chi tiết ở mục "Các vấn đề của dữ liệu nguồn" và "Xử lý các vấn đề của dữ liệu
  nguồn" trong báo cáo):
  - Dòng click trùng khóa: 3.810.465 dòng → gộp, 10,6 triệu còn 8,46 triệu dòng, tổng click giữ nguyên.
  - Giá trị thiếu ghi bằng `?`; IMD thiếu ở 971 sinh viên và có 2 cách ghi (`10-20`, `10-20%`) → NULL, chuẩn hóa, gắn cờ.
  - Không có ngày lịch, chỉ có số ngày tính từ khai giảng (có thể âm) → một quy tắc quy ngày về tuần dùng chung mọi engine.
  - `studentInfo` vi phạm 2NF; nhóm tuổi đổi giữa các lần đăng ký ở 72 sinh viên → tách bảng theo phụ thuộc hàm.
  - 102 lượt có kết quả mâu thuẫn với ngày rút; 11 bài thi không có hạn → giữ dòng, gắn cờ, không xóa.

### Phần 3. Giải pháp kỹ thuật dữ liệu

**Slide 8. Kiến trúc tổng thể**
- Hình `report/Images/Kien_truc.png`.
- 4 tầng raw → staging → kho → phục vụ; 3 nơi lưu; 2 đường nạp (batch bằng Spark, stream bằng Kafka + Spark);
  Airflow điều phối nhánh batch.

**Slide 9. Công nghệ quản lý dữ liệu**
- Bảng 3 nơi lưu | vai trò | lý do chọn:
  - BigQuery: kho chính cho dashboard; lưu theo cột, không quản trị máy chủ, tính tiền theo dữ liệu quét.
  - PostgreSQL 16: kho đối chứng và nền benchmark; lưu theo dòng, có chỉ mục.
  - Parquet + DuckDB: kho trung gian, nguồn chung cho mọi engine; viết và kiểm SQL tại máy không tốn hạn mức BigQuery.
- Giới hạn của BigQuery Sandbox: 10 GB, bảng tự xóa sau 60 ngày, không cho `INSERT`/`UPDATE`.

**Slide 10. Công nghệ xử lý: ETL bằng Spark**
- Các bước ETL và thời gian (Bảng thời gian ETL ở mục "ETL bằng Spark"); `make all` dựng lại toàn bộ kho trong 303 s.
- Nguyên tắc: gắn cờ chất lượng thay vì xóa dòng; nạp lại không nhân đôi dữ liệu.
- Vì sao Spark: kho 5× có 42,3 triệu dòng click; cùng một engine cho batch và stream; code chạy được trên cụm.

**Slide 11. Thiết kế kho: star schema dạng constellation**
- Hình `report/Images/star_schema.png`.
- 5 dimension, 4 fact; ghi grain của từng fact.
- Nhấn bảng ảnh chụp `fact_student_week` (1.342.949 dòng, một sinh viên × một đợt × một tuần): chỉ chứa dữ liệu đến hết
  tuần đó và không chứa cột kết quả cuối kỳ, nên cảnh báo không dùng được thông tin tương lai.

**Slide 12. Stream: Kafka + Spark Structured Streaming**
- Sơ đồ: producer → Kafka → Spark (cửa sổ tuần theo thời gian sự kiện, watermark 7 ngày) → BigQuery (bảng log ghi thêm
  + view lấy bản mới nhất) → trang Click thời gian thực.
- Số đo: lệch 0 dòng so với batch trên 1.342.949 dòng; trạng thái lớn nhất 65 nghìn khóa thay vì 627 nghìn khi không
  có watermark; chạy lại một micro-batch không sinh dòng trùng.
- Nói trước hạn chế: là phát lại dữ liệu lịch sử, nhưng xử lý theo thời gian sự kiện như với luồng thật.

**Slide 13. Điều phối bằng Airflow**
- **Cần chụp:** tab Graph và Gantt của DAG `oulad_batch` (cách chụp ở [overview_and_demo.md](overview_and_demo.md) mục 5.1
  bước 4).
- Sensor chờ dữ liệu → các bước Spark → cổng chất lượng → 2 bước nạp song song → dựng lại data mart. DAG chạy 223 s.
- Cổng chất lượng lỗi thì không nạp, BigQuery giữ bản cũ; task lỗi hẳn thì báo qua log và webhook.

**Slide 14. Phương án thay thế: star, 3NF, bảng rộng** (TV3)
- 3 cách tổ chức × 2 hệ (PostgreSQL, BigQuery) × 2 quy mô (1×, 5×), 4 truy vấn đại diện, mỗi tổ hợp chạy 5 lần lấy
  trung vị; 44/48 tổ hợp đo được (bảng rộng 5× vượt 10 GB của Sandbox).
- Bảng rút gọn từ Bảng "Thời gian trung vị của star" ở mục "So sánh các cách tổ chức dữ liệu".
- 3 kết luận: PostgreSQL star ≈ 3NF (chênh ≤ 11%); bảng rộng chậm 2,02× ở BR1 vì đọc cả dòng; BigQuery star và 3NF
  quét cùng lượng dữ liệu.
- Quyết định: giữ star vì dễ viết truy vấn nhất và không thua rõ ở đâu; tăng tốc bằng tối ưu (slide 15) thay vì đổi
  cách tổ chức.

**Slide 15. Tận dụng công nghệ cho ứng dụng**
- Bảng 4 kỹ thuật tối ưu đã nằm trong kho chính (Bảng "Kết quả các kỹ thuật tối ưu truy vấn"):
  phân vùng 79,2 → 4,7 MB (16,8×); gom cụm 304,6 → 19,2 MB (15,9×); data mart BR2 381,6 → 1,2 MB (330×);
  chỉ mục PostgreSQL 200,5 → 37,6 ms (5,3×).
- Lớp truy vấn chung: dashboard đổi nơi đọc (BigQuery / DuckDB) bằng một biến môi trường; kết quả lưu tạm 1–6 giờ vì kho
  chỉ đổi khi nạp lại.
- Ví dụ thảo luận: phân vùng chỉ có tác dụng khi lọc cột phân vùng bằng hằng số (Bảng "điều kiện hằng số" trong báo cáo).

### Phần 4. Ứng dụng và demo

Slide 17–21 là slide mốc: video chiếu slide vài giây rồi chuyển sang quay màn hình dashboard. Mỗi BR demo theo cùng
một khuôn: **câu hỏi của người dùng → thao tác trên trang → đọc kết quả → một câu ý nghĩa**. Đây là phần được 8/10 điểm
nên không cắt BR nào.

**Slide 16. Dashboard: thiết kế theo người dùng** (phục vụ tiêu chí UI 2/10)
- Ảnh trang Tổng quan (cần chụp) hoặc menu bên trái.
- 9 trang chia theo 6 nhóm (Bảng "Các trang của dashboard theo nhóm người dùng").
- Những điểm đã tính đến người dùng:
  - Menu theo vai trò, mỗi người chỉ cần đọc nhóm trang của mình.
  - Chọn đợt học một lần, chuyển trang không phải chọn lại.
  - Trang sinh viên ẩn phân vị khi nhóm dưới 30 người, chỉ báo IMD ở mức nhóm.
  - Chế độ đối soát của cố vấn tách riêng, không ảnh hưởng danh sách cảnh báo.
  - Giao diện tiếng Việt; mỗi biểu đồ có chú thích cách tính và câu nhắc "tương quan, không phải nhân quả".
- Mọi số trên trang tính từ kho lúc mở trang, không ghi cố định trong code.

**Slide 17. Giảng viên: BR1, BR2, BR3**
- Ảnh `report/Images/dashboard_hoc_phan.png`. Ba câu hỏi và kết quả: 16,8% bài TMA nộp trễ; `oucontent` chiếm 28,3%
  click, tuần 2 nhiều click nhất; Spearman dương ở cả 19 đợt, từ 0,16 đến 0,41.

**Slide 18. Cố vấn học tập: BR4, BR5**
- Ảnh `report/Images/dashboard_canh_bao.png`. Tuần 4: 3.958 sinh viên, 80,6% thực sự rớt hoặc rút (nền 43,5%).
  30,4% lượt rút diễn ra trước hoặc đúng ngày khai giảng; ngày rút trung vị là ngày 27.

**Slide 19. Lãnh đạo khoa: BR6**
- Ảnh `report/Images/dashboard_imd.png`. Kỳ 2014J: 41,1% so với 63,3%, chênh 22,2 điểm; kỳ 2013B chênh 25,3 điểm.

**Slide 20. Sinh viên: BR7, BR8**
- Ảnh `report/Images/dashboard_sinh_vien.png`. AAA 2014J tuần 10: trung vị tổng click 593 trên 336 sinh viên.
  Thêm ảnh trang **So với nhóm đạt** (cần chụp, đặt cạnh ảnh BR7): BBB 2013J tuần 5, sinh viên 23798 có 10 click diễn
  đàn, nằm trong dải 0–22 của 1.072 bạn đã đạt (trung vị 5); mỗi loại học liệu một dòng.

**Slide 21. Click thời gian thực** (TV1)
- Ảnh trang Click thời gian thực khi đường stream đã trùng đường batch (cần chụp).
- Dùng làm mốc cho đoạn quay demo stream khoảng 1 phút.

### Phần 5. Đánh giá

**Slide 22. Độ đúng dữ liệu** (TV2)
- Đáp án chuẩn của 20 câu hỏi mẫu tính thẳng từ 7 file CSV, không qua kho; SQL chạy trên BigQuery, PostgreSQL, DuckDB
  đều trùng đáp án. Số dòng 9 bảng khớp trên cả 3 nơi lưu.
- 290 bài kiểm thử, nhóm theo Bảng "Phân nhóm bộ kiểm thử".
- Ví dụ thảo luận: đối chiếu hai hệ phát hiện BigQuery dùng phân vị xấp xỉ làm danh sách cảnh báo ra 3.953 thay vì
  3.958; đổi sang phân vị chính xác thì khớp.

**Slide 23. Hiệu năng** (TV1)
- Dựng lại kho: `make all` 303 s, DAG Airflow 223 s.
- Nhắc lại 4 số tối ưu (slide 15) và kết quả chỉ mục cho `fact_student_week` (mục "Chỉ mục và hiệu năng truy vấn"):
  BigQuery 79,2 → 4,7 MB; PostgreSQL 125 → 74 ms, số trang đọc 22.016 → 567 khi thêm `CLUSTER`; chi phí ghi tăng 91%.

**Slide 24. Hiệu quả khai thác qua ứng dụng** (TV2)
- Dashboard trả lời được cả 20 câu hỏi mẫu trên giao diện (có test mô phỏng người dùng).
- Bảng "Dữ liệu quét và thời gian tải từng trang" (mục "Hiệu quả khai thác qua ứng dụng" trong báo cáo): 7/8 trang tải
  trong khoảng 2,5 giây lần đầu, trang Cảnh báo 7,7 giây; một lượt mở cả 8 trang quét khoảng 273 MB, hạn mức miễn phí
  1 TB/tháng đủ cho hơn 3.000 lượt.
- Có thể thêm 1 slide tóm tắt bảng "Đánh giá các công nghệ" (6 công nghệ × 4 tiêu chí) nếu còn thời gian.
- Bảng BR4 theo tuần (Bảng "Hiệu quả quy tắc cảnh báo sớm BR4"): tuần 4 / 8 / 12, độ chính xác 80,6 / 84,6 / 80,6%,
  độ bao phủ 26,9 / 35,6 / 45,0%. Thảo luận: cảnh báo sớm thì danh sách ngắn mà phần lớn đúng; muộn hơn thì bắt được
  nhiều hơn nhưng còn ít thời gian hỗ trợ.

### Phần 6. Kết luận

**Slide 25. Kết luận và hướng phát triển**
- Đạt được: kho chạy lại bằng một lệnh, đúng trên 3 nơi lưu, 8 BR cho 4 nhóm người dùng, batch và stream, có số đo.
- Hạn chế (nói chủ động, theo bảng "Hạn chế" ở [lo_traceability.md](lo_traceability.md)): stream là phát lại dữ liệu;
  Kafka 1 broker; BigQuery Sandbox nên nạp lại toàn bộ, chưa có CDC; star chậm hơn 3NF trên BigQuery chưa giải thích được.
- Hướng phát triển: CDC (Debezium → Kafka → `MERGE`), Storage Write API cho độ trễ dưới 1 giây, mô hình học máy cho cảnh báo.

**Slide 26. Cảm ơn**
- Đường dẫn mã nguồn; cách chạy (`docker compose up`, `make all`, `make app`).

---

## 4. Việc cần chuẩn bị trước khi làm slide

- [ ] Chụp Airflow tab Graph và Gantt (slide 13).
- [ ] Chụp trang Tổng quan (slide 16), trang So với nhóm đạt ở BBB 2013J tuần 5 (slide 20) và trang Click thời gian
      thực khi stream chạy xong (slide 21).
- [ ] Xác nhận mã nhóm để ghi lên bìa và đặt tên file nộp. Project GCP tên `dataengineergroup32`, nên nhiều khả năng là
      nhóm 32.
