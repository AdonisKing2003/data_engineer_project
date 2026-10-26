# Bố trí chuẩn hóa một phần fact và wide cho TV3

`scripts/build_layouts.py` tạo các bố trí thay thế để chạy benchmark BR1, BR2, BR4 và BR6. Bố trí star hiện hữu là nguồn chỉ đọc.

## Nguồn và đích

| Engine | Scale | Nguồn star chỉ đọc | Đích chuẩn hóa một phần fact | Đích wide |
|---|---:|---|---|---|
| PostgreSQL | 1× | schema `public` | `three_nf` | `wide` |
| PostgreSQL | 5× | schema `x5` | `three_nf_x5` | `wide_x5` |
| BigQuery | 1× | dataset `BQ_DATASET` | `BQ_DATASET_3nf` | `BQ_DATASET_wide` |
| BigQuery | 5× | dataset `BQ_DATASET_5x` | `BQ_DATASET_3nf_5x` | `BQ_DATASET_wide_5x` |

Với BigQuery, truy vấn nguồn dùng tên bảng không kèm dataset và đặt `default_dataset` rõ ràng thành dataset nguồn. Lệnh tạo bảng chỉ định đầy đủ project và dataset đích. Với PostgreSQL, mọi bảng nguồn đều được ghi bằng tên schema và bảng đã quote.

## Chạy

Trước tiên nạp kho star 1× bằng quy trình hiện có (`make all`). Nếu cần 5×, chạy `make scale` trước để có nguồn `x5` và `BQ_DATASET_5x`. Chạy trong container `app` để dùng cấu hình trong `.env`:

```powershell
docker compose exec -T app python scripts/build_layouts.py --engine pg --scale 1 --layout all
docker compose exec -T app python scripts/build_layouts.py --engine pg --scale 5 --layout all
docker compose exec -T app python scripts/build_layouts.py --engine bq --scale 1 --layout all
docker compose exec -T app python scripts/build_layouts.py --engine bq --scale 5 --layout all
```

`--layout` nhận `3nf`, `wide` hoặc `all`. Chọn một bố trí để chỉ xây đích đó. `--scale` nhận `1` hoặc `5`, mặc định là `1`. `--engine` là bắt buộc và nhận `pg` hoặc `bq`.

Ví dụ chỉ dựng PostgreSQL bố trí chuẩn hóa một phần fact ở scale 1× (ID kỹ thuật `3nf`):

```powershell
docker compose exec -T app python scripts/build_layouts.py --engine pg --scale 1 --layout 3nf
```

## Bảng và grain

### Chuẩn hóa một phần fact (ID kỹ thuật: `3nf`)

Tên người dùng của bố trí này là **chuẩn hóa một phần fact** vì chỉ hai fact được tách các thuộc tính dư thừa vào dimension; ID kỹ thuật vẫn là `3nf`. Target PostgreSQL vẫn là schema `three_nf`, còn target BigQuery vẫn dùng hậu tố `_3nf`.

Giữ nguyên chín bảng logic theo hợp đồng: năm dimension và bốn fact. Grain của các dimension là `dim_presentation` (một dòng mỗi cặp `code_module`, `code_presentation`), `dim_student` (`id_student`), `dim_assessment` (`id_assessment`), `dim_vle_site` (`id_site`) và `dim_week` (`week_no`). Grain của các fact vẫn là:

| Bảng | Grain |
|---|---|
| `fact_enrollment` | Một sinh viên × một đợt (`id_student`, `code_module`, `code_presentation`) |
| `fact_submission` | Một sinh viên × một bài nộp (`id_student`, `id_assessment`) |
| `fact_vle_daily` | Một sinh viên × một đợt × một học liệu × một ngày |
| `fact_student_week` | Một sinh viên × một đợt × một tuần |

Các bảng dimension được sao chép đầy đủ. Bảy bảng logic khác được giữ nguyên tên và cột. Hai fact dưới đây dùng bảng vật lý chuẩn hóa có hậu tố `_n`; view cùng tên logic giữ nguyên đầy đủ các cột và grain trong `docs/contract.md` để câu SQL hiện có vẫn chạy được:

- `fact_submission_n` bỏ `code_module`, `code_presentation` (tra qua `dim_assessment`) và `week_no` (tính từ `date_submitted`). View `fact_submission` phục hồi các cột này theo đúng thứ tự hợp đồng.
- `fact_vle_daily_n` bỏ `code_module`, `code_presentation` (tra qua `dim_vle_site`) và `week_no` (tính từ `date`). Khóa vật lý là (`id_student`, `id_site`, `date`); `id_site` xác định duy nhất đợt qua `dim_vle_site`. View `fact_vle_daily` phục hồi cột mã đợt và tuần, giữ grain hợp đồng.

PostgreSQL đặt khóa chính theo grain của các bảng vật lý. Hai view hợp đồng không có khóa chính vật lý. BigQuery không áp khóa chính cưỡng chế; builder kiểm tra số dòng và grain cả bảng vật lý lẫn view.

### Wide

Mỗi fact giữ một bảng riêng ở grain gốc. Một bảng wide chỉ lấy dữ liệu từ đúng một fact; các phép nối bổ sung chỉ đọc dimension có khóa duy nhất. Builder không nối hai fact khác grain.

| Bảng | Nguồn fact | Grain | Thuộc tính dimension bổ sung |
|---|---|---|---|
| `wide_enrollment` | `fact_enrollment` | Sinh viên × đợt | student, presentation |
| `wide_submission` | `fact_submission` | Sinh viên × bài nộp | student, assessment, presentation |
| `wide_vle_daily` | `fact_vle_daily` | Sinh viên × đợt × học liệu × ngày | student, site, presentation |
| `wide_student_week` | `fact_student_week` | Sinh viên × đợt × tuần | student, presentation, week |
| `wide_presentation` | `dim_presentation` | Một dòng mỗi đợt | Bản trình bày đầy đủ của `dim_presentation` |

Các cột fact gốc được giữ lại, gồm cả `final_result` trong `wide_enrollment`. Thuộc tính dimension dùng tên cột trực tiếp như `imd_band`, `assessment_type`, `activity_type`, `year` và `day_from`; chỉ đổi tên khi trùng với cột fact. `wide_student_week` không chứa `final_result` và không nối với `fact_enrollment`.

## Ghi lại và kiểm tra

Builder chỉ ghi vào schema/dataset đích tương ứng với `--engine`, `--scale` và `--layout` đã chọn. Nó tạo schema/dataset nếu chưa có và thay các bảng đích được chọn khi chạy lại. PostgreSQL thực hiện toàn bộ thao tác trong một transaction; lỗi sẽ rollback các thay đổi trong lần chạy. BigQuery dùng `CREATE OR REPLACE TABLE` cho từng bảng đích. Bảng nguồn star và các bảng đích layout khác không bị xóa hay ghi đè.

Trước khi sao chép bảng BigQuery, builder chạy dry-run cho từng câu `SELECT` vật lý và in ước lượng bytes nguồn. View tương thích logic không sao chép dữ liệu nên không có ước lượng copy riêng. Sau mỗi lần tạo bảng hoặc view, cả hai engine đều in số dòng đầu ra so với bảng nguồn và số khóa grain duy nhất. Nếu số dòng không khớp hoặc grain bị trùng, lệnh báo lỗi. Kiểm tra grain BigQuery đọc bảng/view đích nên có thể phát sinh bytes xử lý ngoài các ước lượng dry-run cho bước sao chép.

Các câu SQL benchmark dùng trực tiếp tên logic trong `docs/contract.md`. Với layout `3nf`, BR1 đọc view `fact_submission` được dựng từ `fact_submission_n`; view nối `dim_assessment` để khôi phục mã đợt và trường hợp đồng. BR2 đọc view `fact_vle_daily` được dựng từ `fact_vle_daily_n`; view nối `dim_vle_site` để khôi phục mã đợt và trường tuần. Như vậy hai workload này đi qua fact vật lý `_n` bằng các view hợp đồng.

BR4 và BR6 là workload đối chứng, giữ nguyên quy tắc nghiệp vụ và cột kết quả giữa các bố trí. Ở star và `3nf`, chúng dùng `fact_student_week`, `fact_enrollment` và dimension theo hợp đồng; ở wide, chúng dùng các bảng wide tương ứng. Có thể truy vấn bảng `_n` trực tiếp khi cần đo riêng thao tác trên fact đã chuẩn hóa. Khi xử lý ngày âm trong SQL khác, dùng `FLOOR(date / 7.0)` để giữ đúng quy ước trong [hợp đồng kho](contract.md).

### Bằng chứng PostgreSQL 1× — 20/10/2026

Đã kiểm tra nguồn `public` trước khi ghi: số dòng cả chín bảng khớp với Parquet 1×; các khóa chính đều trùng grain dự kiến. Lệnh `build_layouts.py --engine pg --scale 1 --layout all` tạo `three_nf` và `wide` thành công, kiểm tra số dòng và khóa grain cho mọi bảng/view. BR1/Q7, BR2/Q9, BR4/Q14 và BR6/Q18 sau đó chạy trên `star`, `3nf`, `wide`; mỗi workload có cùng số dòng và hash kết quả giữa ba layout. BR1 và BR4 ở đây là SQL benchmark-only, chưa được TV2 xác nhận là đáp án nghiệp vụ. Đây là bằng chứng dựng và parity PostgreSQL 1×, không phải đo hiệu năng; xem [báo cáo kiểm tra chi tiết](tv3_layout_pg_1x_validation.md).
