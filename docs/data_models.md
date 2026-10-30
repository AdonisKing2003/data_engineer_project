# Mô hình hóa dữ liệu: từ quan hệ đến phi quan hệ

## 1. Các mô hình dữ liệu dùng trong project

Cùng dữ liệu OULAD được tổ chức theo nhiều mô hình, mỗi mô hình hợp với một kiểu truy cập.

| Mô hình | Ở đâu trong project | Hợp với | Không hợp với |
|---|---|---|---|
| Quan hệ chuẩn hóa (3NF) | PostgreSQL schema `three_nf` (TV3, [layouts.md](layouts.md)) | Hệ thống ghi nhiều (OLTP): mỗi dữ kiện lưu một chỗ, sửa không lệch | Phân tích: phải nối nhiều bảng |
| Mô hình chiều (star) | Kho chính: BigQuery `oulad`, PostgreSQL `public` ([design_levels.md](design_levels.md)) | Phân tích theo nhiều chiều, ít phép nối, dễ hiểu với người dùng | Ghi/sửa từng dòng |
| Bảng rộng phi chuẩn hóa | PostgreSQL/BigQuery `wide` (TV3) | Truy vấn không cần nối | Tốn chỗ, đổi một thuộc tính phải sửa nhiều dòng |
| Lưu trữ theo cột | Parquet (`data/warehouse`), BigQuery | Quét nhiều dòng, ít cột; nén tốt | Lấy trọn một dòng, ghi từng dòng |
| **Dạng lồng (nested, repeated)** | BigQuery `nested_student_timeline` (mục 2) | Dữ liệu cha-con luôn đọc cùng nhau | Câu hỏi cắt ngang phần tử con của mọi dòng |
| **Tài liệu (document, JSON)** | PostgreSQL `doc.student_timeline`, kiểu JSONB (mục 3) | Lấy trọn hồ sơ một đối tượng, cấu trúc linh hoạt | Tổng hợp trên nhiều tài liệu |
| **Khóa-giá trị (key-value)** | State store của Spark Structured Streaming ([report_tv1.md](report_tv1.md) mục 4): khóa SV × đợt × tuần → tổng click | Cập nhật và tra cứu theo khóa rất nhanh | Mọi truy vấn không đi theo khóa |

Mô hình đồ thị không dùng: các câu hỏi của 8 BR không cần duyệt quan hệ nhiều bước (kiểu "bạn của bạn").
Quan hệ sinh viên - học liệu chỉ có một bước, nối bảng là đủ.

Số đo so sánh 3NF / star / bảng rộng nằm ở [benchmark.md](benchmark.md). Tài liệu này đo hai mô hình phi quan
hệ, cùng dựng từ `fact_student_week` (sinh viên × đợt × tuần), so với chính bảng phẳng đó.

Đo lúc 26/10/2026 17:32. Mỗi truy vấn chạy 5 lần, thời gian lấy trung vị; BigQuery tắt cache.
File này do `scripts/data_models.py` tự sinh; chạy lại `make models` để cập nhật.

## 2. Dạng lồng trên BigQuery

**Mô hình:** mỗi lượt đăng ký một dòng, các tuần nằm trong cột `weeks` kiểu `ARRAY<STRUCT<…>>`
([sql/models/bq_build_nested.sql](../sql/models/bq_build_nested.sql)):

```
nested_student_timeline
├── id_student, code_module, code_presentation      ← khóa, lưu 1 lần
└── weeks: ARRAY of STRUCT                          ← 37–43 phần tử, sắp theo tuần
        week_no, clicks_week, clicks_cum, avg_score_cum, n_tma_missed_cum, is_enrolled, …
```

| | Số dòng | Kích thước |
|---|---:|---:|
| Bảng phẳng `fact_student_week` | 1,342,949 | 123.9 MB |
| Bảng lồng `nested_student_timeline` | 32,593 | 97.7 MB |

Bảng lồng nhỏ hơn 1.3× vì 3 cột khóa không còn lặp lại ở mỗi tuần.

**Truy vấn 1: dòng thời gian của một sinh viên** (11391, AAA 2013J; trang Sinh viên).
Bản phẳng [timeline_flat.sql](../sql/models/timeline_flat.sql) lọc 43 dòng trong 1,3 triệu dòng; bản lồng
[bq_timeline_nested.sql](../sql/models/bq_timeline_nested.sql) lấy đúng một dòng rồi trải mảng ra.

| | Bytes quét | Slot ms | Thời gian (s) |
|---|---:|---:|---:|
| Phẳng | 78.3 MB | 54 | 0.22 |
| Lồng | 52.1 MB | 60 | 0.27 |

Kết quả: giống hệt (43 tuần).

**Truy vấn 2: BR4 tuần 4 trên mọi đợt** (câu 14; trang Cảnh báo). Bản phẳng
[br4_week4.sql](../sql/optimize/br4_week4.sql) phải **nối bảng với chính nó** để lấy click tuần 3 cạnh tuần 4.
Bản lồng [bq_br4_week4_nested.sql](../sql/models/bq_br4_week4_nested.sql) không cần phép nối: tuần 3 nằm
ngay trong mảng của cùng dòng.

| | Bytes quét | Slot ms | Thời gian (s) |
|---|---:|---:|---:|
| Phẳng (nối với chính nó) | 79.2 MB | 304 | 0.26 |
| Lồng (không nối) | 53.0 MB | 4,374 | 0.83 |

Kết quả: giống hệt (27,250 lượt còn học, 3,958 vào danh sách, độ chính xác 80.6%).

**Đọc kết quả:**

- BigQuery lưu mỗi trường con của mảng thành một cột riêng, nên bảng lồng vẫn được quét theo cột. Bytes quét
  giảm vì cột khóa chỉ còn 32.593 giá trị thay vì 1,3 triệu.
- Nhưng ở truy vấn BR4, slot ms (công tính toán) tăng 14.4×: bỏ được
  phép nối bảng với chính nó, nhưng BigQuery phải dựng lại mảng của từng dòng để tìm tuần 3 và tuần 4. Công
  việc không mất đi mà chuyển từ phép nối sang xử lý mảng.
- Với cách tính tiền theo bytes quét (on-demand, như Sandbox) bản lồng rẻ hơn; với cách tính theo công tính
  toán (mua slot) và về thời gian chờ thì bản phẳng tốt hơn.
- Thêm nữa, SQL khó viết hơn (`UNNEST`, truy vấn con trên mảng) và sửa một tuần phải ghi lại cả dòng.

## 3. Dạng tài liệu JSONB trên PostgreSQL

**Mô hình:** mỗi lượt đăng ký một tài liệu JSON, giống cách một cơ sở dữ liệu tài liệu (MongoDB…) lưu hồ sơ
học tập ([sql/models/pg_build_document.sql](../sql/models/pg_build_document.sql)):

```json
{"weeks": [{"week_no": -4, "clicks_week": 0, "clicks_cum": 0, "avg_score_cum": null, "is_enrolled": true, ...},
           {"week_no": -3, ...}, ...]}
```

Dựng bảng mất 11.4 s.

| | Số dòng | Kích thước (gồm TOAST và khóa chính) |
|---|---:|---:|
| Bảng phẳng `public.fact_student_week` | 1,342,949 | 247.3 MB |
| Tài liệu `doc.student_timeline` | 32,593 | 33.3 MB |

Bản tài liệu nhỏ hơn 7.4× dù JSONB lặp lại tên trường ở mỗi tuần: tài liệu lớn
được PostgreSQL nén khi lưu ngoài dòng (TOAST), mỗi lượt đăng ký chỉ tốn một phần đầu dòng thay vì 37–43, và
khóa chính chỉ có 32.593 mục thay vì 1,3 triệu. Bảng phẳng thì không nén.

| Truy vấn | Phẳng (ms) | Tài liệu (ms) | Kết quả |
|---|---:|---:|---|
| Dòng thời gian một sinh viên ([phẳng](../sql/models/timeline_flat.sql), [tài liệu](../sql/models/pg_timeline_document.sql)) | 0.13 | 0.17 | giống hệt |
| Tuần 4 theo đợt, cắt ngang mọi sinh viên ([phẳng](../sql/models/pg_week4_flat.sql), [tài liệu](../sql/models/pg_week4_document.sql)) | 52.60 | 153.45 | giống hệt |

**Đọc kết quả:**

- Lấy hồ sơ một sinh viên: cả hai đều đi qua khóa chính. Bản phẳng đọc 43 dòng; bản tài liệu đọc đúng một
  dòng rồi giải nén và tách mảng. Ở cỡ này cả hai đều dưới 1 ms, khác biệt không đáng kể.
- Câu hỏi cắt ngang tuần 4: bản tài liệu chậm hơn 2.9×
  vì phải mở toàn bộ tài liệu, giải nén và tách mọi phần tử chỉ để giữ lại tuần 4. Bảng phẳng chỉ cần lọc theo
  cột `week_no`.

## 4. Kết luận: chọn mô hình theo cách truy cập

| Kiểu truy cập trong app | Mô hình hợp | Lý do |
|---|---|---|
| Tổng hợp nhiều chiều, cắt ngang mọi sinh viên (BR1–BR6) | Star, lưu theo cột | Lọc và gom theo cột nhanh, ít phép nối |
| Hồ sơ trọn vẹn của một sinh viên (BR7, trang Sinh viên) | Tài liệu hoặc dạng lồng | Một lần đọc ra cả hồ sơ, không cần nối |
| So tuần này với tuần trước của cùng sinh viên (BR4) | Star phẳng, phân vùng theo tuần | Dạng lồng bỏ được phép nối và quét ít bytes hơn, nhưng tốn công tính toán hơn nhiều (mục 2); phân vùng giảm bytes mà không tốn thêm ([optimization.md](optimization.md)) |
| Cập nhật liên tục theo khóa (stream) | Khóa-giá trị | Mỗi sự kiện chỉ chạm một khóa |
| Ghi và sửa dữ liệu gốc | Quan hệ 3NF | Mỗi dữ kiện một chỗ, không lệch khi sửa |

Kho chính của project giữ star vì 6/8 BR là câu hỏi tổng hợp cắt ngang. Các mô hình khác dùng ở đúng chỗ
hợp với chúng, không thay thế kho chính.

<details><summary>Kế hoạch truy vấn PostgreSQL: tuần 4</summary>

**Phẳng**

```
Finalize GroupAggregate  (cost=30176.31..30184.11 rows=28 width=58) (actual time=49.276..53.197 rows=22 loops=1)
  Group Key: code_module, code_presentation
  Buffers: shared hit=11281 read=10755
  ->  Gather Merge  (cost=30176.31..30182.85 rows=56 width=58) (actual time=49.265..53.166 rows=66 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=11281 read=10755
        ->  Sort  (cost=29176.29..29176.36 rows=28 width=58) (actual time=38.934..38.935 rows=22 loops=3)
              Sort Key: code_module, code_presentation
              Sort Method: quicksort  Memory: 26kB
              Buffers: shared hit=11281 read=10755
              Worker 0:  Sort Method: quicksort  Memory: 26kB
              Worker 1:  Sort Method: quicksort  Memory: 26kB
              ->  Partial HashAggregate  (cost=29175.27..29175.62 rows=28 width=58) (actual time=38.899..38.904 rows=22 loops=3)
                    Group Key: code_module, code_presentation
                    Batches: 1  Memory Usage: 24kB
                    Buffers: shared hit=11265 read=10755
                    Worker 0:  Batches: 1  Memory Usage: 24kB
                    Worker 1:  Batches: 1  Memory Usage: 24kB
                    ->  Parallel Seq Scan on fact_student_week  (cost=0.00..29014.53 rows=10716 width=26) (actual time=0.016..37.163 rows=9083 loops=3)
                          Filter: (is_enrolled AND (week_no = 4))
                          Rows Removed by Filter: 438566
                          Buffers: shared hit=11265 read=10755
Planning:
  Buffers: shared hit=2
Planning Time: 0.086 ms
Execution Time: 53.226 ms
```

**Tài liệu**

```
Finalize GroupAggregate  (cost=42929.06..42936.85 rows=28 width=58) (actual time=151.088..154.561 rows=22 loops=1)
  Group Key: t.code_module, t.code_presentation
  Buffers: shared hit=3920
  ->  Gather Merge  (cost=42929.06..42935.59 rows=56 width=58) (actual time=151.074..154.528 rows=66 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=3920
        ->  Sort  (cost=41929.03..41929.10 rows=28 width=58) (actual time=141.102..141.104 rows=22 loops=3)
              Sort Key: t.code_module, t.code_presentation
              Sort Method: quicksort  Memory: 26kB
              Buffers: shared hit=3920
              Worker 0:  Sort Method: quicksort  Memory: 26kB
              Worker 1:  Sort Method: quicksort  Memory: 26kB
              ->  Partial HashAggregate  (cost=41928.01..41928.36 rows=28 width=58) (actual time=141.071..141.076 rows=22 loops=3)
                    Group Key: t.code_module, t.code_presentation
                    Batches: 1  Memory Usage: 24kB
                    Buffers: shared hit=3904
                    Worker 0:  Batches: 1  Memory Usage: 24kB
                    Worker 1:  Batches: 1  Memory Usage: 24kB
                    ->  Nested Loop  (cost=0.01..41520.61 rows=13580 width=42) (actual time=0.050..137.264 rows=9083 loops=3)
                          Buffers: shared hit=3904
                          ->  Parallel Seq Scan on student_timeline t  (cost=0.00..4039.80 rows=13580 width=878) (actual time=0.004..3.128 rows=10864 loops=3)
                                Buffers: shared hit=3904
                          ->  Function Scan on jsonb_array_elements w  (cost=0.01..2.76 rows=1 width=32) (actual time=0.008..0.012 rows=1 loops=32593)
                                Filter: (((value ->> 'is_enrolled'::text))::boolean AND (((value ->> 'week_no'::text))::bigint = 4))
                                Rows Removed by Filter: 40
Planning:
  Buffers: shared hit=2
Planning Time: 0.097 ms
Execution Time: 154.594 ms
```

</details>
