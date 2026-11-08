# Chỉ mục cho `fact_student_week` (trang Cảnh báo BR4, trang Sinh viên BR7)

Đo lúc 08/11/2026 03:08. Mỗi truy vấn chạy 5 lần, thời gian lấy trung vị; BigQuery tắt cache kết quả.
File này do `scripts/index_student_week.py` tự sinh (`make indexing`). Đo trên bảng thử, cùng dữ liệu với
kho thật, tạo khi đo rồi xóa; bảng thật không bị đụng tới.

## Cách lưu được đo

BigQuery, theo `TUNING` trong `etl/04_load_bq.py`:

```sql
CREATE TABLE fact_student_week (...)
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(-4, 39, 1))
CLUSTER BY code_module, code_presentation, id_student
```

PostgreSQL, theo `INDEXES` trong `etl/05_load_pg.py` (khóa chính có sẵn: `(id_student, code_module, code_presentation, week_no)`):

```sql
CREATE INDEX ix_fact_student_week_week ON fact_student_week (week_no, code_module, code_presentation);
CLUSTER fact_student_week USING ix_fact_student_week_week;
```

## BigQuery 1× (`dataengineergroup32.oulad`)

| Mức | Dòng | Dung lượng bảng |
|---|---:|---:|
| Bảng thường | 1,342,949 | 123.9 MB |
| Phân vùng | 1,342,949 | 123.9 MB |
| Phân vùng + gom cụm | 1,342,949 | 123.9 MB |

Tham số: tuần 4, đợt BBB 2014J, sinh viên 26315. Phần đọc `fact_enrollment` (giống nhau ở mọi mức) là 0.9 MB.

| Truy vấn | Mức | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |
|---|---|---:|---:|---:|---:|---:|
| BR4 tuần 4, toàn trường (`br4_at_risk_all`) | Bảng thường | 79.2 MB | 79.7 MB | 5,404,389 | 1,168 | 0.87 |
| BR4 tuần 4, toàn trường (`br4_at_risk_all`) | Phân vùng | 4.7 MB | 21.0 MB | 162,965 | 598 | 0.66 |
| BR4 tuần 4, toàn trường (`br4_at_risk_all`) | Phân vùng + gom cụm | 4.7 MB | 21.0 MB | 162,965 | 342 | 0.72 |
| BR4 tuần 4, một đợt (BBB 2014J) (`br4_at_risk_list`) | Bảng thường | 79.2 MB | 79.7 MB | 5,404,389 | 509 | 0.25 |
| BR4 tuần 4, một đợt (BBB 2014J) (`br4_at_risk_list`) | Phân vùng | 4.7 MB | 21.0 MB | 162,965 | 61 | 0.21 |
| BR4 tuần 4, một đợt (BBB 2014J) (`br4_at_risk_list`) | Phân vùng + gom cụm | 4.7 MB | 21.0 MB | 162,965 | 78 | 0.22 |
| BR7 phân vị theo tuần, một đợt (`br7_cohort_benchmark`) | Bảng thường | 46.0 MB | 46.1 MB | 2,685,898 | 329 | 0.21 |
| BR7 phân vị theo tuần, một đợt (`br7_cohort_benchmark`) | Phân vùng | 46.0 MB | 46.1 MB | 2,685,898 | 1,147 | 0.36 |
| BR7 phân vị theo tuần, một đợt (`br7_cohort_benchmark`) | Phân vùng + gom cụm | 46.0 MB | 46.1 MB | 2,615,080 | 770 | 0.35 |
| BR7 tiến trình một sinh viên (`br7_student_progress`) | Bảng thường | 79.2 MB | 79.7 MB | 1,375,542 | 172 | 0.21 |
| BR7 tiến trình một sinh viên (`br7_student_progress`) | Phân vùng | 79.2 MB | 79.7 MB | 1,375,542 | 509 | 0.23 |
| BR7 tiến trình một sinh viên (`br7_student_progress`) | Phân vùng + gom cụm | 77.1 MB | 77.6 MB | 1,340,133 | 424 | 0.23 |

Kết quả 3 mức: `br4_at_risk_all` giống hệt (27,250 dòng); `br4_at_risk_list` giống hệt (1,782 dòng); `br7_cohort_benchmark` giống hệt (42 dòng); `br7_student_progress` giống hệt (42 dòng).

**BigQuery 5×: chưa đo.** Ba bản sao 5× (~1,9 GB) vượt hạn mức lưu trữ 10 GB của gói Sandbox (project đang dùng ~8,6 GB; bảng vừa xóa vẫn tính vào hạn mức trong thời gian time travel).

## PostgreSQL 1× (bản sao trong schema `idx_test`)

Truy vấn: [sql/optimize/br4_week4_pg.sql](../sql/optimize/br4_week4_pg.sql), BR4 tuần 4 toàn trường.

| Mức | Thời gian (ms) | Execution Time (ms) | Tương quan `week_no` | Tạo (s) | Bảng | Chỉ mục (gồm khóa chính) |
|---|---:|---:|---:|---:|---:|---:|
| Chỉ khóa chính | 144.2 | 125.2 | 0.022 | — | 180.4 MB | 66.8 MB |
| + chỉ mục B+-tree | 192.0 | 172.3 | 0.023 | 1.0 | 180.4 MB | 76.7 MB |
| + CLUSTER theo chỉ mục | 88.5 | 73.9 | 1.000 | 4.0 | 180.4 MB | 76.7 MB |

Cách quét `fact_student_week` (phía `w` tuần 4 và phía `p` tuần 3):

- **Chỉ khóa chính**
  - `Parallel Seq Scan on fact_student_week p_1; Buffers: shared hit=3424 read=18592`
  - `Parallel Seq Scan on fact_student_week w; Buffers: shared hit=3328 read=18688`
- **+ chỉ mục B+-tree**
  - `Bitmap Heap Scan on fact_student_week p_1; Buffers: shared hit=1 read=22046`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared read=32`
  - `Bitmap Heap Scan on fact_student_week w; Buffers: shared read=22047`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared read=32`
- **+ CLUSTER theo chỉ mục**
  - `Bitmap Heap Scan on fact_student_week p_1; Buffers: shared hit=567`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared hit=32`
  - `Bitmap Heap Scan on fact_student_week w; Buffers: shared hit=567`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared hit=32`

Kết quả 3 mức: giống hệt (27,250 lượt còn học, 3,958 có risk_score ≥ 2).

**Chi phí ghi:** INSERT toàn bộ bảng vào bảng rỗng (trung vị 3 lần):

| Bảng đích | Thời gian (s) |
|---|---:|
| Chỉ khóa chính | 2.36 |
| Khóa chính + chỉ mục | 4.52 |

Chỉ mục làm việc ghi chậm thêm 91%.

## PostgreSQL 5× (bản sao trong schema `idx_test_x5`)

Truy vấn: [sql/optimize/br4_week4_pg.sql](../sql/optimize/br4_week4_pg.sql), BR4 tuần 4 toàn trường.

| Mức | Thời gian (ms) | Execution Time (ms) | Tương quan `week_no` | Tạo (s) | Bảng | Chỉ mục (gồm khóa chính) |
|---|---:|---:|---:|---:|---:|---:|
| Chỉ khóa chính | 651.4 | 558.0 | 0.026 | — | 901.8 MB | 333.9 MB |
| + chỉ mục B+-tree | 478.5 | 386.8 | 0.018 | 4.4 | 901.8 MB | 382.1 MB |
| + CLUSTER theo chỉ mục | 367.8 | 274.5 | 1.000 | 12.9 | 901.8 MB | 382.1 MB |

Cách quét `fact_student_week` (phía `w` tuần 4 và phía `p` tuần 3):

- **Chỉ khóa chính**
  - `Parallel Seq Scan on fact_student_week p_1; Buffers: shared hit=3424 read=106656`
  - `Parallel Seq Scan on fact_student_week w; Buffers: shared hit=3328 read=106752`
- **+ chỉ mục B+-tree**
  - `Parallel Bitmap Heap Scan on fact_student_week p_1; Buffers: shared hit=6 read=34819`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared hit=3 read=146`
  - `Parallel Bitmap Heap Scan on fact_student_week w; Buffers: shared read=34868`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared read=144`
- **+ CLUSTER theo chỉ mục**
  - `Parallel Bitmap Heap Scan on fact_student_week p_1; Buffers: shared hit=2822`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared hit=149`
  - `Parallel Bitmap Heap Scan on fact_student_week w; Buffers: shared hit=2817`
  - `Bitmap Index Scan on ix_fact_student_week_week; Buffers: shared hit=144`

Kết quả 3 mức: giống hệt (136,250 lượt còn học, 19,770 có risk_score ≥ 2).

## Kế hoạch truy vấn PostgreSQL đầy đủ

<details><summary>1× — Chỉ khóa chính</summary>

```
Nested Loop  (cost=64116.14..65257.67 rows=1 width=143) (actual time=85.239..124.350 rows=27250 loops=1)
  Buffers: shared hit=88730 read=37280
  CTE cohort
    ->  Gather  (cost=30200.75..61635.87 rows=22827 width=66) (actual time=42.845..69.917 rows=27250 loops=1)
          Workers Planned: 2
          Workers Launched: 2
          Buffers: shared hit=6980 read=37280
          ->  Parallel Hash Right Join  (cost=29200.75..58353.17 rows=9511 width=66) (actual time=41.015..69.841 rows=9083 loops=3)
                Hash Cond: ((p_1.id_student = w.id_student) AND (p_1.code_module = w.code_module) AND (p_1.code_presentation = w.code_presentation) AND (p_1.week_no = (w.week_no - 1)))
                Buffers: shared hit=6980 read=37280
                ->  Parallel Seq Scan on fact_student_week p_1  (cost=0.00..29010.53 rows=13355 width=34) (actual time=0.009..25.209 rows=10864 loops=3)
                      Filter: (week_no = 3)
                      Rows Removed by Filter: 436785
                      Buffers: shared hit=3424 read=18592
                ->  Parallel Hash  (cost=29010.53..29010.53 rows=9511 width=58) (actual time=40.791..40.791 rows=9083 loops=3)
                      Buckets: 32768  Batches: 1  Memory Usage: 2816kB
                      Buffers: shared hit=3328 read=18688
                      ->  Parallel Seq Scan on fact_student_week w  (cost=0.00..29010.53 rows=9511 width=58) (actual time=0.030..38.182 rows=9083 loops=3)
                            Filter: (is_enrolled AND (week_no = 4))
                            Rows Removed by Filter: 438566
                            Buffers: shared hit=3328 read=18688
  ->  Hash Join  (cost=2479.99..3056.38 rows=1303 width=192) (actual time=85.216..92.258 rows=27250 loops=1)
        Hash Cond: ((c.code_module = p.code_module) AND (c.code_presentation = p.code_presentation))
        Buffers: shared hit=6980 read=37280
        ->  CTE Scan on cohort c  (cost=0.00..456.54 rows=22827 width=120) (actual time=42.847..44.153 rows=27250 loops=1)
              Buffers: shared hit=1239 read=7249
        ->  Hash  (cost=2445.74..2445.74 rows=2283 width=72) (actual time=42.354..42.355 rows=22 loops=1)
              Buckets: 4096  Batches: 1  Memory Usage: 34kB
              Buffers: shared hit=5741 read=30031
              ->  Subquery Scan on p  (cost=2109.04..2445.74 rows=2283 width=72) (actual time=37.977..42.345 rows=22 loops=1)
                    Buffers: shared hit=5741 read=30031
                    ->  GroupAggregate  (cost=2109.04..2422.91 rows=2283 width=72) (actual time=37.976..42.341 rows=22 loops=1)
                          Group Key: cohort.code_module, cohort.code_presentation
                          Buffers: shared hit=5741 read=30031
                          ->  Sort  (cost=2109.04..2166.11 rows=22827 width=72) (actual time=37.901..38.621 rows=27250 loops=1)
                                Sort Key: cohort.code_module, cohort.code_presentation
                                Sort Method: quicksort  Memory: 2046kB
                                Buffers: shared hit=5741 read=30031
                                ->  CTE Scan on cohort  (cost=0.00..456.54 rows=22827 width=72) (actual time=0.001..30.682 rows=27250 loops=1)
                                      Buffers: shared hit=5741 read=30031
  ->  Index Scan using fact_enrollment_pkey on fact_enrollment e  (cost=0.29..0.43 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=27250)
        Index Cond: ((id_student = c.id_student) AND (code_module = c.code_module) AND (code_presentation = c.code_presentation))
        Buffers: shared hit=81750
Planning:
  Buffers: shared hit=16
Planning Time: 0.332 ms
Execution Time: 125.201 ms
```

</details>

<details><summary>1× — + chỉ mục B+-tree</summary>

```
Nested Loop  (cost=51369.30..52701.97 rows=1 width=143) (actual time=135.061..171.552 rows=27250 loops=1)
  Buffers: shared hit=81751 read=44093
  CTE cohort
    ->  Hash Right Join  (cost=24756.58..48570.21 rows=25569 width=66) (actual time=62.099..116.796 rows=27250 loops=1)
          Hash Cond: ((p_1.id_student = w.id_student) AND (p_1.code_module = w.code_module) AND (p_1.code_presentation = w.code_presentation) AND (p_1.week_no = (w.week_no - 1)))
          Buffers: shared hit=1 read=44093
          ->  Bitmap Heap Scan on fact_student_week p_1  (cost=384.97..23841.41 rows=33618 width=34) (actual time=4.360..48.094 rows=32593 loops=1)
                Recheck Cond: (week_no = 3)
                Heap Blocks: exact=22015
                Buffers: shared hit=1 read=22046
                ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..376.56 rows=33618 width=0) (actual time=1.761..1.761 rows=32593 loops=1)
                      Index Cond: (week_no = 3)
                      Buffers: shared read=32
          ->  Hash  (cost=23860.23..23860.23 rows=25569 width=58) (actual time=57.716..57.717 rows=27250 loops=1)
                Buckets: 32768  Batches: 1  Memory Usage: 2775kB
                Buffers: shared read=22047
                ->  Bitmap Heap Scan on fact_student_week w  (cost=373.92..23860.23 rows=25569 width=58) (actual time=3.508..51.870 rows=27250 loops=1)
                      Recheck Cond: (week_no = 4)
                      Filter: is_enrolled
                      Rows Removed by Filter: 5343
                      Heap Blocks: exact=22015
                      Buffers: shared read=22047
                      ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..367.53 rows=32947 width=0) (actual time=1.434..1.434 rows=32593 loops=1)
                            Index Cond: (week_no = 4)
                            Buffers: shared read=32
  ->  Hash Join  (cost=2798.80..3444.43 rows=1634 width=192) (actual time=135.042..141.745 rows=27250 loops=1)
        Hash Cond: ((c.code_module = p.code_module) AND (c.code_presentation = p.code_presentation))
        Buffers: shared hit=1 read=44093
        ->  CTE Scan on cohort c  (cost=0.00..511.38 rows=25569 width=120) (actual time=62.101..63.335 rows=27250 loops=1)
              Buffers: shared read=22080
        ->  Hash  (cost=2760.45..2760.45 rows=2557 width=72) (actual time=72.931..72.932 rows=22 loops=1)
              Buckets: 4096  Batches: 1  Memory Usage: 34kB
              Buffers: shared hit=1 read=22013
              ->  Subquery Scan on p  (cost=2383.30..2760.45 rows=2557 width=72) (actual time=68.858..72.925 rows=22 loops=1)
                    Buffers: shared hit=1 read=22013
                    ->  GroupAggregate  (cost=2383.30..2734.88 rows=2557 width=72) (actual time=68.857..72.922 rows=22 loops=1)
                          Group Key: cohort.code_module, cohort.code_presentation
                          Buffers: shared hit=1 read=22013
                          ->  Sort  (cost=2383.30..2447.22 rows=25569 width=72) (actual time=68.787..69.440 rows=27250 loops=1)
                                Sort Key: cohort.code_module, cohort.code_presentation
                                Sort Method: quicksort  Memory: 2046kB
                                Buffers: shared hit=1 read=22013
                                ->  CTE Scan on cohort  (cost=0.00..511.38 rows=25569 width=72) (actual time=0.001..61.630 rows=27250 loops=1)
                                      Buffers: shared hit=1 read=22013
  ->  Index Scan using fact_enrollment_pkey on fact_enrollment e  (cost=0.29..0.42 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=27250)
        Index Cond: ((id_student = c.id_student) AND (code_module = c.code_module) AND (code_presentation = c.code_presentation))
        Buffers: shared hit=81750
Planning:
  Buffers: shared hit=10 read=6
Planning Time: 0.333 ms
Execution Time: 172.316 ms
```

</details>

<details><summary>1× — + CLUSTER theo chỉ mục</summary>

```
Nested Loop  (cost=51360.27..52672.49 rows=1 width=143) (actual time=31.380..72.983 rows=27250 loops=1)
  Buffers: shared hit=82884
  CTE cohort
    ->  Hash Right Join  (cost=24752.30..48595.12 rows=25278 width=66) (actual time=6.945..17.155 rows=27250 loops=1)
          Hash Cond: ((p_1.id_student = w.id_student) AND (p_1.code_module = w.code_module) AND (p_1.code_presentation = w.code_presentation) AND (p_1.week_no = (w.week_no - 1)))
          Buffers: shared hit=1134
          ->  Bitmap Heap Scan on fact_student_week p_1  (cost=374.03..23869.17 rows=32723 width=34) (actual time=0.415..2.072 rows=32593 loops=1)
                Recheck Cond: (week_no = 3)
                Heap Blocks: exact=535
                Buffers: shared hit=567
                ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..365.85 rows=32723 width=0) (actual time=0.379..0.379 rows=32593 loops=1)
                      Index Cond: (week_no = 3)
                      Buffers: shared hit=32
          ->  Hash  (cost=23872.71..23872.71 rows=25278 width=58) (actual time=6.511..6.512 rows=27250 loops=1)
                Buckets: 32768  Batches: 1  Memory Usage: 2775kB
                Buffers: shared hit=567
                ->  Bitmap Heap Scan on fact_student_week w  (cost=370.83..23872.71 rows=25278 width=58) (actual time=0.336..3.277 rows=27250 loops=1)
                      Recheck Cond: (week_no = 4)
                      Filter: is_enrolled
                      Rows Removed by Filter: 5343
                      Heap Blocks: exact=535
                      Buffers: shared hit=567
                      ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..364.51 rows=32544 width=0) (actual time=0.296..0.296 rows=32593 loops=1)
                            Index Cond: (week_no = 4)
                            Buffers: shared hit=32
  ->  Hash Join  (cost=2764.86..3403.15 rows=1598 width=192) (actual time=31.361..38.320 rows=27250 loops=1)
        Hash Cond: ((c.code_module = p.code_module) AND (c.code_presentation = p.code_presentation))
        Buffers: shared hit=1134
        ->  CTE Scan on cohort c  (cost=0.00..505.56 rows=25278 width=120) (actual time=6.947..8.283 rows=27250 loops=1)
              Buffers: shared hit=600
        ->  Hash  (cost=2726.94..2726.94 rows=2528 width=72) (actual time=24.408..24.410 rows=22 loops=1)
              Buckets: 4096  Batches: 1  Memory Usage: 34kB
              Buffers: shared hit=534
              ->  Subquery Scan on p  (cost=2354.09..2726.94 rows=2528 width=72) (actual time=18.614..24.399 rows=22 loops=1)
                    Buffers: shared hit=534
                    ->  GroupAggregate  (cost=2354.09..2701.66 rows=2528 width=72) (actual time=18.613..24.394 rows=22 loops=1)
                          Group Key: cohort.code_module, cohort.code_presentation
                          Buffers: shared hit=534
                          ->  Sort  (cost=2354.09..2417.28 rows=25278 width=72) (actual time=18.532..19.337 rows=27250 loops=1)
                                Sort Key: cohort.code_module, cohort.code_presentation
                                Sort Method: quicksort  Memory: 2046kB
                                Buffers: shared hit=534
                                ->  CTE Scan on cohort  (cost=0.00..505.56 rows=25278 width=72) (actual time=0.001..15.916 rows=27250 loops=1)
                                      Buffers: shared hit=534
  ->  Index Scan using fact_enrollment_pkey on fact_enrollment e  (cost=0.29..0.42 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=27250)
        Index Cond: ((id_student = c.id_student) AND (code_module = c.code_module) AND (code_presentation = c.code_presentation))
        Buffers: shared hit=81750
Planning:
  Buffers: shared hit=16
Planning Time: 0.318 ms
Execution Time: 73.860 ms
```

</details>

<details><summary>5× — Chỉ khóa chính</summary>

```
Hash Join  (cost=328558.61..332144.15 rows=1 width=143) (actual time=479.922..551.954 rows=136250 loops=1)
  Hash Cond: ((c.code_module = p.code_module) AND (c.code_presentation = p.code_presentation) AND (c.id_student = e.id_student))
  Buffers: shared hit=9497 read=213408, temp read=3347 written=3349
  CTE cohort
    ->  Gather  (cost=147009.45..304187.31 rows=114735 width=66) (actual time=198.264..327.419 rows=136250 loops=1)
          Workers Planned: 2
          Workers Launched: 2
          Buffers: shared hit=6938 read=213408
          ->  Parallel Hash Right Join  (cost=146009.45..291713.81 rows=47806 width=66) (actual time=188.355..332.192 rows=45417 loops=3)
                Hash Cond: ((p_1.id_student = w.id_student) AND (p_1.code_module = w.code_module) AND (p_1.code_presentation = w.code_presentation) AND (p_1.week_no = (w.week_no - 1)))
                Buffers: shared hit=6938 read=213408
                ->  Parallel Seq Scan on fact_student_week p_1  (cost=0.00..145053.33 rows=61273 width=34) (actual time=0.027..123.787 rows=54322 loops=3)
                      Filter: (week_no = 3)
                      Rows Removed by Filter: 2183927
                      Buffers: shared hit=3424 read=106656
                ->  Parallel Hash  (cost=145053.33..145053.33 rows=47806 width=58) (actual time=187.967..187.967 rows=45417 loops=3)
                      Buckets: 262144 (originally 131072)  Batches: 1 (originally 1)  Memory Usage: 15744kB
                      Buffers: shared hit=3328 read=106752
                      ->  Parallel Seq Scan on fact_student_week w  (cost=0.00..145053.33 rows=47806 width=58) (actual time=11.338..170.404 rows=45417 loops=3)
                            Filter: (is_enrolled AND (week_no = 4))
                            Rows Removed by Filter: 2192832
                            Buffers: shared hit=3328 read=106752
  ->  CTE Scan on cohort c  (cost=0.00..2294.70 rows=114735 width=120) (actual time=198.266..206.713 rows=136250 loops=1)
        Buffers: shared hit=1262 read=36482, temp read=1364 written=1
  ->  Hash  (cost=23553.23..23553.23 rows=46747 width=97) (actual time=281.595..281.598 rows=162965 loops=1)
        Buckets: 131072 (originally 65536)  Batches: 2 (originally 1)  Memory Usage: 7169kB
        Buffers: shared hit=8235 read=176926, temp read=568 written=2582
        ->  Hash Join  (cost=18508.96..23553.23 rows=46747 width=97) (actual time=220.094..253.942 rows=162965 loops=1)
              Hash Cond: ((e.code_module = p.code_module) AND (e.code_presentation = p.code_presentation))
              Buffers: shared hit=8235 read=176926, temp read=568 written=1933
              ->  Seq Scan on fact_enrollment e  (cost=0.00..4188.65 rows=162965 width=25) (actual time=0.003..6.766 rows=162965 loops=1)
                    Buffers: shared hit=2559
              ->  Hash  (cost=18336.85..18336.85 rows=11474 width=72) (actual time=220.055..220.057 rows=22 loops=1)
                    Buckets: 16384  Batches: 1  Memory Usage: 130kB
                    Buffers: shared hit=5676 read=176926, temp read=568 written=1933
                    ->  Subquery Scan on p  (cost=16644.50..18336.85 rows=11474 width=72) (actual time=185.175..220.039 rows=22 loops=1)
                          Buffers: shared hit=5676 read=176926, temp read=568 written=1933
                          ->  GroupAggregate  (cost=16644.50..18222.11 rows=11474 width=72) (actual time=185.173..220.032 rows=22 loops=1)
                                Group Key: cohort.code_module, cohort.code_presentation
                                Buffers: shared hit=5676 read=176926, temp read=568 written=1933
                                ->  Sort  (cost=16644.50..16931.34 rows=114735 width=72) (actual time=184.706..200.466 rows=136250 loops=1)
                                      Sort Key: cohort.code_module, cohort.code_presentation
                                      Sort Method: external merge  Disk: 4544kB
                                      Buffers: shared hit=5676 read=176926, temp read=568 written=1933
                                      ->  CTE Scan on cohort  (cost=0.00..2294.70 rows=114735 width=72) (actual time=0.003..152.354 rows=136250 loops=1)
                                            Buffers: shared hit=5676 read=176926, temp written=1363
Planning:
  Buffers: shared hit=20
Planning Time: 0.311 ms
JIT:
  Functions: 108
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 2.607 ms, Inlining 0.000 ms, Optimization 1.714 ms, Emission 32.305 ms, Total 36.625 ms
Execution Time: 557.964 ms
```

</details>

<details><summary>5× — + chỉ mục B+-tree</summary>

```
Hash Join  (cost=323591.44..327674.11 rows=1 width=143) (actual time=306.724..380.564 rows=136250 loops=1)
  Hash Cond: ((c.code_module = p.code_module) AND (c.code_presentation = p.code_presentation) AND (c.id_student = e.id_student))
  Buffers: shared hit=86 read=72254, temp read=3347 written=3349
  CTE cohort
    ->  Gather  (cost=144179.77..296419.89 rows=130643 width=66) (actual time=100.994..154.899 rows=136250 loops=1)
          Workers Planned: 2
          Workers Launched: 2
          Buffers: shared hit=86 read=69695
          ->  Parallel Hash Right Join  (cost=143179.77..282355.59 rows=54435 width=66) (actual time=89.580..152.557 rows=45417 loops=3)
                Hash Cond: ((p_1.id_student = w.id_student) AND (p_1.code_module = w.code_module) AND (p_1.code_presentation = w.code_presentation) AND (p_1.week_no = (w.week_no - 1)))
                Buffers: shared hit=86 read=69695
                ->  Parallel Bitmap Heap Scan on fact_student_week p_1  (cost=1770.15..140250.37 rows=65469 width=34) (actual time=12.181..52.879 rows=54322 loops=3)
                      Recheck Cond: (week_no = 3)
                      Heap Blocks: exact=8409
                      Buffers: shared hit=6 read=34819
                      ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..1730.87 rows=157125 width=0) (actual time=8.191..8.191 rows=162965 loops=1)
                            Index Cond: (week_no = 3)
                            Buffers: shared hit=3 read=146
                ->  Parallel Hash  (cost=140320.92..140320.92 rows=54435 width=58) (actual time=76.976..76.977 rows=45417 loops=3)
                      Buckets: 262144 (originally 131072)  Batches: 1 (originally 1)  Memory Usage: 15744kB
                      Buffers: shared read=34868
                      ->  Parallel Bitmap Heap Scan on fact_student_week w  (cost=1875.07..140320.92 rows=54435 width=58) (actual time=14.691..61.276 rows=45417 loops=3)
                            Recheck Cond: (week_no = 4)
                            Filter: is_enrolled
                            Rows Removed by Filter: 8905
                            Heap Blocks: exact=13538
                            Buffers: shared read=34868
                            ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..1842.41 rows=167197 width=0) (actual time=6.757..6.758 rows=162965 loops=1)
                                  Index Cond: (week_no = 4)
                                  Buffers: shared read=144
  ->  CTE Scan on cohort c  (cost=0.00..2612.86 rows=130643 width=120) (actual time=100.996..109.314 rows=136250 loops=1)
        Buffers: shared read=13683, temp read=1364 written=1
  ->  Hash  (cost=26240.13..26240.13 rows=53224 width=97) (actual time=205.601..205.604 rows=162965 loops=1)
        Buckets: 131072 (originally 65536)  Batches: 2 (originally 1)  Memory Usage: 7169kB
        Buffers: shared hit=86 read=58571, temp read=568 written=2582
        ->  Hash Join  (cost=21195.86..26240.13 rows=53224 width=97) (actual time=141.402..177.680 rows=162965 loops=1)
              Hash Cond: ((e.code_module = p.code_module) AND (e.code_presentation = p.code_presentation))
              Buffers: shared hit=86 read=58571, temp read=568 written=1933
              ->  Seq Scan on fact_enrollment e  (cost=0.00..4188.65 rows=162965 width=25) (actual time=0.007..10.561 rows=162965 loops=1)
                    Buffers: shared read=2559
              ->  Hash  (cost=20999.90..20999.90 rows=13064 width=72) (actual time=141.349..141.351 rows=22 loops=1)
                    Buckets: 16384  Batches: 1  Memory Usage: 130kB
                    Buffers: shared hit=86 read=56012, temp read=568 written=1933
                    ->  Subquery Scan on p  (cost=19072.93..20999.90 rows=13064 width=72) (actual time=108.724..141.334 rows=22 loops=1)
                          Buffers: shared hit=86 read=56012, temp read=568 written=1933
                          ->  GroupAggregate  (cost=19072.93..20869.26 rows=13064 width=72) (actual time=108.722..141.327 rows=22 loops=1)
                                Group Key: cohort.code_module, cohort.code_presentation
                                Buffers: shared hit=86 read=56012, temp read=568 written=1933
                                ->  Sort  (cost=19072.93..19399.53 rows=130643 width=72) (actual time=108.265..123.040 rows=136250 loops=1)
                                      Sort Key: cohort.code_module, cohort.code_presentation
                                      Sort Method: external merge  Disk: 4544kB
                                      Buffers: shared hit=86 read=56012, temp read=568 written=1933
                                      ->  CTE Scan on cohort  (cost=0.00..2612.86 rows=130643 width=72) (actual time=0.003..74.661 rows=136250 loops=1)
                                            Buffers: shared hit=86 read=56012, temp written=1363
Planning:
  Buffers: shared hit=11 read=9
Planning Time: 32.613 ms
JIT:
  Functions: 114
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 2.974 ms, Inlining 0.000 ms, Optimization 2.075 ms, Emission 31.296 ms, Total 36.345 ms
Execution Time: 386.803 ms
```

</details>

<details><summary>5× — + CLUSTER theo chỉ mục</summary>

```
Hash Join  (cost=323637.02..327731.35 rows=1 width=143) (actual time=193.623..268.339 rows=136250 loops=1)
  Hash Cond: ((c.code_module = p.code_module) AND (c.code_presentation = p.code_presentation) AND (c.id_student = e.id_student))
  Buffers: shared hit=8286, temp read=3347 written=3349
  CTE cohort
    ->  Gather  (cost=144156.72..296397.33 rows=131016 width=66) (actual time=46.596..60.808 rows=136250 loops=1)
          Workers Planned: 2
          Workers Launched: 2
          Buffers: shared hit=5727
          ->  Parallel Hash Right Join  (cost=143156.72..282295.73 rows=54590 width=66) (actual time=35.618..55.454 rows=45417 loops=3)
                Hash Cond: ((p_1.id_student = w.id_student) AND (p_1.code_module = w.code_module) AND (p_1.code_presentation = w.code_presentation) AND (p_1.week_no = (w.week_no - 1)))
                Buffers: shared hit=5727
                ->  Parallel Bitmap Heap Scan on fact_student_week p_1  (cost=1746.54..140198.85 rows=64630 width=34) (actual time=2.117..6.074 rows=54322 loops=3)
                      Recheck Cond: (week_no = 3)
                      Heap Blocks: exact=120
                      Buffers: shared hit=2822
                      ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..1707.76 rows=155111 width=0) (actual time=1.858..1.858 rows=162965 loops=1)
                            Index Cond: (week_no = 3)
                            Buffers: shared hit=149
                ->  Parallel Hash  (cost=140318.38..140318.38 rows=54590 width=58) (actual time=33.166..33.167 rows=45417 loops=3)
                      Buckets: 262144 (originally 131072)  Batches: 1 (originally 1)  Memory Usage: 15744kB
                      Buffers: shared hit=2817
                      ->  Parallel Bitmap Heap Scan on fact_student_week w  (cost=1884.20..140318.38 rows=54590 width=58) (actual time=12.030..18.231 rows=45417 loops=3)
                            Recheck Cond: (week_no = 4)
                            Filter: is_enrolled
                            Rows Removed by Filter: 8905
                            Heap Blocks: exact=1036
                            Buffers: shared hit=2817
                            ->  Bitmap Index Scan on ix_fact_student_week_week  (cost=0.00..1851.45 rows=167869 width=0) (actual time=1.627..1.627 rows=162965 loops=1)
                                  Index Cond: (week_no = 4)
                                  Buffers: shared hit=144
  ->  CTE Scan on cohort c  (cost=0.00..2620.32 rows=131016 width=120) (actual time=46.598..54.962 rows=136250 loops=1)
        Buffers: shared hit=1181, temp read=1364 written=1
  ->  Hash  (cost=26305.57..26305.57 rows=53379 width=97) (actual time=146.908..146.911 rows=162965 loops=1)
        Buckets: 131072 (originally 65536)  Batches: 2 (originally 1)  Memory Usage: 7169kB
        Buffers: shared hit=7105, temp read=568 written=2582
        ->  Hash Join  (cost=21261.30..26305.57 rows=53379 width=97) (actual time=85.282..118.962 rows=162965 loops=1)
              Hash Cond: ((e.code_module = p.code_module) AND (e.code_presentation = p.code_presentation))
              Buffers: shared hit=7105, temp read=568 written=1933
              ->  Seq Scan on fact_enrollment e  (cost=0.00..4188.65 rows=162965 width=25) (actual time=0.005..6.671 rows=162965 loops=1)
                    Buffers: shared hit=2559
              ->  Hash  (cost=21064.77..21064.77 rows=13102 width=72) (actual time=85.247..85.249 rows=22 loops=1)
                    Buckets: 16384  Batches: 1  Memory Usage: 130kB
                    Buffers: shared hit=4546, temp read=568 written=1933
                    ->  Subquery Scan on p  (cost=19132.28..21064.77 rows=13102 width=72) (actual time=55.216..85.233 rows=22 loops=1)
                          Buffers: shared hit=4546, temp read=568 written=1933
                          ->  GroupAggregate  (cost=19132.28..20933.75 rows=13102 width=72) (actual time=55.214..85.227 rows=22 loops=1)
                                Group Key: cohort.code_module, cohort.code_presentation
                                Buffers: shared hit=4546, temp read=568 written=1933
                                ->  Sort  (cost=19132.28..19459.82 rows=131016 width=72) (actual time=54.765..66.580 rows=136250 loops=1)
                                      Sort Key: cohort.code_module, cohort.code_presentation
                                      Sort Method: external merge  Disk: 4544kB
                                      Buffers: shared hit=4546, temp read=568 written=1933
                                      ->  CTE Scan on cohort  (cost=0.00..2620.32 rows=131016 width=72) (actual time=0.002..30.790 rows=136250 loops=1)
                                            Buffers: shared hit=4546, temp written=1363
Planning:
  Buffers: shared hit=20
Planning Time: 0.337 ms
JIT:
  Functions: 114
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 2.846 ms, Inlining 0.000 ms, Optimization 1.811 ms, Emission 32.543 ms, Total 37.200 ms
Execution Time: 274.497 ms
```

</details>
