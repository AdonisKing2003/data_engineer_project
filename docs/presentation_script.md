# Kịch bản video phần Project

Lời nói và thao tác cho video phần Project (20–30 phút, nhắm khoảng 25 phút). Nội dung từng slide nằm ở
[slides_outline.md](slides_outline.md); số slide dưới đây khớp với file đó. Nói theo đúng thứ tự slide: đề chấm video
theo tỷ lệ khớp với slide (mức cao nhất là 85–100%).

Lời nói chỉ là gợi ý; mỗi người nói lại bằng lời của mình, nhưng **giữ nguyên các con số**.

---

## Chuẩn bị trước khi quay

**Máy và dữ liệu** (chi tiết ở [overview_and_demo.md](overview_and_demo.md) mục 5.1–5.2):

```bash
docker compose --profile stream up -d                                # app, postgres, kafka
docker compose exec -d app bash -c "cd /work && make app"            # Streamlit, mở http://localhost:8501
```

- Mở thử mọi trang một lượt cho kết quả BigQuery được lưu tạm, lúc quay trang hiện ngay. Trang nào báo không tìm thấy
  bảng thì BigQuery Sandbox đã xóa bảng (sau 60 ngày): chạy `make all` rồi `make marts`.
- Chạy stream một lần trước (`make stream-kafka STREAM_ARGS="--produce --to-bq"`) để Spark tải sẵn connector.
- Trình duyệt phóng to khoảng 110–125% để chữ đọc được trong video; tắt thông báo hệ thống.

**Cách quay:**
- Quay màn hình slide hoặc dashboard, góc dưới có khung mặt người đang nói.
- Mỗi người quay phần của mình rồi ghép; chỗ chuyển lượt quay cả hai người, hoặc ghép liền để nghe như nói tiếp nhau.
- Khi demo, rê chuột vào đúng con số đang đọc.

**Tương tác** (đề chấm "có tương tác phù hợp" ở mức cao nhất):
- Chuyển lượt luôn có câu nối ý, gọi tên người nói tiếp.
- Có 3 đoạn hỏi đáp ngắn giữa các thành viên, đánh dấu **[Hỏi đáp]** bên dưới. Các đoạn này trả lời đúng những câu hay
  bị hỏi, nên vừa là tương tác vừa là nội dung.

**Phân chia:** TV1 khoảng 9 phút, TV2 khoảng 8 phút, TV3 khoảng 8 phút.

---

## Mở đầu (0:00–0:30) — TV3

**Slide 1–2.**
> Chào thầy cô và các bạn. Nhóm [mã nhóm] trình bày project "Kho dữ liệu phân tích học tập và cảnh báo sớm" trên bộ
> dữ liệu OULAD. Nhóm có ba thành viên: Vương phụ trách môi trường, ETL, kho dữ liệu và stream; Tài phụ trách bốn yêu
> cầu BR1, BR4, BR5, BR7; mình là Linh, phụ trách BR2, BR3, BR6, BR8 và phần so sánh các cách tổ chức dữ liệu.
> Bài trình bày gồm 6 phần: bối cảnh và người dùng, dữ liệu nguồn, giải pháp kỹ thuật dữ liệu, ứng dụng và demo,
> đánh giá, và kết luận.

---

## Phần 1. Bối cảnh và người dùng (0:30–3:30) — TV3

**Slide 3. Bối cảnh** (1 phút)
> Open University là trường đào tạo từ xa ở Anh. Sinh viên học gần như hoàn toàn trên hệ thống trực tuyến, gọi là VLE,
> nên giảng viên không thấy ai đang tụt lại. Thường đến khi có điểm thi mới biết sinh viên rớt, lúc đó đã quá muộn để
> hỗ trợ.
> Dữ liệu để phát hiện sớm thì có: ai đăng ký, nộp bài lúc nào, điểm bao nhiêu, click vào học liệu nào mỗi ngày. Nhưng
> nó nằm rời ở 7 file. Mục tiêu của nhóm là dựng một kho dữ liệu gom các file này lại, trả lời 8 yêu cầu nghiệp vụ và
> 20 câu hỏi mẫu, rồi đưa kết quả lên dashboard cho từng nhóm người dùng.
> Nhóm không dựng cơ sở dữ liệu vận hành vì nguồn là bản xuất tĩnh, và cảnh báo dùng quy tắc chứ không dùng học máy.

**Slide 4. Người dùng và 8 yêu cầu nghiệp vụ** (1 phút)
> Hệ thống phục vụ 4 nhóm người dùng. Giảng viên cần biết sinh viên nộp bài và học trên VLE ra sao: BR1 đến BR3. Cố vấn
> học tập cần danh sách sinh viên có nguy cơ và biết sinh viên hay rút môn vào lúc nào: BR4 và BR5. Lãnh đạo khoa quan
> tâm khoảng cách kết quả giữa sinh viên ở khu vực khó khăn và khu vực khá giả: BR6. Còn sinh viên muốn biết mình đang
> ở đâu so với các bạn cùng lớp: BR7 và BR8.
> Nhóm có 3 người nên đề yêu cầu ít nhất 6 yêu cầu nghiệp vụ; nhóm làm 8.

**Slide 5. Nhu cầu dùng dữ liệu** (1 phút)
> Mỗi nhóm cần dữ liệu ở mức chi tiết và với ràng buộc khác nhau, và chính các ràng buộc này quyết định thiết kế kho.
> Quan trọng nhất là cố vấn học tập: danh sách cảnh báo ở tuần 4 chỉ được dùng dữ liệu đến hết tuần 4. Nếu lỡ dùng kết
> quả cuối kỳ thì cảnh báo trông rất chính xác nhưng không dùng được ngoài thực tế.
> Với sinh viên, nếu lớp dưới 30 người thì không hiện phân vị, để không ai đoán ra số của bạn khác. Với lãnh đạo khoa,
> kết quả chỉ báo ở mức nhóm IMD.
> Vương sẽ trình bày dữ liệu nguồn và những gì phải xử lý trước khi đưa vào kho.

---

## Phần 2. Dữ liệu nguồn (3:30–6:00) — TV1

**Slide 6. Bộ dữ liệu OULAD** (1 phút)
> Bộ OULAD gồm 7 file CSV: 22 đợt học của 7 môn trong hai năm 2013–2014, 28.785 sinh viên, 32.593 lượt đăng ký. File
> lớn nhất là `studentVle`, ghi số click của từng sinh viên trên từng học liệu mỗi ngày: hơn 10,6 triệu dòng, gần 40 triệu
> click. Dữ liệu đã ẩn danh, giấy phép CC BY 4.0.

**Slide 7. Đặc điểm dữ liệu cần xử lý** (1 phút 30)
> Dữ liệu không nạp thẳng vào kho được, vì 5 vấn đề.
> Thứ nhất, file click không có khóa: hơn 3,8 triệu dòng trùng sinh viên, học liệu và ngày. Nhóm gộp lại, còn 8,46 triệu
> dòng, và kiểm tra tổng click trước và sau vẫn bằng nhau.
> Thứ hai, giá trị thiếu ghi bằng dấu hỏi, cột IMD vừa thiếu vừa ghi một nhóm theo hai cách.
> Thứ ba, không có ngày lịch: mọi mốc là số ngày tính từ khai giảng, có thể âm. Nếu mỗi engine quy ngày về tuần một kiểu
> thì cùng câu hỏi sẽ ra hai đáp án, nên nhóm chốt một quy tắc chung.
> Thứ tư, `studentInfo` vi phạm dạng chuẩn 2: đặc điểm sinh viên lặp lại ở mỗi đợt. Nhóm tuổi trông như đặc điểm sinh
> viên nhưng đổi giữa các lần đăng ký ở 72 người, nên phải xếp vào lượt đăng ký.
> Cuối cùng là các dòng mâu thuẫn. Nguyên tắc chung: không xóa dòng nào, chỉ gắn cờ chất lượng, để số đếm luôn đối chiếu
> được với nguồn.

---

## Phần 3. Giải pháp kỹ thuật dữ liệu (6:00–13:30) — TV1, slide 14 TV3

**Slide 8. Kiến trúc tổng thể** (1 phút)
> Dữ liệu đi qua 4 tầng theo một chiều: file gốc, staging dạng Parquet, kho dạng star schema, rồi tầng phục vụ. Mỗi tầng
> dựng lại được hoàn toàn từ tầng trước. Kho được nạp vào 3 nơi, mỗi nơi một vai trò. Có hai đường nạp: batch bằng Spark,
> và stream đi qua Kafka. Airflow điều phối toàn bộ nhánh batch.

**Slide 9. Công nghệ quản lý dữ liệu** (1 phút)
> BigQuery là kho chính cho dashboard: lưu theo cột nên truy vấn tổng hợp chỉ đọc cột cần, không phải quản trị máy chủ,
> và tính tiền theo dữ liệu quét. Vì vậy mọi tối ưu trên BigQuery nhóm đều đo bằng số byte quét.
> PostgreSQL lưu theo dòng, là kho đối chứng: cùng một câu SQL phải ra cùng kết quả trên hai hệ lưu khác nhau. Parquet
> cùng DuckDB là nguồn chung và là nơi viết, kiểm SQL tại máy mà không tốn hạn mức BigQuery.
> Gói Sandbox miễn phí có giới hạn: 10 GB, bảng tự xóa sau 60 ngày, không cho `INSERT` hay `UPDATE`. Giới hạn này ảnh
> hưởng tới cách nạp mà mình sẽ nói ở phần stream.

**Slide 10. ETL bằng Spark** (1 phút)
> ETL viết bằng PySpark. Một lệnh `make all` dựng lại toàn bộ kho từ 7 file gốc trong khoảng 5 phút, 303 giây. Chạy lại
> bao nhiêu lần cũng không nhân đôi dữ liệu.
> Nhóm chọn Spark dù 10 triệu dòng thì pandas vẫn chạy được, vì kho 5 lần để đo tải có 42 triệu dòng click, vì Spark
> dùng chung cho cả batch và stream, và vì code giữ nguyên khi chuyển lên cụm.

**Slide 11. Thiết kế kho** (1 phút 15)
> Kho theo mô hình chiều: 4 bảng fact dùng chung 5 dimension, dạng constellation. Bảng đáng chú ý nhất là
> `fact_student_week`, 1,34 triệu dòng, mỗi dòng là một sinh viên trong một đợt tại một tuần. Mỗi dòng chỉ chứa dữ liệu
> phát sinh đến hết tuần đó, và bảng không có cột kết quả cuối kỳ. Nhờ vậy truy vấn cảnh báo ở tuần 4 về cấu trúc không
> thể nhìn thấy tương lai.

**[Hỏi đáp 1]** (20 giây)
> **TV2:** Nhưng trang cảnh báo của mình vẫn hiện độ chính xác, tức là vẫn phải dùng kết quả cuối kỳ chứ?
> **TV1:** Đúng, nhưng kết quả cuối kỳ chỉ được ghép vào **sau khi** đã có danh sách, để chấm danh sách đó. Nhóm có test
> đảo toàn bộ kết quả cuối kỳ rồi chạy lại: danh sách vẫn đúng 3.958 sinh viên, chỉ độ chính xác thay đổi.

**Slide 12. Stream** (1 phút 15)
> Nhánh stream: một producer phát lại file click theo ngày vào Kafka. Spark Structured Streaming gom theo cửa sổ tuần
> theo thời gian sự kiện, với watermark 7 ngày, rồi ghi lên BigQuery. Vì Sandbox không cho `UPDATE`, mỗi micro-batch ghi
> thêm vào một bảng log, và một view lấy bản mới nhất.
> Kết quả stream lệch 0 dòng so với batch trên 1,34 triệu dòng. Watermark giữ trạng thái lớn nhất ở 65 nghìn khóa thay vì
> 627 nghìn. Chạy lại một micro-batch không sinh dòng trùng.
> Đây là phát lại dữ liệu lịch sử, nhưng nguồn là Kafka và xử lý theo thời gian sự kiện, đúng như khi có luồng thật.

**Slide 13. Airflow** (45 giây)
> Airflow chạy nhánh batch theo lịch: chờ dữ liệu nguồn, chạy các bước Spark, qua cổng kiểm tra chất lượng, rồi hai bước
> nạp BigQuery và PostgreSQL chạy song song, cuối cùng dựng lại data mart. Cả DAG mất 223 giây. Nếu cổng chất lượng lỗi
> thì không nạp, dashboard vẫn đọc bản cũ còn đúng. Mỗi task gọi đúng một lệnh `make`, nên logic không bị viết hai lần.
> Để phần so sánh phương án thay thế, mời Linh.

**Slide 14. Phương án thay thế** (1 phút 15) — TV3
> Đề yêu cầu ít nhất một phương án thay thế. Nhóm so star schema với hai phương án: lược đồ chuẩn 3NF, và bảng rộng đã
> nối sẵn mọi thuộc tính. Đo trên 2 hệ, 2 quy mô 1× và 5×, 4 truy vấn đại diện, mỗi tổ hợp chạy 5 lần lấy trung vị, và
> chỉ ghi nhận khi mọi tổ hợp ra cùng đáp án.
> Trên PostgreSQL, star và 3NF gần như ngang nhau, chênh không quá 11%. Bảng rộng chậm gấp 2 lần ở BR1, vì hệ lưu theo
> dòng phải đọc cả dòng kể cả cột không dùng, nhưng lại nhanh hơn ở truy vấn nhỏ như BR6 vì không phải nối bảng. Trên
> BigQuery, star và 3NF quét đúng cùng lượng dữ liệu, vì hệ lưu theo cột chỉ đọc cột cần.
> Không phương án nào thắng ở mọi ô, nên nhóm giữ star vì dễ viết truy vấn nhất, và tăng tốc từng trang bằng tối ưu.
> Vương nói tiếp phần tối ưu.

**Slide 15. Tận dụng công nghệ cho ứng dụng** (1 phút) — TV1
> Bốn kỹ thuật tối ưu đã nằm trong kho chính, mỗi cái đo trên đúng truy vấn của một trang. Phân vùng bảng tiến độ theo
> tuần giảm dữ liệu quét 16,8 lần. Gom cụm bảng click theo đợt giảm 15,9 lần. Data mart BR2 giảm 330 lần, từ 381 MB xuống
> 1,2 MB mỗi lần mở trang. Chỉ mục trên PostgreSQL nhanh hơn 5,3 lần.
> Một điều nhóm học được: phân vùng chỉ có tác dụng khi lọc bằng hằng số. Truy vấn cảnh báo ban đầu lọc tuần trước bằng
> "tuần hiện tại trừ một" qua phép nối, BigQuery không dùng điều kiện đó để bỏ phân vùng, nên vẫn quét 79 MB. Thêm điều
> kiện hằng số tương đương thì còn 4,7 MB.
> Dashboard đọc dữ liệu qua một lớp truy vấn chung, đổi giữa BigQuery và DuckDB bằng một biến môi trường. Tài sẽ giới
> thiệu dashboard.

---

## Phần 4. Ứng dụng và demo (13:30–21:30) — TV2, TV3, TV1

Mỗi BR theo cùng một khuôn: **câu hỏi → thao tác → đọc kết quả → một câu ý nghĩa**. Phần này được 8/10 điểm, không cắt
BR nào.

**Slide 16. Dashboard: thiết kế theo người dùng** (1 phút) — TV2
> Dashboard viết bằng Streamlit, 9 trang chia theo vai trò. Mỗi người chỉ cần đọc nhóm trang của mình ở menu trái. Chọn
> đợt học một lần thì chuyển trang không phải chọn lại. Trang sinh viên ẩn phân vị khi lớp dưới 30 người. Mọi biểu đồ có
> chú thích cách tính, và các trang tương quan đều nhắc "tương quan, không phải nhân quả". Mọi con số được tính từ kho lúc
> mở trang, không có số nào ghi cố định trong code.

**Slide 17 → demo BR1** (1 phút) — TV2
- Thao tác: trang **Nộp bài & điểm**, đợt **BBB 2014J** (mặc định). Chỉ biểu đồ tỷ lệ nộp và trễ từng bài, rồi hộp điểm.
  Cuộn xuống phần **Toàn trường**.
> Câu hỏi của giảng viên: mỗi bài tập có bao nhiêu sinh viên nộp, bao nhiêu nộp trễ, điểm ra sao. Với BBB 2014J, đây là
> tỷ lệ nộp và nộp trễ từng bài, và phân bố điểm. Toàn trường, 16,8% bài TMA nộp trễ. Bài chuyển điểm từ đợt trước không
> được tính, và CMA không tính trễ vì ngày ghi của CMA không phải hạn nộp thật.
> Linh trình bày hai yêu cầu còn lại của giảng viên.

**Demo BR2** (1 phút) — TV3
- Thao tác: trang **Hoạt động học tập**, tab **Click VLE theo tuần**. Chọn **Toàn trường** trước, rồi đổi sang **BBB 2014J**,
  tuần **4**.
> Giảng viên hỏi: sinh viên dùng loại học liệu nào nhiều nhất, và giai đoạn nào hoạt động nhiều. Toàn trường, trang nội
> dung `oucontent` chiếm 28,3% click, và tuần 2 có nhiều click nhất. Chọn một đợt là BBB 2014J: heatmap cho thấy tỷ trọng
> từng loại học liệu theo tuần, các vạch đứt là hạn nộp TMA. Ở tuần 4 có 1.782 sinh viên còn học, trung bình 28,6 click
> mỗi người. Trang này đọc từ data mart, nên mỗi lần mở chỉ quét khoảng 1 MB.

**Demo BR3** (45 giây) — TV3
- Thao tác: cùng trang, tab **Click trước hạn TMA và điểm**.
> Câu hỏi: click nhiều trước hạn bài TMA đầu tiên thì điểm bài đó có cao hơn không. Cả 19 đợt có TMA tính điểm đều có hệ
> số Spearman dương, từ 0,16 ở BBB 2014J đến 0,41 ở EEE 2014J: liên hệ dương nhưng yếu đến vừa. Đây là tương quan, không
> cho phép nói click nhiều làm điểm cao.
> Tài trình bày phần cho cố vấn học tập.

**Slide 18 → demo BR4** (1 phút 15) — TV2
- Thao tác: trang **Cảnh báo sớm & rút lui**, sidebar để **Tất cả các đợt (Toàn trường)**, tuần **4**, bật chế độ đối soát.
  Sau đó kéo tuần lên **12**. Cuối cùng chọn **BBB 2014J**, tuần 4, cuộn xuống danh sách.
> Câu hỏi của cố vấn: tính đến cuối tuần này, ai đang có nguy cơ. Mỗi sinh viên được xét 4 dấu hiệu: click thuộc 25%
> thấp nhất, hai tuần liền không click, có TMA quá hạn chưa nộp, điểm trung bình dưới 40. Từ hai dấu hiệu trở lên thì vào
> danh sách.
> Tuần 4, toàn trường có 3.958 sinh viên. Bật chế độ đối soát: 80,6% trong số đó cuối cùng rớt hoặc rút, gần gấp đôi tỷ lệ
> nền 43,5%. Kéo lên tuần 12, danh sách bắt được 45% số sinh viên sẽ rớt hoặc rút mà độ chính xác vẫn trên 80%; đổi lại
> còn ít thời gian hỗ trợ hơn. Với từng đợt, ví dụ BBB 2014J, cố vấn có danh sách tên kèm dấu hiệu nào đang bật.

**Demo BR5** (45 giây) — TV2
- Thao tác: cùng trang, tab **Đường cong rút lui tích lũy & duy trì**.
> Câu hỏi: sinh viên rút môn vào lúc nào. 30,4% lượt rút diễn ra trước hoặc đúng ngày khai giảng, và ngày rút trung vị là
> ngày 27, tức khoảng tuần 3. Nghĩa là muốn giữ chân sinh viên thì phải liên hệ trước và ngay đầu đợt học.
> Linh trình bày phần của lãnh đạo khoa.

**Slide 19 → demo BR6** (1 phút) — TV3
- Thao tác: trang **Khoảng cách IMD**, chỉ số **Pass/Distinction**, rồi đổi sang **Distinction**.
> Lãnh đạo khoa hỏi: nhóm sinh viên ở khu vực khó khăn nhất đạt môn thấp hơn nhóm khá giả nhất bao nhiêu, và có thay đổi
> qua các kỳ không. Kỳ 2014J, nhóm IMD 0–10% đạt 41,1%, nhóm 90–100% đạt 63,3%, chênh 22,2 điểm phần trăm. Kỳ 2013B chênh
> 25,3 điểm, nên khoảng cách có thu hẹp nhưng vẫn lớn. Chỉ dùng 3 môn có đủ 4 kỳ để so qua thời gian cho công bằng, và
> nhóm nào quá ít người thì không hiện số.

**[Hỏi đáp 2]** (20 giây)
> **TV2:** Con số 41,1 này có chắc đúng không, hay chỉ đúng trên BigQuery?
> **TV3:** Câu này là câu hỏi mẫu số 18. Đáp án chuẩn được tính thẳng từ file CSV gốc, rồi cùng câu SQL chạy trên
> BigQuery, PostgreSQL và DuckDB, cả ba đều ra 41,1, 63,3 và 22,2.

**Slide 20 → demo BR7** (1 phút) — TV2
- Thao tác: trang **Tiến độ so với lớp**, đợt **AAA 2014J** (mặc định). Chọn một sinh viên, chỉ đường của sinh viên so với
  dải phân vị; kéo **tuần đánh giá = 10**.
> Câu hỏi của sinh viên: tính đến tuần này, mình đang ở đâu so với các bạn. Đường đỏ là tổng click của mình, dải xanh là
> 50% ở giữa của lớp, đường đứt nét là trung vị. Ở tuần 10, trung vị của 336 bạn còn học là 593 click. Trang đưa ra một câu
> nhận xét ngắn về vị trí của mình, không hiện số của bất kỳ bạn nào khác.

**Demo BR8** (1 phút) — TV3
- Thao tác: trang **So với nhóm đạt**. Trang mở sẵn ở **BBB 2013J**, **tuần 5** và sinh viên đầu danh sách (23798).
  Chỉ dòng `forumng`, rồi đổi sang một mã sinh viên khác để thấy chấm chuyển đỏ hoặc xanh. Cuộn xuống phần **Ví dụ**.
> Câu hỏi của sinh viên: tuần này mình dùng từng loại học liệu nhiều hay ít so với các bạn đã đạt môn. Mỗi dòng là một
> loại học liệu: dải xanh nhạt là 50% ở giữa của nhóm đạt, vạch xanh đậm là trung vị, hình thoi là số của mình. Thoi đỏ là
> thấp hơn 25% nhóm đạt, xanh lá là cao hơn 75%.
> Ví dụ bạn 23798 ở BBB 2013J tuần 5 có 10 click diễn đàn, nằm trong dải 0 đến 22 của 1.072 bạn đã đạt, trung vị là 5.
> Dải này cũng chính là đáp án câu hỏi mẫu 20 ở phần ví dụ bên dưới. Danh sách chỉ gồm sinh viên còn học ở tuần đó, và
> nhóm đạt dưới 30 người thì không hiện dải. Khi dùng thật thì nhóm đạt lấy từ đợt trước của cùng môn, vì đợt đang học
> chưa có kết quả.
> Vương demo trang thời gian thực.

**Slide 21 → demo stream** (1 phút) — TV1
- Thao tác: trang **Click thời gian thực**, bật **Tự tải lại**. Ở terminal:
  `docker compose exec app make stream-kafka STREAM_ARGS="--produce --to-bq"`. Cắt video, chỉ giữ đầu và cuối.
> Đây là cùng số liệu click theo tuần nhưng đến từ Kafka. Đường liền là stream, đường đứt nét là batch. Khi producer phát
> hết dữ liệu, hai đường trùng nhau, khớp với con số lệch 0 dòng ở phần trước. Độ trễ khoảng 5 đến 10 giây, vì Sandbox chỉ
> cho nạp bằng load job.

---

## Phần 5. Đánh giá (21:30–24:30) — TV2, TV1

**Slide 22. Độ đúng dữ liệu** (1 phút) — TV2
> Nhóm đánh giá theo ba tiêu chí của đề. Thứ nhất là độ đúng. Đáp án chuẩn của 20 câu hỏi mẫu được tính thẳng từ 7 file
> CSV, không đi qua kho. SQL của 20 câu chạy trên cả ba hệ đều trùng đáp án. Số dòng 9 bảng khớp trên cả ba nơi lưu. Toàn
> bộ có 290 bài kiểm thử.
> Việc đối chiếu nhiều hệ đã bắt được một lỗi thật: bản BigQuery của vài truy vấn dùng hàm phân vị xấp xỉ, làm danh sách
> cảnh báo ra 3.953 thay vì 3.958 sinh viên. Đổi sang phân vị chính xác thì khớp.

**Slide 23. Hiệu năng** (1 phút) — TV1
> Thứ hai là hiệu năng. Dựng lại toàn bộ kho mất 303 giây bằng một lệnh, qua Airflow là 223 giây vì hai bước nạp chạy song
> song. Ở mức truy vấn, ngoài 4 kỹ thuật đã nói, nhóm làm thêm chỉ mục cho bảng tiến độ theo tuần: chỉ mục B-tree một mình
> lại chậm hơn vì dòng nằm rải khắp bảng; sắp lại bảng theo chỉ mục bằng `CLUSTER` thì số trang phải đọc giảm từ 22 nghìn
> xuống 567, đổi lại thời gian ghi tăng 91%.

**[Hỏi đáp 3]** (20 giây)
> **TV2:** Vậy sao không bật chỉ mục cho mọi bảng?
> **TV1:** Vì chỉ mục có giá khi ghi và chiếm chỗ: riêng một chỉ mục đã 499 MB. Nhóm chỉ thêm ở bảng mà trang dashboard
> đọc nhiều và kho chỉ nạp lại theo lịch.

**Slide 24. Hiệu quả khai thác qua ứng dụng** (1 phút) — TV2
> Thứ ba là hiệu quả khai thác. Nhóm mô phỏng người dùng cho cả 20 câu hỏi mẫu: mở đúng trang, chọn đúng đợt và tuần, rồi
> tìm đáp án trên màn hình. Dashboard trả lời được cả 20 câu. Nhóm cũng đo từng trang khi mở lần đầu: 7 trên 8 trang tải
> trong khoảng 2,5 giây, chậm nhất là trang Cảnh báo 7,7 giây vì tính trên cả 27 nghìn sinh viên. Mở hết 8 trang chỉ quét
> khoảng 273 MB, nên hạn mức miễn phí của BigQuery đủ cho hơn 3.000 lượt như vậy mỗi tháng.
> Về giá trị nghiệp vụ, bảng này cho thấy quy tắc cảnh báo: ở tuần 4 danh sách ngắn mà 80,6% là đúng, phù hợp khi nguồn lực
> hỗ trợ có hạn; đến tuần 12 bắt được 45% số sinh viên sẽ rớt hoặc rút. Nhà trường chọn tuần cảnh báo tùy nguồn lực.

---

## Phần 6. Kết luận (24:30–25:30) — TV2

**Slide 25. Kết luận** (50 giây)
> Tóm lại, nhóm đã dựng được kho dữ liệu chạy lại bằng một lệnh, đúng trên ba nơi lưu, phục vụ 8 yêu cầu cho 4 nhóm người
> dùng, có cả batch và stream, và mọi lựa chọn đều có số đo.
> Hạn chế: stream là phát lại dữ liệu lịch sử; Kafka chỉ một broker; do gói Sandbox nên kho batch nạp lại toàn bộ, chưa
> có CDC; và star chậm hơn 3NF trên BigQuery dù quét cùng dữ liệu, nhóm chưa kiểm chứng được nguyên nhân.
> Hướng phát triển: CDC từ cơ sở dữ liệu vận hành qua Kafka, ghi stream bằng Storage Write API để độ trễ dưới một giây,
> và thử mô hình học máy cho cảnh báo sớm.

**Slide 26. Cảm ơn** (10 giây)
> Cảm ơn thầy cô và các bạn đã theo dõi. Mã nguồn và hướng dẫn chạy ở đường dẫn trên slide.

---

## Kiểm tra trước khi xuất video

- [ ] Tổng thời lượng 20–30 phút (nhắm 25).
- [ ] Không bỏ slide nào, thứ tự nói đúng thứ tự slide.
- [ ] Demo đủ 8 BR; mỗi BR có câu hỏi, thao tác, con số đọc được trên màn hình.
- [ ] Con số đọc trong video trùng với slide và báo cáo.
- [ ] Mỗi người nói khoảng 8–9 phút; có 3 đoạn hỏi đáp.
- [ ] File video và PDF đặt tên theo mã nhóm.
