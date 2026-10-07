"""Việc 1.2: nạp thử bảng courses lên BigQuery rồi truy vấn lại.
Chạy:  python scripts/bq_smoke_test.py
Cần: .env có GCP_PROJECT_ID, BQ_DATASET; file khóa ở secrets/gcp-key.json.
"""
import os
from pathlib import Path

from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
project = os.environ["GCP_PROJECT_ID"]
dataset = os.getenv("BQ_DATASET", "oulad")
location = os.getenv("BQ_LOCATION", "US")

client = bigquery.Client(project=project)

ds = bigquery.Dataset(f"{project}.{dataset}")
ds.location = location
client.create_dataset(ds, exists_ok=True)
print(f"Dataset {project}.{dataset} ({location}) sẵn sàng")

table_id = f"{project}.{dataset}.zz_test_courses"
job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.CSV,
    skip_leading_rows=1,
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # chạy lại không nhân đôi
    schema=[
        bigquery.SchemaField("code_module", "STRING"),
        bigquery.SchemaField("code_presentation", "STRING"),
        bigquery.SchemaField("module_presentation_length", "INT64"),
    ],
)
with open(ROOT / "data" / "raw" / "courses.csv", "rb") as f:
    client.load_table_from_file(f, table_id, job_config=job_config).result()

rows = list(client.query(
    f"SELECT COUNT(*) n, MIN(module_presentation_length) mn, MAX(module_presentation_length) mx "
    f"FROM `{table_id}`").result())
r = rows[0]
print(f"{table_id}: {r.n} dòng (chuẩn 22), độ dài khóa {r.mn}–{r.mx} ngày")
assert r.n == 22, "Số dòng không khớp 22"
print("Xong 1.2: BigQuery nạp và truy vấn được.")
