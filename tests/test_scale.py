"""Test cho 1.12: kho nhân bản 5× (data/warehouse_5x, BigQuery oulad_5x, PostgreSQL schema x5).
Chạy:  pytest -q tests/test_scale.py
"""
import json
import os
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
WH1 = ROOT / "data" / "warehouse"
WH5 = ROOT / "data" / "warehouse_5x"
FACTOR, OFFSET = 5, 10_000_000
STUDENT_TABLES = ["dim_student", "fact_enrollment", "fact_vle_daily", "fact_submission", "fact_student_week"]
STATIC_TABLES = ["dim_presentation", "dim_assessment", "dim_vle_site", "dim_week"]
PRIMARY_KEYS = {
    "dim_student": "id_student",
    "fact_enrollment": "id_student, code_module, code_presentation",
    "fact_vle_daily": "id_student, code_module, code_presentation, id_site, date",
    "fact_submission": "id_student, id_assessment",
    "fact_student_week": "id_student, code_module, code_presentation, week_no",
}


@pytest.fixture(scope="module")
def db():
    if not WH5.exists():
        pytest.skip("chưa chạy make scale")
    con = duckdb.connect()
    for t in STUDENT_TABLES + STATIC_TABLES:
        con.sql(f"create view w1_{t} as select * from read_parquet('{WH1 / t}/*.parquet')")
        con.sql(f"create view w5_{t} as select * from read_parquet('{WH5 / t}/*.parquet')")
    return con


def one(db, sql):
    return db.sql(sql).fetchone()


@pytest.mark.parametrize("table", STUDENT_TABLES + STATIC_TABLES)
def test_row_count_scaled(db, table):
    n1, n5 = one(db, f"select (select count(*) from w1_{table}), (select count(*) from w5_{table})")
    assert n5 == n1 * (FACTOR if table in STUDENT_TABLES else 1)


@pytest.mark.parametrize("table,key", PRIMARY_KEYS.items())
def test_primary_key_unique(db, table, key):
    assert one(db, f"select count(*) - count(distinct ({key})) from w5_{table}")[0] == 0


def test_each_copy_is_complete(db):
    """Bản i có id_student = mã gốc + i × 10.000.000; mỗi bản có đủ 28.785 SV, bản 0 là mã gốc."""
    rows = db.sql("select id_student // 10000000 as copy_no, count(*) from w5_dim_student group by 1 order by 1").fetchall()
    assert rows == [(i, 28785) for i in range(FACTOR)]
    assert one(db, "select count(*) from w5_dim_student s join w1_dim_student o using (id_student)")[0] == 28785


def test_rates_unchanged(db):
    """Chép nguyên vẹn nên mọi tỷ lệ trên kho 5× bằng kho 1×."""
    late = """select round(100 * avg(is_late::int), 4) from {p}_fact_submission s
              join {p}_dim_assessment a using (id_assessment)
              where a.assessment_type = 'TMA' and not s.is_banked"""
    withdrawn = "select round(100 * avg(is_withdrawn::int), 4) from {p}_fact_enrollment"
    for sql in [late, withdrawn]:
        assert one(db, sql.format(p="w5")) == one(db, sql.format(p="w1"))


def test_click_distribution_unchanged(db):
    """Trung bình, độ lệch chuẩn, min, max của click theo từng đợt giữ nguyên; tổng gấp 5."""
    sql = """select code_module, code_presentation, round(avg(sum_click), 6), round(stddev_pop(sum_click), 6),
                    min(sum_click), max(sum_click)
             from {p}_fact_vle_daily group by all order by all"""
    assert db.sql(sql.format(p="w5")).fetchall() == db.sql(sql.format(p="w1")).fetchall()
    assert one(db, "select sum(sum_click) from w5_fact_vle_daily")[0] == 39605099 * FACTOR


def test_bigquery_loaded():
    p = WH5 / "_report_04_load_bq.json"
    if not p.exists():
        pytest.skip("chưa nạp kho 5× lên BigQuery")
    report = json.loads(p.read_text())
    assert report["fact_vle_daily"]["rows"] == 8459320 * FACTOR
    assert all(r["ok"] for r in report.values())


def test_postgres_loaded():
    psycopg = pytest.importorskip("psycopg")
    conninfo = (f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
                f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
                f"dbname={os.getenv('POSTGRES_DB', 'oulad')}")
    try:
        conn = psycopg.connect(conninfo, connect_timeout=3)
    except psycopg.OperationalError as e:
        pytest.skip(f"không kết nối được PostgreSQL: {e}")
    with conn:
        tables = {r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema = 'x5'")}
        if "fact_vle_daily" not in tables:
            pytest.skip("chưa nạp kho 5× vào PostgreSQL")
        assert conn.execute("select count(*) from x5.fact_vle_daily").fetchone()[0] == 8459320 * FACTOR
        assert conn.execute("select count(*) from x5.fact_student_week").fetchone()[0] == 1342949 * FACTOR
        assert conn.execute("select count(*) from x5.dim_presentation").fetchone()[0] == 22
