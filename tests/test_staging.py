"""Test nhanh cho 1.3 (sau này gom vào bộ test 1.10).
Chạy:  pytest -q tests/test_staging.py
"""
from pathlib import Path

import duckdb
import pytest

STG = Path(__file__).resolve().parents[1] / "data" / "staging"

EXPECTED = {
    "stg_courses": 22,
    "stg_assessments": 206,
    "stg_vle": 6364,
    "stg_student_info": 32593,
    "stg_student_registration": 32593,
    "stg_student_assessment": 173912,
    "stg_student_vle": 10655280,
}


@pytest.mark.parametrize("table,expected", EXPECTED.items())
def test_row_count(table, expected):
    p = STG / table
    if not p.exists():
        pytest.skip(f"chưa chạy 01_staging.py ({table})")
    n = duckdb.sql(f"select count(*) from read_parquet('{p}/*.parquet')").fetchone()[0]
    assert n == expected


def test_date_columns_are_integers():
    p = STG / "stg_student_vle"
    if not p.exists():
        pytest.skip("chưa chạy 01_staging.py")
    t = duckdb.sql(f"select typeof(date) from read_parquet('{p}/*.parquet') limit 1").fetchone()[0]
    assert t == "INTEGER"
