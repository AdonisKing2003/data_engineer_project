# Chuẩn đầu ra → bằng chứng trong project

Mỗi chuẩn đầu ra của môn có ít nhất một tài liệu, một phần code và một con số đo được làm bằng chứng. Mọi con số
dưới đây chạy lại được bằng lệnh `make` ghi kèm, và phần lớn có test giữ cho nó đúng.

Theo đề cương, chuẩn 1.1 và 1.2 chấm qua tiểu luận và bài thi. Chuẩn 2.1 đến 3.2 chấm thêm qua thuyết trình, nên
mục cuối gợi ý slide và trang demo cho từng chuẩn.

## Tóm tắt

| Chuẩn đầu ra | Bằng chứng chính | Con số tiêu biểu |
|---|---|---|
| 1.1 Thiết kế CSDL ở mức ý niệm, luận lý, vật lý | [design_levels.md](design_levels.md), [contract.md](contract.md) | 8 thực thể → 5 dimension + 4 fact; 11 phụ thuộc hàm kiểm trên dữ liệu; cùng bảng click 42 MB / 516 MB / 816 MB trên Parquet / BigQuery / PostgreSQL |
| 1.2 Mô hình hóa từ quan hệ đến phi quan hệ | [data_models.md](data_models.md), [benchmark.md](benchmark.md) | 7 mô hình; bảng lồng quét ít hơn 33% nhưng tốn công tính toán gấp 14,4×; JSONB nhỏ hơn 7,4× nhưng chậm 2,9× ở câu hỏi cắt ngang |
| 2.1 Kiến trúc quản lý dữ liệu từ nhiều nguồn | [report_tv1.md](report_tv1.md) mục 1, 3 | 7 nguồn CSV, 4 tầng, 3 nơi lưu, 2 đường nạp batch và stream; `make all` 303 s |
| 2.2 Thiết kế kho dữ liệu | [design_levels.md](design_levels.md) mục 2, [benchmark.md](benchmark.md) | Constellation 4 fact; bảng ảnh chụp SV-tuần 1.342.949 dòng; star / 3NF / bảng rộng ở 1× và 5× |
| 3.1 Quản lý dữ liệu phức tạp | [report_tv1.md](report_tv1.md) mục 3, 5 | 3.810.465 dòng click trùng được gộp; 208 test; đảo nhãn không đổi danh sách cảnh báo 3.958 SV |
| 3.2 Xử lý dữ liệu theo kiểu mẫu hiện đại | [report_tv1.md](report_tv1.md) mục 4, 6, [optimization.md](optimization.md) | Stream khớp batch 0 lệch trên 1.342.949 dòng; tối ưu giảm 5,4× đến 330× |

---

## 1.1 Thiết kế CSDL ở mức ý niệm, luận lý, vật lý

| Mức | Bằng chứng | Ở đâu |
|---|---|---|
| Ý niệm | Sơ đồ thực thể nghiệp vụ: Học phần, Đợt học, Sinh viên, Bài kiểm tra, Học liệu, Đăng ký, Lần nộp, Lượt truy cập. Quy tắc nghiệp vụ rút ra ở mức này, như "nhóm tuổi thuộc về lượt đăng ký, không thuộc về sinh viên" (72 SV đổi nhóm tuổi) | [design_levels.md](design_levels.md) mục 1 |
| Luận lý | Star schema dạng constellation: 5 dimension, 4 fact, grain và khóa từng bảng; các quyết định (giữ khóa gốc, cờ thay vì xóa dòng, bảng SV-tuần không chứa nhãn) | [design_levels.md](design_levels.md) mục 2, [contract.md](contract.md) |
| Chuẩn hóa | Phụ thuộc hàm kiểm trên dữ liệu thật: `studentVle` chưa đạt 1NF (dòng trùng khóa), `studentInfo` vi phạm 2NF (`id_student` → thuộc tính SV). Tách theo phụ thuộc hàm ra bố trí 3NF, rồi phi chuẩn hóa có chủ đích ra star | [design_levels.md](design_levels.md) mục 2.4, `tests/test_staging.py` (11 test) |
| Vật lý | Ánh xạ kiểu dữ liệu trên 3 engine; kích thước từng bảng; khóa chính, phân vùng, gom cụm, chỉ mục | [design_levels.md](design_levels.md) mục 3, [optimization.md](optimization.md) |
| Truy vết 3 mức | Một bảng nối thực thể ý niệm → bảng luận lý → cách lưu vật lý | [design_levels.md](design_levels.md) mục 4 |

Code: `etl/02_clean_dims.py`, `etl/03_facts.py` (mức luận lý thành bảng), `etl/04_load_bq.py`, `etl/05_load_pg.py`
(mức vật lý). Test khóa chính, khóa ngoại: `tests/test_warehouse.py`, `tests/test_postgres.py`.

## 1.2 Mô hình hóa từ quan hệ đến phi quan hệ

| Mô hình | Hiện thực trong project | Số đo |
|---|---|---|
| Quan hệ 3NF | PostgreSQL `three_nf`, BigQuery `oulad_3nf` (TV3) | Bảng click nhỏ hơn star 24%; chậm hơn star 8–16% ở BR1, BR2 trên PostgreSQL |
| Mô hình chiều (star) | Kho chính BigQuery `oulad`, PostgreSQL `public` | Mốc so sánh |
| Bảng rộng phi chuẩn hóa | PostgreSQL `wide`, BigQuery `oulad_wide` (TV3) | Gấp đôi dung lượng; chậm nhất ở PostgreSQL 5× (BR2 1,56× star) |
| Lưu trữ theo cột | Parquet, BigQuery | BigQuery chỉ quét cột cần: star và 3NF quét đúng cùng số bytes |
| Dạng lồng | BigQuery `nested_student_timeline` (`ARRAY<STRUCT>`) | 97,7 MB so với 123,9 MB bảng phẳng; BR4 quét 53,0 MB so với 79,2 MB, nhưng slot ms tăng 14,4× |
| Tài liệu | PostgreSQL `doc.student_timeline` (JSONB) | 33,3 MB so với 247,3 MB; câu hỏi cắt ngang chậm 2,9× |
| Khóa-giá trị | State store của Spark Structured Streaming (khóa SV × đợt × tuần) | 885.466 lần cập nhật qua 44 micro-batch |

Kết luận của nhóm: chọn mô hình theo cách truy cập. Câu hỏi tổng hợp cắt ngang (6/8 yêu cầu nghiệp vụ) dùng star
lưu theo cột. Hồ sơ trọn vẹn một sinh viên hợp với tài liệu hoặc dạng lồng. Cập nhật theo khóa hợp với khóa-giá trị.
Mô hình đồ thị không dùng vì không câu hỏi nào cần duyệt quan hệ nhiều bước.

Chạy lại: `make models` (dạng lồng, tài liệu), `make bench` (3NF / star / bảng rộng, runner mới của TV3). Số liệu 3NF / star / bảng rộng ở bảng trên là của lần đo 26/10 (`bench/results/historical_2026-10-26/`).

## 2.1 Kiến trúc quản lý dữ liệu từ nhiều nguồn

| Thành phần kiến trúc | Bằng chứng |
|---|---|
| Nhiều nguồn có khóa và quy tắc khác nhau | 7 CSV: khóa ghép ở `studentInfo`, không có khóa ở `studentVle`, `"?"` là thiếu ở `imd_band`, ngày tương đối từ khai giảng ([report_tv1.md](report_tv1.md) mục 3.3) |
| Phân tầng | raw (CSV) → staging (Parquet, đặt kiểu) → kho (star) → phục vụ (BigQuery, mart cho app) ([report_tv1.md](report_tv1.md) mục 1.2) |
| Nhiều nơi lưu, mỗi nơi một vai trò | BigQuery là kho chính, PostgreSQL là kho đối chứng, Parquet + DuckDB để chạy tại máy |
| Hai đường nạp | Batch bằng Spark; stream bằng Spark Structured Streaming đọc click phát lại theo ngày |
| Đối soát giữa các nơi lưu | Số dòng khớp ở mọi bảng; 20 câu hỏi mẫu viết bằng SQL chung, ra cùng đáp án trên BigQuery, PostgreSQL, DuckDB |
| Tầng phục vụ tách khỏi nơi lưu | App đọc qua `app/data.py`, đổi BigQuery / DuckDB bằng một biến môi trường `DATA_BACKEND` |
| Chạy lại được ở mọi máy | Docker Compose; `make all` dựng lại toàn bộ trong 303 s ([etl_timing.md](etl_timing.md)) |

## 2.2 Thiết kế kho dữ liệu

| Khía cạnh | Bằng chứng |
|---|---|
| Mô hình chiều | Constellation: 4 fact (`fact_enrollment`, `fact_submission`, `fact_vle_daily`, `fact_student_week`) chia chung 5 dimension ([design_levels.md](design_levels.md) mục 2.2) |
| Grain rõ ràng | Mỗi fact ghi grain và có test khóa chính không trùng |
| Bảng ảnh chụp theo thời gian | `fact_student_week` (1.342.949 dòng): tuần `w` chỉ dùng dữ liệu tới hết tuần `w`, không chứa `final_result` |
| Chất lượng dữ liệu trong kho | Cờ `BOOL` thay vì xóa dòng (`deadline_imputed`, `is_late`, `result_inconsistent`...), số dòng TRUE của từng cờ có trong hợp đồng và được test |
| Tổng hợp sẵn cho app | Mart BR2, BR3 trên BigQuery ([tv3_marts.md](tv3_marts.md)); mart BR2 giảm bytes quét 330× ([optimization.md](optimization.md) ví dụ 3) |
| So sánh thiết kế | Star / 3NF / bảng rộng, 2 engine, 1× và 5×, 5 lần chạy mỗi ô ([benchmark.md](benchmark.md)). Không bố trí nào thắng ở mọi ô: trên BigQuery 5× star chậm hơn 3NF 2,5–4,5× về thời gian dù quét cùng bytes. Nhóm giữ star vì dễ viết SQL nhất và trên PostgreSQL nhanh hơn 3NF |
| Mở rộng quy mô | Kho 5× (`make scale`): mọi tỷ lệ giữ nguyên, nên dùng để kiểm SQL benchmark ra đúng |

## 3.1 Quản lý dữ liệu phức tạp

| Vấn đề | Cách xử lý | Bằng chứng |
|---|---|---|
| Dòng click trùng khóa | Gộp, cộng `sum_click`, ghi `n_records`: 10.655.280 → 8.459.320 dòng, tổng click giữ nguyên 39.605.099 | `tests/test_staging.py`, `tests/test_warehouse.py` |
| Giá trị thiếu, sai định dạng | `"?"` thành NULL; `imd_band` thiếu thành `'Unknown'` kèm cờ; `10-20` thành `10-20%` | [report_tv1.md](report_tv1.md) mục 3.3 |
| Hạn nộp thiếu | 11 bài thi lấy hạn = độ dài đợt, cờ `deadline_imputed` | [contract.md](contract.md) |
| Dữ liệu mâu thuẫn | 102 lượt có `final_result` và ngày rút không khớp: giữ lại, đánh cờ `result_inconsistent` | [contract.md](contract.md) |
| Rò rỉ nhãn | Bảng SV-tuần không có nhãn; test đảo toàn bộ `final_result` rồi chạy lại câu 14: danh sách 3.958 SV giữ nguyên, chỉ độ chính xác đổi | `tests/test_tv2_sql.py`, `tests/test_student_week.py` |
| Chạy lại không nhân đôi | Mọi bước ghi đè; test nạp hai lần vẫn đúng số dòng | `tests/test_pipeline.py` |
| Đúng trên nhiều engine | Cùng bộ số kiểm trên Parquet và PostgreSQL; 20 đáp án mẫu kiểm trên DuckDB | `tests/test_postgres.py`, `tests/test_questions.py` |
| Kiểm thử tổng | 208 test: kho, phụ thuộc hàm, SQL nghiệp vụ, đáp án mẫu, app | `make test` |

## 3.2 Xử lý dữ liệu theo kiểu mẫu hiện đại

| Kiểu mẫu | Bằng chứng |
|---|---|
| Xử lý phân tán | Spark 3.5 cho toàn bộ ETL batch và sinh kho 5× |
| Stream | Spark Structured Streaming, micro-batch, có trạng thái, `outputMode("update")`: 295 file ngày, 44 micro-batch, 97,5 s; so với batch lệch 0 trên 1.342.949 dòng ([report_tv1.md](report_tv1.md) mục 4) |
| Kho dữ liệu đám mây không máy chủ | BigQuery, tính tiền theo bytes quét |
| Lưu trữ theo cột | Parquet, BigQuery; DuckDB chạy SQL thẳng trên Parquet |
| Tối ưu có số đo | Phân vùng 16,8×, gom cụm 25,5×, bảng tổng hợp sẵn 330× (bytes quét BigQuery); chỉ mục 5,4× (thời gian PostgreSQL) ([optimization.md](optimization.md)) |
| Container, chạy một lệnh | Docker Compose; Makefile; `scripts/run_all.py` dừng ở bước lỗi đầu tiên và ghi thời gian từng bước |
| Phục vụ người dùng | Dashboard Streamlit chia theo vai trò, đọc BigQuery; test khói `tests/test_app.py` |

---

## Hạn chế cần nói trước khi bị hỏi

| Hạn chế | Ảnh hưởng tới chuẩn | Cách trả lời |
|---|---|---|
| Stream là phát lại dữ liệu lịch sử, không phải luồng thật; nguồn chỉ có ngày, không có giờ | 3.2 | Vẫn là xử lý stream thật (micro-batch, trạng thái, ghi tăng dần); không dùng Kafka để bớt một hệ thống phải vận hành |
| 7 nguồn đều thuộc một bộ dữ liệu | 2.1 | Các file có khóa, chất lượng và quy tắc ngày khác nhau, nên vẫn phải hợp nhất như nhiều nguồn |
| BigQuery Sandbox: bảng tự xóa sau 60 ngày, không cho `INSERT`/`UPDATE` | 2.1, 3.2 | Nạp lại toàn bộ mỗi lần, chưa nạp tăng dần |
| Bảng rộng 5× không dựng được trên BigQuery vì vượt hạn mức 10 GB | 1.2, 2.2 | So bảng rộng ở 1× trên BigQuery và ở 5× trên PostgreSQL |
| Star 5× trên BigQuery chậm hơn 3NF dù quét cùng bytes; giả thuyết là do cách tạo bảng, chưa kiểm được | 2.2 | So bằng bytes quét, chỉ số đáng tin trên BigQuery ([benchmark.md](benchmark.md)) |
| 3 trang của TV2 (`app/pages/`) vẫn đọc DuckDB qua `app/db.py`, chưa qua `app/data.py` | 2.1 | Demo các trang đó ở chế độ chạy tại máy |
| Kho 5× là bản sao, không thêm đa dạng thật | 2.2 | Dùng để đo tải, không dùng để rút kết luận nghiệp vụ |

## Gợi ý thuyết trình (chuẩn 2.1 đến 3.2)

| Chuẩn | Slide nên có | Một con số để nói | Trang demo |
|---|---|---|---|
| 2.1 | Sơ đồ luồng dữ liệu 4 tầng, 3 nơi lưu | 20 câu hỏi ra cùng đáp án trên 3 engine | Tổng quan (đổi `DATA_BACKEND`) |
| 2.2 | Sơ đồ constellation, grain 4 fact, bảng ảnh chụp SV-tuần | Ở 5× trên PostgreSQL, bảng rộng gấp đôi dung lượng và chậm gấp 1,56 lần star ở BR2 | Chất lượng & benchmark |
| 3.1 | Bảng vấn đề dữ liệu → cách xử lý; test chống rò rỉ nhãn | Đảo nhãn, danh sách cảnh báo vẫn 3.958 SV | Cảnh báo sớm & rút lui |
| 3.2 | Batch và stream; 4 ví dụ tối ưu | Stream lệch 0 dòng so với batch; mart giảm 330× | Hoạt động học tập (đọc mart BR2) |

## Câu hỏi thi nên ôn, và chỗ có ví dụ trong project

| Câu hỏi | Ví dụ |
|---|---|
| Khác nhau giữa 3 mức ý niệm, luận lý, vật lý? | [design_levels.md](design_levels.md) mục 4 |
| 1NF, 2NF, 3NF là gì; dữ liệu OULAD vi phạm dạng nào? | [design_levels.md](design_levels.md) mục 2.4 |
| Vì sao kho dữ liệu cố ý phi chuẩn hóa? Cái giá là gì? | [design_levels.md](design_levels.md) mục 2.4, [benchmark.md](benchmark.md) kết luận |
| Khi nào dùng 3NF, star, bảng rộng, dạng lồng, tài liệu, khóa-giá trị? | [data_models.md](data_models.md) mục 4 |
| Grain là gì; bảng ảnh chụp khác bảng giao dịch thế nào? | [design_levels.md](design_levels.md) mục 2, [contract.md](contract.md) |
| Rò rỉ nhãn là gì, kiểm bằng cách nào? | [report_tv1.md](report_tv1.md) mục 3.4 |
| Phân vùng, gom cụm, chỉ mục khác nhau thế nào; hợp với engine nào? | [optimization.md](optimization.md) |
| Batch khác stream thế nào; micro-batch, trạng thái, `outputMode`? | [report_tv1.md](report_tv1.md) mục 4 |
