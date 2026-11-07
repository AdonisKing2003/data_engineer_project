# Tối ưu truy vấn (việc 1.11)

Đo lúc 07/11/2026 17:34. Mỗi truy vấn chạy 5 lần, thời gian lấy trung vị; BigQuery tắt cache kết quả.
File này do `scripts/optimize.py` tự sinh; chạy lại `make optimize` để cập nhật.
Mỗi ví dụ đều so kết quả trước/sau tối ưu, hai bên phải ra giống hệt.

Kỹ thuật 1, 2, 4 đã nằm trong kho chính: `etl/04_load_bq.py` nạp thẳng vào bảng phân vùng / gom cụm,
`etl/05_load_pg.py` tạo chỉ mục khi nạp; `make marts` (cũng là một task trong DAG Airflow, ngay sau
bước nạp BigQuery) dựng lại mart của kỹ thuật 3. Mốc "trước" là bản sao bảng thường (`opt_fact_student_week_plain`,
`opt_fact_vle_daily_plain`) tạo tạm khi đo rồi xóa; với PostgreSQL, script xóa chỉ mục để đo rồi tạo lại.

## Tóm tắt

| # | Kỹ thuật | Engine | Truy vấn | Chỉ số | Trước | Sau | Giảm |
|---|---|---|---|---|---:|---:|---:|
| 1 | Phân vùng `fact_student_week` theo `week_no` | BigQuery | BR4 tuần 4 | bytes quét | 79.2 MB | 4.7 MB | 16.8× |
| 2 | Gom cụm `fact_vle_daily` theo module, kỳ | BigQuery | click 1 đợt theo tuần × loại | bytes quét | 304.6 MB | 19.2 MB | 15.9× |
| 3 | Bảng tổng hợp sẵn cho app (mart BR2) | BigQuery | biểu đồ BR2 của 1 đợt | bytes quét | 381.6 MB | 1.2 MB | 330.1× |
| 4 | Chỉ mục trên `fact_vle_daily` | PostgreSQL | như ví dụ 2 | thời gian | 200.5 ms | 37.6 ms | 5.3× |

Với BigQuery, bytes quét là chỉ số chính: tiền và hạn mức 1 TB/tháng tính theo bytes. Thời gian ở
cỡ dữ liệu này (dưới 1 GB) chủ yếu là chi phí khởi động job nên chênh ít và dao động giữa các lần chạy.
Bytes tính tiền (`billed`) tối thiểu 10 MB cho mỗi bảng được đọc, nên ở bảng nhỏ nó cao hơn bytes quét.

## 1. Phân vùng `fact_student_week` theo `week_no` (BigQuery)

**Truy vấn:** [sql/optimize/br4_week4.sql](../sql/optimize/br4_week4.sql), danh sách nguy cơ BR4 tại tuần 4
trên mọi đợt (câu 14). Trang Cảnh báo luôn hỏi theo một tuần cụ thể, nên phân vùng theo tuần khớp với cách app đọc.

**Cách lưu của kho chính:** phân vùng theo khoảng số nguyên, mỗi tuần một phân vùng (43 phân vùng, tuần −4
đến 38). `etl/04_load_bq.py` đặt phân vùng này trong load job, tương đương:

```sql
CREATE TABLE fact_student_week (...)
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(-4, 39, 1))
```

| Bảng | Truy vấn | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |
|---|---|---:|---:|---:|---:|---:|
| Bảng thường | lọc tuần qua phép nối | 79.2 MB | 79.7 MB | 2,718,491 | 958 | 0.32 |
| Bảng thường | thêm `p.week_no = 3` | 79.2 MB | 79.7 MB | 2,718,491 | 297 | 0.24 |
| Phân vùng | lọc tuần qua phép nối | 79.2 MB | 79.7 MB | 1,408,135 | 653 | 0.27 |
| Phân vùng | thêm `p.week_no = 3` | 4.7 MB | 21.0 MB | 97,779 | 64 | 0.23 |

Kết quả 4 lần chạy: giống hệt (27,250 lượt còn học, 3,958 vào danh sách, độ chính xác 80.6%).

**Đọc kết quả:**

- Truy vấn ghép `fact_student_week` với chính nó để lấy click tuần trước (`p.week_no = w.week_no - 1`).
  Điều kiện này chỉ biết giá trị khi chạy phép nối, nên BigQuery không dùng nó để bỏ phân vùng.
  Trên bảng phân vùng, phía `w` (`w.week_no = 4`) đã chỉ đọc tuần 4 nên số dòng đọc giảm gần một nửa,
  nhưng phía `p` vẫn đọc cả bảng nên bytes quét không giảm.
- Thêm điều kiện hằng số `p.week_no = 3` (không đổi kết quả) thì cả hai phía chỉ đọc đúng 1 phân vùng.
  Bài học: phân vùng chỉ có tác dụng khi truy vấn lọc cột phân vùng bằng hằng số hoặc tham số.
  Vì vậy truy vấn BR4 của app trên BigQuery (`sql/bigquery/br4_at_risk_all.sql`, `br4_at_risk_list.sql`) có thêm
  `p.week_no = @week_no - 1`: mỗi lần mở trang Cảnh báo chỉ quét khoảng 4,7 MB thay vì 79,2 MB.
- Trên bảng thường, thêm điều kiện đó không giảm bytes: BigQuery vẫn phải đọc cả cột.

**Đánh đổi:** Google khuyên mỗi phân vùng nên lớn (cỡ từ 1 GB); ở đây mỗi phân vùng chỉ vài MB nên
phân vùng là để minh họa, ở cỡ thật nên cân nhắc gom cụm theo `week_no` thay vì phân vùng.
Load job `WRITE_TRUNCATE` không đổi được cách phân vùng của bảng đã có, nên khi chuyển giữa bảng thường
và bảng phân vùng (`make load-plain`, `make tune`), `04_load_bq.py` xóa bảng cũ trước khi nạp.

## 2. Gom cụm `fact_vle_daily` theo `code_module`, `code_presentation` (BigQuery)

**Truy vấn:** [sql/optimize/vle_offering_week.sql](../sql/optimize/vle_offering_week.sql), click theo tuần ×
loại hoạt động của BBB 2014J. Đây là phần nặng nhất của trang Học phần (BR2) khi người dùng chọn một đợt.

**Cách lưu của kho chính:** sắp dữ liệu theo module, kỳ khi ghi để các khối lưu trữ của một đợt nằm cạnh
nhau. `etl/04_load_bq.py` đặt gom cụm này trong load job, tương đương:

```sql
CREATE TABLE fact_vle_daily (...)
CLUSTER BY code_module, code_presentation
```

| | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |
|---|---:|---:|---:|---:|---:|
| Bảng thường | 304.6 MB | 305.1 MB | 8,465,684 | 427 | 0.21 |
| Gom cụm | 19.2 MB | 21.0 MB | 536,432 | 45 | 0.18 |

Kết quả: giống hệt (366 dòng).

**Đọc kết quả:** bảng thường phải đọc 5 cột của cả 8,5 triệu dòng rồi mới lọc. Bảng gom cụm cho BigQuery
bỏ qua các khối không chứa BBB 2014J nên chỉ đọc khoảng 1/22 bảng (22 đợt). Khác phân vùng, gom cụm không
cần cột kiểu ngày/số và không giới hạn số giá trị, hợp với cột chuỗi như mã module, mã kỳ.

**Đánh đổi:** bytes ước tính trước khi chạy (dry run) không tính được phần bỏ qua nhờ gom cụm, chỉ biết sau
khi chạy. Truy vấn không lọc theo module, kỳ (ví dụ tổng click toàn kho) không được lợi gì.

## 3. Bảng tổng hợp sẵn cho app: mart BR2 (BigQuery)

**Truy vấn:** biểu đồ BR2 của trang Học phần cho BBB 2014J (tham số `@code_module`, `@code_presentation`).

- Trước: tính từ kho star bằng [sql/bigquery/br2_vle_weekly.sql](../sql/bigquery/br2_vle_weekly.sql)
  (ghép `fact_vle_daily`, `fact_enrollment`, `dim_vle_site`, lịch tuần) rồi lọc đợt; bảng click là bản sao
  bảng thường, để chỉ đo tác dụng của mart.
- Sau: đọc [sql/bigquery/br2_dashboard.sql](../sql/bigquery/br2_dashboard.sql) từ bảng `tv3_br2_weekly_mart`
  đã tính sẵn một lần bằng `make marts` (mart do TV3 thiết kế, xem
  [docs/tv3_marts.md](tv3_marts.md)).

Mart có 16,340 dòng, 1.9 MB.

| | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |
|---|---:|---:|---:|---:|---:|
| Tính từ kho star | 381.6 MB | 381.7 MB | 17,036,515 | 11,733 | 1.01 |
| Đọc mart | 1.2 MB | 10.5 MB | 16,340 | 11 | 0.19 |

Kết quả: giống hệt (760 dòng, so trên các cột trang Học phần dùng).

**Đọc kết quả:** mỗi lần người dùng đổi đợt, app chỉ đọc mart 16,340 dòng đã tính sẵn thay vì
ghép lại 8,5 triệu dòng click với bảng đăng ký và lịch tuần. Chi phí tính được trả một lần lúc dựng mart.
Mart chưa gom cụm theo module, kỳ nên vẫn đọc cả mart; ở cỡ này không đáng làm thêm.

**Đánh đổi:** mart phải dựng lại sau mỗi lần nạp kho; DAG Airflow làm việc này ngay sau bước nạp BigQuery,
còn khi nạp tay thì phải chạy `make marts`. Mart chỉ trả lời đúng các câu hỏi đã thiết kế trước (grain đợt ×
tuần × loại hoạt động).

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

Tạo chỉ mục + VACUUM mất 7.0 s. Chỉ mục chiếm 498.9 MB (bảng 855.5 MB).

| | Thời gian (ms) | Cách quét `fact_vle_daily` |
|---|---:|---|
| Không chỉ mục | 200.5 | `Parallel Seq Scan on fact_vle_daily v; Buffers: shared hit=2912 read=101576` |
| Có chỉ mục | 37.6 | `Parallel Index Only Scan using ix_fact_vle_daily_offering on fact_vle_daily v; Buffers: shared hit=2787` |

Kết quả: giống hệt. Thời gian đo phía client, sau một lần chạy nóng.

**Đọc kết quả:** không có chỉ mục thì PostgreSQL quét tuần tự cả bảng để lấy các dòng của một đợt trong 22.
Bảng lớn hơn bộ đệm `shared_buffers` nên dù đã chạy nóng, phần lớn trang vẫn phải đọc từ ngoài (`read=` trong
`Buffers`). Có chỉ mục thì PostgreSQL nhảy thẳng tới đoạn của BBB 2014J, đọc ít trang hơn hẳn và không mở bảng
(`Index Only Scan`).

**Đánh đổi:** tốn thêm dung lượng và làm chậm lúc nạp dữ liệu. `make load-pg` tạo chỉ mục này ngay khi nạp.
Bộ chạy benchmark star / 3NF / bảng rộng chỉ nhận schema có khóa chính, nên trước `make bench` chạy
`make load-plain` (bỏ chỉ mục, bỏ phân vùng / gom cụm), đo xong chạy `make tune` để bật lại.

## Kế hoạch truy vấn PostgreSQL đầy đủ

<details><summary>Không chỉ mục</summary>

```
Finalize GroupAggregate  (cost=160231.90..160460.53 rows=860 width=48) (actual time=203.219..206.183 rows=366 loops=1)
  Group Key: v.week_no, s.activity_type
  Buffers: shared hit=3094 read=101576
  ->  Gather Merge  (cost=160231.90..160432.58 rows=1720 width=48) (actual time=203.208..205.986 rows=1086 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=3094 read=101576
        ->  Sort  (cost=159231.87..159234.02 rows=860 width=48) (actual time=190.916..190.926 rows=362 loops=3)
              Sort Key: v.week_no, s.activity_type
              Sort Method: quicksort  Memory: 50kB
              Buffers: shared hit=3094 read=101576
              Worker 0:  Sort Method: quicksort  Memory: 50kB
              Worker 1:  Sort Method: quicksort  Memory: 50kB
              ->  Partial HashAggregate  (cost=159179.20..159189.95 rows=860 width=48) (actual time=190.740..190.788 rows=362 loops=3)
                    Group Key: v.week_no, s.activity_type
                    Batches: 1  Memory Usage: 105kB
                    Buffers: shared hit=3062 read=101576
                    Worker 0:  Batches: 1  Memory Usage: 105kB
                    Worker 1:  Batches: 1  Memory Usage: 105kB
                    ->  Hash Join  (cost=193.19..157977.84 rows=160182 width=24) (actual time=6.604..177.863 rows=109673 loops=3)
                          Hash Cond: (v.id_site = s.id_site)
                          Buffers: shared hit=3062 read=101576
                          ->  Parallel Seq Scan on fact_vle_daily v  (cost=0.00..157363.89 rows=160182 width=24) (actual time=5.639..164.582 rows=109673 loops=3)
                                Filter: ((code_module = 'BBB'::text) AND (code_presentation = '2014J'::text))
                                Rows Removed by Filter: 2710100
                                Buffers: shared hit=2912 read=101576
                          ->  Hash  (cost=113.64..113.64 rows=6364 width=16) (actual time=0.949..0.950 rows=6364 loops=3)
                                Buckets: 8192  Batches: 1  Memory Usage: 394kB
                                Buffers: shared hit=150
                                ->  Seq Scan on dim_vle_site s  (cost=0.00..113.64 rows=6364 width=16) (actual time=0.016..0.348 rows=6364 loops=3)
                                      Buffers: shared hit=150
Planning:
  Buffers: shared hit=6
Planning Time: 0.173 ms
JIT:
  Functions: 54
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 1.637 ms, Inlining 0.000 ms, Optimization 0.939 ms, Emission 15.717 ms, Total 18.293 ms
Execution Time: 206.991 ms
```

</details>

<details><summary>Có chỉ mục</summary>

```
Finalize GroupAggregate  (cost=18901.89..19130.52 rows=860 width=48) (actual time=39.385..41.977 rows=366 loops=1)
  Group Key: v.week_no, s.activity_type
  Buffers: shared hit=2975
  ->  Gather Merge  (cost=18901.89..19102.57 rows=1720 width=48) (actual time=39.380..41.770 rows=1039 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=2975
        ->  Sort  (cost=17901.86..17904.01 rows=860 width=48) (actual time=30.757..30.767 rows=346 loops=3)
              Sort Key: v.week_no, s.activity_type
              Sort Method: quicksort  Memory: 50kB
              Buffers: shared hit=2975
              Worker 0:  Sort Method: quicksort  Memory: 49kB
              Worker 1:  Sort Method: quicksort  Memory: 48kB
              ->  Partial HashAggregate  (cost=17849.20..17859.95 rows=860 width=48) (actual time=30.599..30.642 rows=346 loops=3)
                    Group Key: v.week_no, s.activity_type
                    Batches: 1  Memory Usage: 105kB
                    Buffers: shared hit=2943
                    Worker 0:  Batches: 1  Memory Usage: 105kB
                    Worker 1:  Batches: 1  Memory Usage: 105kB
                    ->  Hash Join  (cost=193.75..16679.93 rows=155902 width=24) (actual time=1.101..19.873 rows=109673 loops=3)
                          Hash Cond: (v.id_site = s.id_site)
                          Buffers: shared hit=2943
                          ->  Parallel Index Only Scan using ix_fact_vle_daily_offering on fact_vle_daily v  (cost=0.56..16077.23 rows=155902 width=24) (actual time=0.023..9.941 rows=109673 loops=3)
                                Index Cond: ((code_module = 'BBB'::text) AND (code_presentation = '2014J'::text))
                                Heap Fetches: 0
                                Buffers: shared hit=2787
                          ->  Hash  (cost=113.64..113.64 rows=6364 width=16) (actual time=1.053..1.053 rows=6364 loops=3)
                                Buckets: 8192  Batches: 1  Memory Usage: 394kB
                                Buffers: shared hit=150
                                ->  Seq Scan on dim_vle_site s  (cost=0.00..113.64 rows=6364 width=16) (actual time=0.009..0.398 rows=6364 loops=3)
                                      Buffers: shared hit=150
Planning:
  Buffers: shared hit=6
Planning Time: 0.138 ms
Execution Time: 42.015 ms
```

</details>
