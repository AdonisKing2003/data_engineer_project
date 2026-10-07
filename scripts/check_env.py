"""Việc 1.1b: kiểm tra container có đủ đồ nghề chưa.
Chạy:  python scripts/check_env.py
"""
import os
import sys

ok = True


def step(name, fn):
    global ok
    try:
        msg = fn()
        print(f"[OK ] {name}: {msg}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"[SAI] {name}: {e}")


def spark():
    from pyspark.sql import SparkSession
    s = SparkSession.builder.master("local[2]").appName("check").getOrCreate()
    n = s.range(1_000_000).count()
    v = s.version
    s.stop()
    return f"Spark {v}, đếm được {n:,} dòng"


def duckdb_():
    import duckdb
    return f"DuckDB {duckdb.__version__}, 1+1={duckdb.sql('select 1+1').fetchone()[0]}"


def streamlit_():
    import streamlit
    return f"Streamlit {streamlit.__version__}"


def postgres():
    import psycopg
    conninfo = (f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
                f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
                f"dbname={os.getenv('POSTGRES_DB', 'oulad')}")
    with psycopg.connect(conninfo, connect_timeout=5) as c:
        return c.execute("select version()").fetchone()[0].split(",")[0]


def bigquery():
    key = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not key or not os.path.exists(key):
        raise RuntimeError(f"chưa có file khóa ở '{key}' (bỏ qua nếu chưa làm 1.2)")
    from google.cloud import bigquery as bq
    c = bq.Client(project=os.getenv("GCP_PROJECT_ID"))
    return f"kết nối project {c.project}, query thử = {list(c.query('select 1 x').result())[0].x}"


step("Spark", spark)
step("DuckDB", duckdb_)
step("Streamlit", streamlit_)
step("PostgreSQL", postgres)
step("BigQuery", bigquery)
sys.exit(0 if ok else 1)
