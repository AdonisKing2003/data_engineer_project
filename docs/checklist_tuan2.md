# Checklist (18/10): kiểm việc tuần 2 của TV1, TV2, TV3

**Mốc kiểm tra cuối tuần 2 (18/10)** trong kế hoạch: trước khi sang tuần 3, cả nhóm phải đạt đủ 3 điều:
**(1)** `make test` xanh, **(2)** 20 câu hỏi mẫu chạy trên BigQuery ra đúng đáp án,
**(3)** các trang dashboard chạy được kịch bản demo. Chưa đạt thì tuần 3 chỉ sửa cho đủ, không làm thêm tính năng.

Mọi lệnh chạy ở thư mục repo trên máy thật. Đáp án lấy từ tài liệu "OULAD – Giai đoạn 2: Đặc tả 8 BR".
Số thập phân: tài liệu ghi dấu phẩy (96,5%), máy in dấu chấm (96.5) — coi là như nhau.

---

## 0. Chuẩn bị (TV1)

- [ ] Bật container: `docker compose up -d`
- [ ] Lấy code mới của 2 bạn về:
  ```bash
  git fetch origin && git branch -r          # xem nhánh của TV2, TV3
  git switch <tên-nhánh>                     # hoặc merge Pull Request vào main rồi git pull
  ```
- [ ] Kho còn đúng:
  ```bash
  docker compose exec app make test
  ```
  ✅ Đúng khi: dòng cuối `169 passed` (hoặc nhiều hơn nếu 2 bạn thêm test), không có `failed`.

## 1. Quy ước file (thống nhất với 2 bạn trước khi kiểm)

| Loại | Đường dẫn | Quy tắc |
|---|---|---|
| 20 câu hỏi mẫu | `sql/questions/q01.sql` … `q20.sql` | Mỗi file **một câu SELECT**. Dòng đầu là chú thích câu hỏi và đáp án chuẩn. Q1–Q4 TV1 đã viết sẵn làm mẫu |
| Truy vấn chính của BR | `sql/br1_submission.sql`, `sql/br2_vle_activity.sql`, … | Truy vấn mà trang dashboard dùng |
| Benchmark 3NF / bảng rộng | `sql/bench/` | Của TV3 (việc 3.7: dựng 3NF và bảng rộng trên PostgreSQL) |

Cả hai loại đều **không ghi tên dataset/schema** trước tên bảng (`FROM fact_enrollment`, không phải `FROM oulad.fact_enrollment`).
Công cụ `scripts/run_sql.py` tự chọn kho:

```bash
docker compose exec app python scripts/run_sql.py sql/questions/q05.sql                   # BigQuery 1× (mặc định)
docker compose exec app python scripts/run_sql.py sql/questions/q05.sql --engine pg       # PostgreSQL
docker compose exec app python scripts/run_sql.py sql/questions/q05.sql --engine duckdb   # Parquet trên máy
docker compose exec app python scripts/run_sql.py sql/questions/q05.sql --scale 5         # BigQuery 5×
```

Chạy cả 20 câu một lượt trên BigQuery:
```bash
for f in sql/questions/q*.sql; do echo "== $f"; docker compose exec -T app python scripts/run_sql.py "$f"; done
```

---

## 2. Hai mươi câu hỏi mẫu trên BigQuery (điều kiện chính của mốc kiểm tra cuối tuần 2)

| # | Ai | BR | Câu hỏi | Đáp án chuẩn | Đúng? |
|---|---|---|---|---|---|
| 1 | TV1 | Chung | Bao nhiêu lượt đăng ký, bao nhiêu SV? | 32.593 lượt; 28.785 SV | ✅ |
| 2 | TV1 | Chung | Tỷ lệ từng kết quả cuối kỳ? | Pass 37,9%; Withdrawn 31,2%; Fail 21,6%; Distinction 9,3% | ✅ |
| 3 | TV1 | Chung | Đợt nào đông SV nhất? | CCC 2014J, 2.498 lượt | ✅ |
| 4 | TV1 | Chung | Bao nhiêu lượt không có click VLE nào? | 3.365 lượt (10,3%) | ✅ |
| 5 | TV2 | BR1 | Tỷ lệ nộp bài 1752 của AAA 2013J? | 96,5% (359 / 372) | [ ] |
| 6 | TV2 | BR1 | TMA nào của BBB 2014J nộp trễ nhiều nhất? | Bài 15023 (hạn ngày 152), 22,1% | [ ] |
| 7 | TV2 | BR1 | Tỷ lệ nộp trễ chung của mọi TMA? | 16,8% (16.320 bài) | [ ] |
| 8 | TV2 | BR1 | Môn nào có điểm TMA trung bình cao nhất, thấp nhất? | Cao nhất EEE (81,2); thấp nhất GGG (68,5) | [ ] |
| 9 | TV3 | BR2 | Loại học liệu nào được click nhiều nhất? | oucontent, 11.206.803 click (28,3%) | [ ] |
| 10 | TV3 | BR2 | Tuần nào có tổng click cao nhất? | Tuần 2, 2.307.080 click | [ ] |
| 11 | TV3 | BR2 | FFF 2014J tuần 0: click trung bình mỗi SV còn học? | 119,2 click (255.054 / 2.140) | [ ] |
| 12 | TV3 | BR3 | BR3 tính được cho bao nhiêu đợt, vì sao không đủ 22? | 19 đợt; GGG không có TMA có trọng số > 0 | [ ] |
| 13 | TV3 | BR3 | Spearman click trước hạn vs điểm TMA đầu tiên, AAA 2013J? | ρ = 0,37 (n = 358) | [ ] |
| 14 | TV2 | BR4 | Tuần 4, mọi đợt: bao nhiêu SV vào danh sách nguy cơ, bao nhiêu % thật sự rớt/rút? | 3.958 SV; 80,6% (tỷ lệ nền 43,5%) | [ ] |
| 15 | TV2 | BR5 | Bao nhiêu % lượt Withdrawn rút từ ngày 0 trở về trước? | 30,4% (3.089 / 10.156) | [ ] |
| 16 | TV2 | BR5 | Ngày rút trung vị của SV Withdrawn? | Ngày 27 | [ ] |
| 17 | TV2 | BR5 | Đợt nào có tỷ lệ Withdrawn cao nhất? | CCC 2014B, 46,4% | [ ] |
| 18 | TV3 | BR6 | 2014J (BBB, DDD, FFF): IMD 90–100% đạt cao hơn IMD 0–10% bao nhiêu điểm %? | 22,2 điểm (63,3% so với 41,1%) | [ ] |
| 19 | TV2 | BR7 | AAA 2014J tuần 10: trung vị tổng click từ đầu đợt của SV còn học? | 593 click (336 SV) | [ ] |
| 20 | TV3 | BR8 | BBB 2013J tuần 5: nhóm đạt có trung vị bao nhiêu click vào diễn đàn? | 5 click (1.072 SV). Bỏ câu này nếu nhóm đã quyết định cắt BR8 (mốc 15/10) | [ ] |

Kết quả: ____ / 20 câu đúng (hoặc ____ / 19 nếu cắt BR8).

Câu nào sai, kiểm theo thứ tự: (1) có lọc SV rút trước khai giảng (`withdrawn_before_start`) đúng như Phụ lục chưa;
(2) có bỏ bài chuyển điểm (`is_banked`) chưa; (3) tuần có tính bằng `FLOOR(date / 7)` chưa (không dùng `DIV` hay `//`);
(4) bài thi dùng `deadline` (đã điền) hay `deadline_raw`.

---

## 3. TV2: BR1, BR4, BR5, BR7 và trang Cảnh báo

| Việc | Hạn | Kiểm bằng | ✅ Đúng khi | Xong? |
|---|---|---|---|---|
| 2.4 BR4 danh sách nguy cơ | 13/10 | Chạy `sql/br4_*.sql` cho DDD 2014J tuần 4 | 1.459 SV còn học / 161 vào danh sách; độ chính xác 90,1%, tỷ lệ nền 45,7%. Tuần 8 mọi đợt: 4.598 SV, 84,6%, độ bao phủ 35,6% | [ ] |
| 2.5 BR1, BR5 trên BigQuery | 14/10 | Câu 5–8, 15–17 ở mục 2 | Đúng hết. Thêm: BBB 2014J (2.292 lượt) đã rút đến ngày 0 / 27 / cuối đợt = 10,5% / 22,0% / 32,1% | [ ] |
| 2.6 Slide schema kho | 15/10 | TV1 đọc slide | Có: Kimball, grain 4 fact, constellation, snapshot as-of, junk dimension. Tên bảng, cột khớp `docs/contract.md`. **TV1 duyệt** | [ ] |
| 2.7 BR4, BR7 trên BigQuery + test rò rỉ | 16/10 | Câu 14, 19; `docker compose exec app make test` | Đúng đáp án; có test "đổi `final_result` thì danh sách tuần 4 không đổi" chạy xanh (bản tham chiếu: `tests/test_student_week.py`) | [ ] |
| 2.8 Trang Cảnh báo + BR1, BR7 | 18/10 | Mục 5 bên dưới | Chạy được kịch bản demo 2 phút của BR1, BR4, BR5, BR7 | [ ] |

Kịch bản demo cần ra đúng số:
- **BR1** (BBB 2014J, TMA): tỷ lệ trễ 9,1% (bài đầu) → 22,1% (bài thứ ba) → 12,8%; điểm trung vị quanh 68–70; đổi sang CMA thì cột trễ biến mất kèm dòng giải thích.
- **BR4** (DDD 2014J, tuần 4): 1.459 / 161; mở một SV thấy ô dấu hiệu nào đang bật.
- **BR5** (BBB 2014J): 10,5% → 22,0% → 32,1%; chồng CCC 2014B (46,4%).
- **BR7** (AAA 2014J, tuần 10): nhóm 336 SV; phân vị 269 / 593 / 1.083; lùi về tuần 5 thì số đổi.

## 4. TV3: BR2, BR3, BR6, BR8, 3NF và các trang Học phần, Khoa, Sinh viên

| Việc | Hạn | Kiểm bằng | ✅ Đúng khi | Xong? |
|---|---|---|---|---|
| 3.2 Khung app 5 trang | 09/10 | `docker compose exec app make app` → http://localhost:8501 | Mở được 5 trang: Học phần, Cảnh báo, Khoa, Sinh viên, Chất lượng & benchmark | [ ] |
| 3.5 BR2, BR3, BR6 trên BigQuery | 14/10 | Câu 9–13, 18 ở mục 2 | Đúng hết. Thêm BR3: BBB 2014J n = 1.585, ρ = 0,16, khoảng tin cậy 0,11–0,21, bài 15021; EEE 2014J n = 911, ρ = 0,41; tổng 19 đợt, 21.693 SV. BR6: bảng 4 kỳ ở mục dưới | [ ] |
| 3.6 BR8 (nếu giữ) | 15/10 | Câu 20 | BBB 2013J: 1.072 SV; tuần 5 forumng trung vị / 25% / 75% = 5 / 0 / 22. Không có cụm từ "để đạt", "giúp bạn", "làm tăng", "do đó" | [ ] |
| 3.7 3NF + bảng rộng trên PostgreSQL | 17/10 | `docker compose exec postgres psql -U oulad -d oulad -c '\dn'` rồi chạy 4 truy vấn trong `sql/bench/` | Có 2 schema mới (ngoài `public`, `x5`). BR1, BR2, BR4, BR6 chạy được trên cả 3 schema (star, 3NF, bảng rộng) và **ra cùng kết quả** | [ ] |
| 3.8 Trang Học phần, Khoa, Sinh viên | 18/10 | Mục 5 bên dưới | Chạy được kịch bản demo BR2, BR3, BR6 (BR8 nếu giữ), đọc từ BigQuery | [ ] |

BR6 (BBB, DDD, FFF; bỏ SV rút trước khai giảng):

| Kỳ | IMD 0–10%: n; đạt; Distinction | IMD 90–100%: n; đạt; Distinction | Khoảng cách đạt |
|---|---|---|---|
| 2013B | 468; 31,2%; 4,7% | 322; 56,5%; 13,4% | 25,3 điểm |
| 2013J | 581; 39,4%; 5,2% | 439; 63,8%; 14,4% | 24,4 điểm |
| 2014B | 411; 39,2%; 4,4% | 282; 62,1%; 15,6% | 22,9 điểm |
| 2014J | 615; 41,1%; 4,6% | 436; 63,3%; 16,3% | 22,2 điểm |

Kịch bản demo cần ra đúng số:
- **BR2** (FFF 2014J): tuần 0 mỗi SV 119,2 click; forumng 38,5, oucontent 25,4; có vạch dọc ở tuần có hạn TMA (3, 7, 13, 19, 28).
- **BR3**: forest plot 19 đợt, ρ từ 0,16 đến 0,41; có dòng "tương quan, không phải nhân quả"; chọn GGG thì báo "không có TMA có trọng số".
- **BR6**: biểu đồ quả tạ 4 kỳ, khoảng cách 25,3 → 22,2 điểm; đổi sang Distinction thì 8,7 → 11,7 điểm.
- **BR8** (BBB 2013J, tuần 5): forumng 5 / 0–22 click, câu mô tả không hàm ý nhân quả.

---

## 5. Kiểm dashboard (cả hai)

- [ ] `docker compose exec app make app`, mở http://localhost:8501
- [ ] App đọc từ **BigQuery**, không còn đọc CSV hay DuckDB (việc 3.2 ghi: tuần 2 đổi sang BigQuery)
- [ ] Mỗi BR chạy hết kịch bản demo 2 phút ở mục 3, 4 và **ra đúng số**
- [ ] Một người **khác** người viết trang chạy thử được kịch bản (tiêu chí "BR xong" trong kế hoạch)

## 6. Mốc và quyết định còn treo

- [ ] **Mốc 15/10, giữ hay cắt BR8:** nếu BR1–BR7 chưa khớp trên BigQuery thì cắt BR8. Nhóm đã chọn: ________
- [ ] **Họp khởi động (07/10), phần còn treo:** đã chốt quyết định 1 (ẩn ô dưới 30 SV) và quyết định 5
  (BR6 chỉ xét IMD trên BBB, DDD, FFF), và cả 3 người đã ghi tên vào bảng duyệt 8 BR trong tài liệu đặc tả
- [ ] (Tùy chọn) So view `student_week` của TV2 với `fact_student_week`: cùng 3 số của BR7 tuần 10 AAA 2014J là đủ

## 7. Kết luận mốc kiểm tra cuối tuần 2

| Điều kiện | Kết quả |
|---|---|
| `make test` xanh | [ ] |
| 20 câu hỏi mẫu (hoặc 19) đúng trên BigQuery | ____ / 20 |
| Kịch bản demo các BR chạy được | [ ] |

- **Qua hết:** sang tuần 3. TV1 bắt đầu việc 1.11 (4 ví dụ tối ưu có số đo) trên các file `sql/br*.sql`,
  TV3 bắt đầu việc 3.9 (chạy benchmark) trên kho 1× và 5×.
- **Chưa qua:** tuần 3 chỉ sửa cho đủ, không thêm tính năng. Ghi lại câu nào sai, ai sửa, hạn sửa: ________
