"""Việc 1.6: nạp mọi bảng trong data/warehouse lên BigQuery, rồi so số dòng.

- Mỗi bảng gộp các file part của Spark thành MỘT file Parquet và nạp bằng MỘT job WRITE_TRUNCATE:
  job thành công thì thay hẳn bảng cũ, thất bại thì bảng cũ giữ nguyên. Chạy lại không bị nhân đôi.
- Kiểu cột lấy theo Parquet: int -> INT64, double -> FLOAT64, string -> STRING, bool -> BOOL.
- Nạp file (load job) không tốn phí; số dòng đọc từ metadata của bảng nên cũng không tốn phí truy vấn.

Cần: .env có GCP_PROJECT_ID, BQ_DATASET, BQ_LOCATION; khóa ở secrets/gcp-key.json.
Chạy trong container (không cần Spark):
    cd etl && python 04_load_bq.py              # nạp mọi bảng
    cd etl && python 04_load_bq.py dim_week     # chỉ nạp một vài bảng
"""
import io
import os
import sys
import time

import pyarrow.parquet as pq
from google.cloud import bigquery

from common import WAREHOUSE_DIR, save_report


def warehouse_tables():
    return sorted(p.name for p in WAREHOUSE_DIR.iterdir()
                  if p.is_dir() and p.name.startswith(("dim_", "fact_")))


def load_table(client, dataset, name):
    t0 = time.time()
    table = pq.read_table(str(WAREHOUSE_DIR / name))  # bỏ qua _SUCCESS và .crc
    buf = io.BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    table_id = f"{dataset}.{name}"
    client.load_table_from_file(buf, table_id, job_config=job_config).result()
    n_bq = client.get_table(table_id).num_rows
    ok = n_bq == table.num_rows
    seconds = round(time.time() - t0, 1)
    print(f"{'OK ' if ok else 'SAI'} {name:22s} {n_bq:>12,} dòng trên BigQuery "
          f"(Parquet {table.num_rows:,})  {seconds}s")
    return {"rows": n_bq, "expected": table.num_rows, "ok": ok, "seconds": seconds}


def main():
    project = os.environ["GCP_PROJECT_ID"]
    dataset = f"{project}.{os.getenv('BQ_DATASET', 'oulad')}"
    location = os.getenv("BQ_LOCATION", "US")

    names = sys.argv[1:] or warehouse_tables()
    missing = [n for n in names if not (WAREHOUSE_DIR / n).is_dir()]
    if missing or not names:
        sys.exit(f"Không thấy bảng trong {WAREHOUSE_DIR}: {missing or 'trống'}. Chạy make dims, make facts trước.")

    client = bigquery.Client(project=project, location=location)
    ds = bigquery.Dataset(dataset)
    ds.location = location
    client.create_dataset(ds, exists_ok=True)

    report = {name: load_table(client, dataset, name) for name in names}
    if not save_report(report, "04_load_bq"):
        sys.exit("Có bảng lệch số dòng giữa BigQuery và Parquet, xem log phía trên.")
    print(f"Xong 1.6: {len(names)} bảng đã lên {dataset}, số dòng khớp Parquet. Báo nhóm!")


if __name__ == "__main__":
    main()
