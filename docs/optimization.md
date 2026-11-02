# Tối ưu truy vấn (việc 1.11)

Đo lúc 26/10/2026 15:53. Mỗi truy vấn chạy 5 lần, thời gian lấy trung vị; BigQuery tắt cache kết quả.
File này do `scripts/optimize.py` tự sinh; chạy lại `make optimize` để cập nhật.
Mỗi ví dụ đều so kết quả trước/sau tối ưu, hai bên phải ra giống hệt.

## Tóm tắt

| # | Kỹ thuật | Engine | Truy vấn | Chỉ số | Trước | Sau | Giảm |
|---|---|---|---|---|---:|---:|---:|
| 1 | Phân vùng `fact_student_week` theo `week_no` | BigQuery | BR4 tuần 4 | bytes quét | 79.2 MB | 4.7 MB | 16.8× |
| 2 | Gom cụm `fact_vle_daily` theo module, kỳ | BigQuery | click 1 đợt theo tuần × loại | bytes quét | 304.6 MB | 12.0 MB | 25.5× |
| 3 | Bảng tổng hợp sẵn cho app (mart BR2) | BigQuery | biểu đồ BR2 của 1 đợt | bytes quét | 381.6 MB | 1.2 MB | 330.1× |
| 4 | Chỉ mục trên `fact_vle_daily` | PostgreSQL | như ví dụ 2 | thời gian | 400.1 ms | 73.6 ms | 5.4× |

Với BigQuery, bytes quét là chỉ số chính: tiền và hạn mức 1 TB/tháng tính theo bytes. Thời gian ở
cỡ dữ liệu này (dưới 1 GB) chủ yếu là chi phí khởi động job nên chênh ít và dao động giữa các lần chạy.
Bytes tính tiền (`billed`) tối thiểu 10 MB cho mỗi bảng được đọc, nên ở bảng nhỏ nó cao hơn bytes quét.

## 1. Phân vùng `fact_student_week` theo `week_no` (BigQuery)

**Truy vấn:** [sql/optimize/br4_week4.sql](../sql/optimize/br4_week4.sql), danh sách nguy cơ BR4 tại tuần 4
trên mọi đợt (câu 14). Trang Cảnh báo luôn hỏi theo một tuần cụ thể, nên phân vùng theo tuần khớp với cách app đọc.

**Thay đổi:** tạo bảng phân vùng theo khoảng số nguyên, mỗi tuần một phân vùng (43 phân vùng, tuần −4 đến 38):

```sql
CREATE OR REPLACE TABLE `oulad.opt_fact_student_week_part`
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(-4, 39, 1))
AS SELECT * FROM `oulad.fact_student_week`
```

Tạo bảng mất 4.5 s, quét 123.9 MB.

| Bảng | Truy vấn | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |
|---|---|---:|---:|---:|---:|---:|
| Bảng gốc | lọc tuần qua phép nối | 79.2 MB | 79.7 MB | 2,718,491 | 701 | 0.37 |
| Bảng gốc | thêm `p.week_no = 3` | 79.2 MB | 79.7 MB | 2,718,491 | 202 | 0.24 |
| Phân vùng | lọc tuần qua phép nối | 79.2 MB | 79.7 MB | 1,408,135 | 360 | 0.28 |
| Phân vùng | thêm `p.week_no = 3` | 4.7 MB | 21.0 MB | 97,779 | 52 | 0.20 |

Kết quả 4 lần chạy: giống hệt (27,250 lượt còn học, 3,958 vào danh sách, độ chính xác 80.6%).

**Đọc kết quả:**

- Truy vấn ghép `fact_student_week` với chính nó để lấy click tuần trước (`p.week_no = w.week_no - 1`).
  Điều kiện này chỉ biết giá trị khi chạy phép nối, nên BigQuery không dùng nó để bỏ phân vùng.
  Trên bảng phân vùng, phía `w` (`w.week_no = 4`) đã chỉ đọc tuần 4 nên số dòng đọc giảm gần một nửa,
  nhưng phía `p` vẫn đọc cả bảng nên bytes quét không giảm.
- Thêm điều kiện hằng số `p.week_no = 3` (không đổi kết quả) thì cả hai phía chỉ đọc đúng 1 phân vùng.
  Bài học: phân vùng chỉ có tác dụng khi truy vấn lọc cột phân vùng bằng hằng số hoặc tham số.
- Trên bảng gốc chưa phân vùng, thêm điều kiện đó không giảm bytes: BigQuery vẫn phải đọc cả cột.

**Đánh đổi:** Google khuyên mỗi phân vùng nên lớn (cỡ từ 1 GB); ở đây mỗi phân vùng chỉ vài MB nên
phân vùng là để minh họa, ở cỡ thật nên cân nhắc gom cụm theo `week_no` thay vì phân vùng.
Mỗi lần nạp lại kho phải tạo lại bảng (hoặc cho `04_load_bq.py` nạp thẳng vào bảng có phân vùng).

## 2. Gom cụm `fact_vle_daily` theo `code_module`, `code_presentation` (BigQuery)

**Truy vấn:** [sql/optimize/vle_offering_week.sql](../sql/optimize/vle_offering_week.sql), click theo tuần ×
loại hoạt động của BBB 2014J. Đây là phần nặng nhất của trang Học phần (BR2) khi người dùng chọn một đợt.

**Thay đổi:** sắp dữ liệu theo module, kỳ khi ghi để các khối lưu trữ của một đợt nằm cạnh nhau:

```sql
CREATE OR REPLACE TABLE `oulad.opt_fact_vle_daily_clust`
CLUSTER BY code_module, code_presentation
AS SELECT * FROM `oulad.fact_vle_daily`
```

Tạo bảng mất 7.2 s, quét 516.0 MB.

| | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |
|---|---:|---:|---:|---:|---:|
| Bảng gốc | 304.6 MB | 305.1 MB | 8,465,684 | 156 | 0.24 |
| Gom cụm | 12.0 MB | 21.0 MB | 335,383 | 37 | 0.18 |

Kết quả: giống hệt (366 dòng).

**Đọc kết quả:** bảng gốc phải đọc 5 cột của cả 8,5 triệu dòng rồi mới lọc. Bảng gom cụm cho BigQuery
bỏ qua các khối không chứa BBB 2014J nên chỉ đọc khoảng 1/22 bảng (22 đợt). Khác phân vùng, gom cụm không
cần cột kiểu ngày/số và không giới hạn số giá trị, hợp với cột chuỗi như mã module, mã kỳ.

**Đánh đổi:** bytes ước tính trước khi chạy (dry run) không tính được phần bỏ qua nhờ gom cụm, chỉ biết sau
khi chạy. Truy vấn không lọc theo module, kỳ (ví dụ tổng click toàn kho) không được lợi gì.

## 3. Bảng tổng hợp sẵn cho app: mart BR2 (BigQuery)

**Truy vấn:** biểu đồ BR2 của trang Học phần cho BBB 2014J (tham số `@code_module`, `@code_presentation`).

- Trước: tính từ kho star bằng [sql/bigquery/br2_vle_weekly.sql](../sql/bigquery/br2_vle_weekly.sql)
  (ghép `fact_vle_daily`, `fact_enrollment`, `dim_vle_site`, lịch tuần) rồi lọc đợt.
- Sau: đọc [sql/bigquery/br2_dashboard.sql](../sql/bigquery/br2_dashboard.sql) từ bảng `tv3_br2_weekly_mart`
  đã tính sẵn một lần bằng `python scripts/build_tv3_marts.py --apply` (mart do TV3 thiết kế, xem
  [docs/tv3_marts.md](tv3_marts.md)).

Mart có 16,340 dòng, 1.9 MB.

| | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |
|---|---:|---:|---:|---:|---:|
| Tính từ kho star | 381.6 MB | 381.7 MB | 17,043,117 | 22,749 | 2.63 |
| Đọc mart | 1.2 MB | 10.5 MB | 16,340 | 6 | 0.19 |

Kết quả: giống hệt (760 dòng, so trên các cột trang Học phần dùng).

**Đọc kết quả:** mỗi lần người dùng đổi đợt, app chỉ đọc mart 16,340 dòng đã tính sẵn thay vì
ghép lại 8,5 triệu dòng click với bảng đăng ký và lịch tuần. Chi phí tính được trả một lần lúc dựng mart.
Mart chưa gom cụm theo module, kỳ nên vẫn đọc cả mart; ở cỡ này không đáng làm thêm.

**Đánh đổi:** mart phải dựng lại sau mỗi lần nạp kho, nếu quên thì app hiện số cũ; mart chỉ trả lời đúng
các câu hỏi đã thiết kế trước (grain đợt × tuần × loại hoạt động).

## 4. Chỉ mục PostgreSQL trên `fact_vle_daily`

**Truy vấn:** giống ví dụ 2, chạy trên schema `public`.

**Thay đổi:** khóa chính hiện có bắt đầu bằng `id_student` nên không giúp lọc theo đợt. Thêm chỉ mục bắt
đầu bằng module, kỳ, và kèm (`INCLUDE`) hai cột truy vấn cần để PostgreSQL đọc thẳng từ chỉ mục, không
phải mở bảng:

```sql
CREATE INDEX ix_fact_vle_daily_offering ON fact_vle_daily
    (code_module, code_presentation, week_no) INCLUDE (id_site, sum_click);
VACUUM (ANALYZE, PARALLEL 0) fact_vle_daily;
```

Tạo chỉ mục + VACUUM mất 16.1 s. Chỉ mục chiếm 498.9 MB (bảng 855.5 MB).

| | Thời gian (ms) | Cách quét `fact_vle_daily` |
|---|---:|---|
| Không chỉ mục | 400.1 | `Parallel Seq Scan on fact_vle_daily v; Buffers: shared hit=8607 read=95830` |
| Có chỉ mục | 73.6 | `Parallel Index Only Scan using ix_fact_vle_daily_offering on fact_vle_daily v; Buffers: shared hit=2794` |

Kết quả: giống hệt. Thời gian đo phía client, sau một lần chạy nóng.

**Đọc kết quả:** không có chỉ mục thì PostgreSQL quét tuần tự cả bảng để lấy các dòng của một đợt trong 22.
Bảng lớn hơn bộ đệm `shared_buffers` nên dù đã chạy nóng, phần lớn trang vẫn phải đọc từ ngoài (`read=` trong
`Buffers`). Có chỉ mục thì PostgreSQL nhảy thẳng tới đoạn của BBB 2014J, đọc ít trang hơn hẳn và không mở bảng
(`Index Only Scan`).

**Đánh đổi:** tốn thêm dung lượng và làm chậm lúc nạp dữ liệu. `make load-pg` tạo lại bảng nên chỉ mục mất,
chạy lại `make optimize` để có lại. Khi so benchmark star / 3NF / bảng rộng cần ghi rõ có chỉ mục này hay không.

## Kế hoạch truy vấn PostgreSQL đầy đủ

<details><summary>Không chỉ mục</summary>

```
Finalize GroupAggregate  (cost=160163.49..160392.12 rows=860 width=48) (actual time=376.684..382.686 rows=366 loops=1)
  Group Key: v.week_no, s.activity_type
  Buffers: shared hit=8789 read=95830
  ->  Gather Merge  (cost=160163.49..160364.17 rows=1720 width=48) (actual time=376.646..382.267 rows=1085 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=8789 read=95830
        ->  Sort  (cost=159163.46..159165.61 rows=860 width=48) (actual time=358.643..358.668 rows=362 loops=3)
              Sort Key: v.week_no, s.activity_type
              Sort Method: quicksort  Memory: 50kB
              Buffers: shared hit=8789 read=95830
              Worker 0:  Sort Method: quicksort  Memory: 50kB
              Worker 1:  Sort Method: quicksort  Memory: 50kB
              ->  Partial HashAggregate  (cost=159110.79..159121.54 rows=860 width=48) (actual time=358.305..358.390 rows=362 loops=3)
                    Group Key: v.week_no, s.activity_type
                    Batches: 1  Memory Usage: 105kB
                    Buffers: shared hit=8757 read=95830
                    Worker 0:  Batches: 1  Memory Usage: 105kB
                    Worker 1:  Batches: 1  Memory Usage: 105kB
                    ->  Hash Join  (cost=193.19..157918.87 rows=158923 width=24) (actual time=12.573..331.859 rows=109673 loops=3)
                          Hash Cond: (v.id_site = s.id_site)
                          Buffers: shared hit=8757 read=95830
                          ->  Parallel Seq Scan on fact_vle_daily v  (cost=0.00..157308.23 rows=158923 width=24) (actual time=10.652..304.908 rows=109673 loops=3)
                                Filter: ((code_module = 'BBB'::text) AND (code_presentation = '2014J'::text))
                                Rows Removed by Filter: 2710100
                                Buffers: shared hit=8607 read=95830
                          ->  Hash  (cost=113.64..113.64 rows=6364 width=16) (actual time=1.889..1.890 rows=6364 loops=3)
                                Buckets: 8192  Batches: 1  Memory Usage: 394kB
                                Buffers: shared hit=150
                                ->  Seq Scan on dim_vle_site s  (cost=0.00..113.64 rows=6364 width=16) (actual time=0.030..0.661 rows=6364 loops=3)
                                      Buffers: shared hit=150
Planning:
  Buffers: shared hit=6
Planning Time: 0.215 ms
JIT:
  Functions: 54
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 2.855 ms, Inlining 0.000 ms, Optimization 1.502 ms, Emission 30.151 ms, Total 34.508 ms
Execution Time: 383.698 ms
```

</details>

<details><summary>Có chỉ mục</summary>

```
Finalize GroupAggregate  (cost=18999.40..19228.03 rows=860 width=48) (actual time=80.839..85.021 rows=366 loops=1)
  Group Key: v.week_no, s.activity_type
  Buffers: shared hit=2982
  ->  Gather Merge  (cost=18999.40..19200.08 rows=1720 width=48) (actual time=80.830..84.605 rows=1055 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=2982
        ->  Sort  (cost=17999.38..18001.53 rows=860 width=48) (actual time=65.167..65.189 rows=352 loops=3)
              Sort Key: v.week_no, s.activity_type
              Sort Method: quicksort  Memory: 50kB
              Buffers: shared hit=2982
              Worker 0:  Sort Method: quicksort  Memory: 49kB
              Worker 1:  Sort Method: quicksort  Memory: 49kB
              ->  Partial HashAggregate  (cost=17946.71..17957.46 rows=860 width=48) (actual time=64.834..64.931 rows=352 loops=3)
                    Group Key: v.week_no, s.activity_type
                    Batches: 1  Memory Usage: 105kB
                    Buffers: shared hit=2950
                    Worker 0:  Batches: 1  Memory Usage: 105kB
                    Worker 1:  Batches: 1  Memory Usage: 105kB
                    ->  Hash Join  (cost=193.75..16771.07 rows=156752 width=24) (actual time=2.238..42.122 rows=109673 loops=3)
                          Hash Cond: (v.id_site = s.id_site)
                          Buffers: shared hit=2950
                          ->  Parallel Index Only Scan using ix_fact_vle_daily_offering on fact_vle_daily v  (cost=0.56..16166.13 rows=156752 width=24) (actual time=0.056..21.262 rows=109673 loops=3)
                                Index Cond: ((code_module = 'BBB'::text) AND (code_presentation = '2014J'::text))
                                Heap Fetches: 0
                                Buffers: shared hit=2794
                          ->  Hash  (cost=113.64..113.64 rows=6364 width=16) (actual time=2.143..2.144 rows=6364 loops=3)
                                Buckets: 8192  Batches: 1  Memory Usage: 394kB
                                Buffers: shared hit=150
                                ->  Seq Scan on dim_vle_site s  (cost=0.00..113.64 rows=6364 width=16) (actual time=0.013..0.812 rows=6364 loops=3)
                                      Buffers: shared hit=150
Planning:
  Buffers: shared hit=6
Planning Time: 0.236 ms
Execution Time: 85.088 ms
```

</details>
