# Task 3.8 — kết quả triển khai và kiểm chứng ngày 27/10/2026

**Kết quả kỹ thuật: ĐẠT.** Các trang Học phần, Khoa và Sinh viên đã chạy qua AppTest trên dữ liệu BigQuery thật cho BR2, BR3, BR6 và BR8. Thành viên khác trong nhóm vẫn cần chạy kịch bản thủ công ở cuối tài liệu để xác nhận bàn giao; chưa có chữ ký hoặc buổi demo của người đó.

Bản gốc kiểm tra là `main` tại `3721511`, cộng các thay đổi task 3.8 trong working tree. Môi trường: Docker 29.5.3, Python 3.11.17, Streamlit 1.65.0, DuckDB 1.5.6; BigQuery dataset `oulad`, vùng US. Báo cáo này cập nhật bằng chứng ngày 27/10, thay cho nhận định “chưa tạo mart/chưa có parity BigQuery” trong báo cáo tiến độ ngày 20/10.

## 1. Thay đổi

- Sửa kiểm tra khóa ghép trong `scripts/build_tv3_marts.py`: dùng `COUNT(DISTINCT TO_JSON_STRING(STRUCT(...)))` để BigQuery kiểm grain được. Từ chối snapshot rỗng, trùng grain hoặc lệch số dòng metadata.
- Mở rộng `scripts/validate_tv3_marts.py`: so sánh cả mẫu số và hai chỉ số trung bình BR2; kiểm đủ danh sách offering, mốc TMA theo offering và hai oracle FFF/BBB; đối chiếu thêm BR6 và BR8 giữa DuckDB–BigQuery.
- BR3 ghi rõ “Tương quan, không phải nhân quả”. BR8 dùng nhãn hover “Click” cho cả hai đầu dải phân vị.
- Thêm `tests/test_tv3_task38.py`: mở `Home.py` thật, chuyển trang qua navigation đã đăng ký, kiểm dữ liệu và nội dung biểu đồ. Mặc định test dùng DuckDB; phải đặt `RUN_TV3_BIGQUERY_DEMO=1` để chạy BigQuery.

## 2. Mart và đối chiếu dữ liệu đã chạy

Đã chạy `scripts/build_tv3_marts.py --dry-run`, sau đó `--apply`. Hai bảng nguồn star chỉ được đọc; lệnh refresh thay hai mart `tv3_*` đã khai báo trong builder.

| Mart | Dòng | Khóa grain duy nhất | Timestamp snapshot (UTC) | Thời gian tạo bảng phía client | Bytes xử lý khi tạo bảng |
|---|---:|---:|---|---:|---:|
| `tv3_br2_weekly_mart` | 16.340 | 16.340 | 2026-10-27 10:17:59.146058 | 9,38 giây | 363,9 MiB |
| `tv3_br3_student_mart` | 21.693 | 21.693 | 2026-10-27 10:18:10.866559 | 5,69 giây | 294,6 MiB |

Sau refresh, validator chạy `--engine both` và đạt **24 kiểm tra**. Phạm vi gồm 22 offering, 16.340 dòng BR2, 106 mốc offering–tuần TMA, 21.693 cặp BR3, 19 dòng tóm tắt BR3, 4 dòng BR6 và 1 dòng tổng hợp BR8. Mọi lát cắt dashboard BR2/BR3 đều được so với kết quả raw cùng backend; BR2/BR3, summary, TMA, BR6 và BR8 được so tiếp giữa hai backend.

Bằng chứng: [CSV parity](validation/task38_2026-10-27_parity.csv). CSV chỉ chứa tên kiểm tra, số dòng và hash; không xuất mã hay dữ liệu từng sinh viên. Các hash riêng từng backend có thể khác do biểu diễn số nguyên/số thực; kết luận parity dựa trên so sánh cột, khóa, NULL, giữ dòng trùng và sai số số thực tuyệt đối `1e-8`.

Trong 24 kiểm tra có hai lượt DuckDB “raw versus mart” là chạy lại cùng SQL nguồn làm baseline; Parquet không lưu mart vật lý. Đối chiếu mart vật lý thực sự diễn ra trên BigQuery; các kiểm tra lát cắt dashboard và đối chiếu hai backend cung cấp bằng chứng còn lại. Với BR6/BR8, nhánh `--engine both` mới so sánh giá trị hai backend; chạy một backend riêng chỉ kiểm đầu ra/grain, cần chạy thêm AppTest có oracle để xác nhận nghiệp vụ.

Dry-run bốn truy vấn nguồn ước lượng tổng 1.073.666.786 bytes. Đây là ước lượng nguồn cho preflight; các lần đọc mart, selector và dashboard sau đó là phần bổ sung. `--max-bq-bytes` không phải trần tổng bytes của toàn phiên kiểm tra.

## 3. Kiểm thử giao diện đã chạy

| Lượt chạy | Kết quả | Hiện vật |
|---|---|---|
| DuckDB: bộ task 3.8 và hai file regression TV3 hiện có | 26 passed, 104,96 giây | [JUnit local](validation/task38_2026-10-27_duckdb.xml) |
| Guard kiểm snapshot mart: rỗng, trùng grain, lệch metadata và snapshot hợp lệ | 4 passed, 0,28 giây | [JUnit guard mart](validation/task38_2026-10-27_mart_build.xml) |
| BigQuery: bộ task 3.8, không mock dữ liệu/backend | 4 passed, 78,95 giây | [JUnit BigQuery](validation/task38_2026-10-27_bigquery.xml) |
| Streamlit đang phục vụ dashboard | Endpoint `/_stcore/health` trả `ok` | `http://localhost:8501` |

Các oracle và hành vi được kiểm tra:

| BR | Kết quả kiểm tra |
|---|---|
| BR2 | FFF 2014J tuần 0: 2.140 SV, 255.054 click, 119,2 click/SV; forumng 38,5 và oucontent 25,4. Heatmap tỷ trọng, đường top 5 và mốc TMA 3/7/13/19/28 khớp dữ liệu. |
| BR3 | Forest plot có 19 kỳ, tổng n = 21.693; AAA 2013J n = 358, rho làm tròn 0,37 và khoảng tin cậy Fisher. Scatter dùng trục log với `1 + click`, giữ các cặp zero-click tại x = 1. Chọn GGG hiện giải thích không có TMA có trọng số. |
| BR6 | Biểu đồ quả tạ cho 4 kỳ. Năm 2014J: 41,1% và 63,3%, chênh 22,2 điểm phần trăm. Đổi sang Distinction: 4,6% và 16,3%, chênh 11,7 điểm. |
| BR8 | BBB 2013J tuần 5, nhóm Pass/Distinction: n = 1.072; Q1/trung vị/Q3 = 0/5/22 click. Các thẻ số và dải phân vị khớp. |

Lượt local đầu tiên phát hiện hai lỗi trong test mới: chưa giải mã typed array của Plotly 6 và dùng nhầm số zero-click toàn bộ kỳ cho riêng AAA. Đã sửa đúng phạm vi; các JUnit liên kết phía trên là lượt chạy cuối thành công. Không có lỗi dữ liệu ứng dụng tương ứng được suy ra từ hai lỗi test này.

Đây là kiểm thử giao diện tự động bằng Streamlit AppTest, không phải buổi demo thủ công bởi thành viên khác. Không suy ra M3 đã đạt hoặc toàn bộ bộ test sau merge đã xanh từ các lượt focused này.

## 4. Chạy lại

Các lệnh dưới đây dùng container `app` đã chạy, với `.env` và credentials hợp lệ:

```powershell
docker compose exec -T app python scripts/build_tv3_marts.py --dry-run
docker compose exec -T app python scripts/build_tv3_marts.py --apply
docker compose exec -T app python scripts/validate_tv3_marts.py --engine both --report docs/validation/task38_2026-10-27_parity.csv
docker compose exec -T app python -m pytest -q tests/test_tv3_task38.py tests/test_tv3_dashboard.py tests/test_tv3_feedback.py
docker compose exec -T app python -m pytest -q tests/test_tv3_mart_build.py
docker compose exec -T -e RUN_TV3_BIGQUERY_DEMO=1 app python -m pytest -q tests/test_tv3_task38.py
docker compose exec app make app
```

Để chạy trên Parquet cục bộ, đặt rõ `DATA_BACKEND=duckdb`. Dashboard TV3 mặc định dùng BigQuery và không tự đổi backend khi truy vấn lỗi.

## 5. Kịch bản demo bàn giao cho thành viên khác

- [ ] Ghi tên người chạy, commit được chạy và thời điểm: ____________________.
- [ ] Mở Học phần → BR2 → FFF/2014J, tuần 0. Đọc các thẻ số theo bảng oracle, kiểm heatmap/top 5 và vạch TMA. Chuyển BBB/2014J: các vạch phải thành 2/7/15/21/28; đổi tuần và kiểm thẻ số thay đổi.
- [ ] Học phần → BR3: xem forest 19 kỳ, chọn AAA/2013J và đọc n/rho/khoảng tin cậy; xác nhận trục log giữ cả zero-click. Chọn GGG để đọc lý do không tính được tương quan. Giải thích vì sao không kết luận nhân quả.
- [ ] Khoa → BR6: đọc bốn kỳ và khoảng cách 2014J 22,2 điểm; đổi sang Distinction để đọc khoảng cách 11,7 điểm. Phân biệt lượt đăng ký dùng làm mẫu số với số sinh viên duy nhất dùng cho ngưỡng ẩn nhóm.
- [ ] Sinh viên → BR8: đọc n = 1.072 và 0/5/22 click; giải thích đây là phân bố của nhóm đã đạt, có tính người không click.
- [ ] Người chạy xác nhận các trang TV3 đọc BigQuery, ghi lỗi hoặc ký duyệt: ____________________.

Các trang TV2 hiện vẫn dùng adapter DuckDB riêng. Việc chuyển backend cho các trang đó, nghiệm thu 20 câu hỏi của cả nhóm và demo toàn ứng dụng thuộc cổng tích hợp M3.
