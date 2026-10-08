"""Test cho 1.7: kho PostgreSQL khớp cùng các con số với kho Parquet (sau này gom vào bộ test 1.10).
Dùng lại ROW_COUNTS và CHECKS của test_warehouse.py, nên hai kho được kiểm bằng đúng một bộ số.
Chạy:  pytest -q tests/test_postgres.py
"""
import os

import pytest

from test_warehouse import CHECKS, ROW_COUNTS

psycopg = pytest.importorskip("psycopg")


@pytest.fixture(scope="module")
def pg():
    conninfo = (f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
                f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
                f"dbname={os.getenv('POSTGRES_DB', 'oulad')}")
    try:
        conn = psycopg.connect(conninfo, connect_timeout=3, autocommit=True)
    except psycopg.OperationalError as e:
        pytest.skip(f"không kết nối được PostgreSQL: {e}")
    tables = {r[0] for r in conn.execute(
        "select table_name from information_schema.tables where table_schema = 'public'")}
    yield conn, tables
    conn.close()


def one(pg, table, sql):
    conn, tables = pg
    if table not in tables:
        pytest.skip(f"chưa chạy 05_load_pg.py ({table})")
    return conn.execute(sql).fetchone()[0]


@pytest.mark.parametrize("table,expected", ROW_COUNTS.items())
def test_row_count(pg, table, expected):
    assert one(pg, table, f"select count(*) from {table}") == expected


@pytest.mark.parametrize("table,cond,expected", CHECKS, ids=[f"{t}:{c}" for t, c, _ in CHECKS])
def test_flag_count(pg, table, cond, expected):
    assert one(pg, table, f"select count(*) from {table} where {cond}") == expected


def test_null_survives_copy(pg):
    """NULL phải vẫn là NULL sau khi đi qua CSV, không thành chuỗi rỗng hay số 0."""
    assert one(pg, "fact_submission", "select count(*) from fact_submission where score is null") == 173
    assert one(pg, "fact_submission", "select count(*) from fact_submission where is_pass_score is null") == 173
    assert one(pg, "dim_vle_site", "select count(*) from dim_vle_site where activity_type = ''") == 0


def test_click_total(pg):
    assert one(pg, "fact_vle_daily", "select sum(sum_click) from fact_vle_daily") == 39605099


def test_br1_tma_late_rate(pg):
    """Đáp án câu 7: tỷ lệ trễ chung của TMA = 16,8%."""
    rate = one(pg, "fact_submission", """select avg(s.is_late::int) from fact_submission s
                                         join dim_assessment a using (id_assessment)
                                         where a.assessment_type = 'TMA' and not s.is_banked""")
    assert round(float(rate) * 100, 1) == 16.8
