"""Chạy một file SQL trên BigQuery, PostgreSQL hoặc DuckDB (Parquet), in kết quả và thời gian.

Viết SQL KHÔNG ghi tên dataset/schema trước tên bảng (FROM fact_enrollment, không phải FROM oulad.fact_enrollment).
Công cụ này tự chọn kho:
- BigQuery: default_dataset = <BQ_DATASET> (1×) hoặc <BQ_DATASET>_5x (--scale 5)
- PostgreSQL: search_path = public (1×) hoặc x5 (--scale 5)
- DuckDB: mỗi bảng trong data/warehouse (hoặc data/warehouse_5x) thành một view cùng tên
Mỗi file một câu SELECT. Cú pháp phải đúng với kho đang chạy (xem mục 4 của docs/contract.md).

Chạy trong container:
    python scripts/run_sql.py sql/questions/q01.sql                   # BigQuery 1×
    python scripts/run_sql.py sql/questions/q01.sql --engine pg       # PostgreSQL 1×
    python scripts/run_sql.py sql/questions/q01.sql --engine duckdb   # Parquet trên máy, không cần mạng
    python scripts/run_sql.py sql/questions/q01.sql --scale 5         # BigQuery 5×
"""
import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def run_bigquery(sql, scale):
    from google.cloud import bigquery
    project = os.environ["GCP_PROJECT_ID"]
    base = os.getenv("BQ_DATASET", "oulad")
    dataset = base if scale == 1 else f"{base}_{scale}x"
    client = bigquery.Client(project=project)
    job = client.query(sql, job_config=bigquery.QueryJobConfig(default_dataset=f"{project}.{dataset}"))
    df = job.result().to_dataframe(create_bqstorage_client=False)  # kết quả nhỏ, không cần Storage API
    return df, f"BigQuery {project}.{dataset}, quét {job.total_bytes_processed / 1e6:,.1f} MB"


def run_postgres(sql, scale):
    import psycopg
    schema = "public" if scale == 1 else f"x{scale}"
    conninfo = (f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
                f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
                f"dbname={os.getenv('POSTGRES_DB', 'oulad')}")
    with psycopg.connect(conninfo) as conn:
        conn.execute(f'SET search_path TO "{schema}"')
        cur = conn.execute(sql)
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    return df, f"PostgreSQL schema {schema}"


def run_duckdb(sql, scale):
    import duckdb
    wh = ROOT / "data" / ("warehouse" if scale == 1 else f"warehouse_{scale}x")
    con = duckdb.connect()
    for p in sorted(wh.iterdir()):
        if p.is_dir() and p.name.startswith(("dim_", "fact_")):
            con.sql(f"create view {p.name} as select * from read_parquet('{p}/*.parquet')")
    return con.sql(sql).df(), f"DuckDB trên {wh.relative_to(ROOT)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--engine", choices=["bq", "pg", "duckdb"], default="bq")
    ap.add_argument("--scale", type=int, default=1)
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        sys.exit(f"Không có file {path}")
    sql = path.read_text()
    t0 = time.time()
    df, where = {"bq": run_bigquery, "pg": run_postgres, "duckdb": run_duckdb}[args.engine](sql, args.scale)
    with pd.option_context("display.max_rows", 50, "display.max_columns", 20, "display.width", 160):
        print(df.to_string(index=False) if len(df) <= 50 else df)
    print(f"\n{len(df):,} dòng | {where} | {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
