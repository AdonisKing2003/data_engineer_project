"""Việc 1.7: nạp mọi bảng trong data/warehouse vào PostgreSQL (kho đối chứng), rồi so số dòng.

- Cùng tên bảng, tên cột với BigQuery (docs/contract.md), schema public.
- Kiểu: int -> BIGINT, double -> DOUBLE PRECISION, string -> TEXT, bool -> BOOLEAN.
- Mỗi bảng một transaction: DROP, CREATE, COPY, thêm khóa chính, rồi mới COMMIT.
  Lỗi giữa chừng thì bảng cũ giữ nguyên; chạy lại không bị nhân đôi.
- Chỉ có khóa chính, chưa có chỉ mục nào khác: chỉ mục là việc của 1.11 (đo trước/sau).
- So số dòng với Parquet, và với BigQuery nếu đã chạy 04_load_bq.py.
- --scale N (việc 1.12): nạp kho nhân bản data/warehouse_<N>x vào schema x<N> (vd x5), cùng tên bảng.
  Chạy cùng một câu SQL trên hai kho chỉ cần đổi search_path: SET search_path TO x5;

Chạy trong container (không cần Spark):
    cd etl && python 05_load_pg.py              # nạp mọi bảng
    cd etl && python 05_load_pg.py dim_week     # chỉ nạp một vài bảng
    cd etl && python 05_load_pg.py --scale 5    # kho 5× vào schema x5
"""
import argparse
import io
import json
import os
import sys
import time

import psycopg
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.dataset as pads

from common import WAREHOUSE_DIR, give_back_to_owner, save_report, scaled_dir

PRIMARY_KEYS = {
    "dim_presentation": ["code_module", "code_presentation"],
    "dim_student": ["id_student"],
    "dim_assessment": ["id_assessment"],
    "dim_vle_site": ["id_site"],
    "dim_week": ["week_no"],
    "fact_enrollment": ["id_student", "code_module", "code_presentation"],
    "fact_vle_daily": ["id_student", "code_module", "code_presentation", "id_site", "date"],
    "fact_submission": ["id_student", "id_assessment"],
    "fact_student_week": ["id_student", "code_module", "code_presentation", "week_no"],
}


def pg_type(t: pa.DataType) -> str:
    if pa.types.is_integer(t):
        return "BIGINT"
    if pa.types.is_floating(t):
        return "DOUBLE PRECISION"
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return "TEXT"
    if pa.types.is_boolean(t):
        return "BOOLEAN"
    raise TypeError(f"chưa có kiểu PostgreSQL cho {t}")


def warehouse_tables(src):
    return sorted(p.name for p in src.iterdir()
                  if p.is_dir() and p.name.startswith(("dim_", "fact_")))


def bigquery_counts(src):
    p = src / "_report_04_load_bq.json"
    return {k: v["rows"] for k, v in json.loads(p.read_text()).items()} if p.exists() else {}


def load_table(conn, name, bq_rows, src=WAREHOUSE_DIR, schema="public"):
    t0 = time.time()
    # Đọc theo từng khối thay vì cả bảng, để bản 5× (42 triệu dòng click) không chiếm nhiều RAM.
    # Mặc định pyarrow bỏ qua file bắt đầu bằng "_" hoặc "." (_SUCCESS, .crc).
    data = pads.dataset(str(src / name), format="parquet")
    n_parquet = data.count_rows()
    cols = ", ".join(f'"{f.name}" {pg_type(f.type)}' for f in data.schema)
    names = ", ".join(f'"{f.name}"' for f in data.schema)
    table = f'"{schema}"."{name}"'
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        cur.execute(f"CREATE TABLE {table} ({cols})")
        # Đổ dữ liệu dạng CSV theo từng khối: ô trống không có dấu nháy = NULL, chuỗi luôn có dấu nháy
        with cur.copy(f"COPY {table} ({names}) FROM STDIN (FORMAT csv)") as copy:
            for batch in data.to_batches(batch_size=500_000):
                buf = io.BytesIO()
                pacsv.write_csv(batch, buf, pacsv.WriteOptions(include_header=False))
                copy.write(buf.getvalue())
        if name in PRIMARY_KEYS:
            key = ", ".join(f'"{c}"' for c in PRIMARY_KEYS[name])
            cur.execute(f"ALTER TABLE {table} ADD PRIMARY KEY ({key})")
        cur.execute(f"ANALYZE {table}")
        n_pg = cur.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    ok = n_pg == n_parquet and bq_rows.get(name, n_pg) == n_pg
    seconds = round(time.time() - t0, 1)
    bq = f", BigQuery {bq_rows[name]:,}" if name in bq_rows else ""
    print(f"{'OK ' if ok else 'SAI'} {name:22s} {n_pg:>12,} dòng trên PostgreSQL "
          f"(Parquet {n_parquet:,}{bq})  {seconds}s")
    return {"rows": n_pg, "expected": n_parquet, "bigquery": bq_rows.get(name),
            "ok": ok, "seconds": seconds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="*", help="chỉ nạp các bảng này (mặc định: mọi bảng)")
    ap.add_argument("--scale", type=int, default=1, help="nạp kho nhân bản N× vào schema xN (việc 1.12)")
    args = ap.parse_args()
    src = scaled_dir(args.scale)
    schema = "public" if args.scale == 1 else f"x{args.scale}"

    names = args.tables or (warehouse_tables(src) if src.is_dir() else [])
    missing = [n for n in names if not (src / n).is_dir()]
    if missing or not names:
        sys.exit(f"Không thấy bảng trong {src}: {missing or 'trống'}. "
                 f"Chạy {'make dims, make facts' if args.scale == 1 else 'make scale'} trước.")

    conninfo = (f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
                f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
                f"dbname={os.getenv('POSTGRES_DB', 'oulad')}")
    bq_rows = bigquery_counts(src)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        report = {name: load_table(conn, name, bq_rows, src, schema) for name in names}
    ok = save_report(report, "05_load_pg", src)
    give_back_to_owner(src)
    if not ok:
        sys.exit("Có bảng lệch số dòng giữa PostgreSQL, Parquet và BigQuery, xem log phía trên.")
    print(f"Xong 1.7: {len(names)} bảng đã vào PostgreSQL (schema {schema}), số dòng khớp Parquet và BigQuery.")


if __name__ == "__main__":
    main()
