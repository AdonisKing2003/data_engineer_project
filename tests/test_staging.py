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


# Phụ thuộc hàm làm căn cứ chuẩn hóa (docs/design_levels.md mục 2.4).
# Mỗi cặp: (bảng, vế trái, vế phải) -> số giá trị vế trái ứng với hơn một giá trị vế phải.
DEPENDENCIES = [
    ("stg_student_info", "id_student", "gender", 0),
    ("stg_student_info", "id_student", "region", 0),
    ("stg_student_info", "id_student", "highest_education", 0),
    ("stg_student_info", "id_student", "imd_band", 0),
    ("stg_student_info", "id_student", "disability", 0),
    # ba cột này đổi theo lượt đăng ký nên ở lại fact_enrollment
    ("stg_student_info", "id_student", "age_band", 72),
    ("stg_student_info", "id_student", "num_of_prev_attempts", 1403),
    ("stg_student_info", "id_student", "studied_credits", 1149),
    ("stg_vle", "id_site", "code_module || code_presentation", 0),
    ("stg_assessments", "id_assessment", "code_module || code_presentation", 0),
]


@pytest.mark.parametrize("table,lhs,rhs,violations", DEPENDENCIES)
def test_functional_dependency(table, lhs, rhs, violations):
    p = STG / table
    if not p.exists():
        pytest.skip(f"chưa chạy 01_staging.py ({table})")
    n = duckdb.sql(f"""
        select count(*) from (
            select {lhs} from read_parquet('{p}/*.parquet')
            group by {lhs} having count(distinct coalesce(cast({rhs} as varchar), 'NULL')) > 1
        )
    """).fetchone()[0]
    assert n == violations


def test_student_vle_has_no_key():
    """studentVle gốc có dòng trùng khóa nên chưa đạt 1NF; 03_facts.py gộp chúng thành fact_vle_daily."""
    p = STG / "stg_student_vle"
    if not p.exists():
        pytest.skip("chưa chạy 01_staging.py")
    groups, rows = duckdb.sql(f"""
        select count(*), sum(n) from (
            select count(*) as n from read_parquet('{p}/*.parquet')
            group by code_module, code_presentation, id_student, id_site, date having count(*) > 1
        )
    """).fetchone()
    assert (groups, rows) == (1614505, 3810465)
    assert 10655280 - rows + groups == 8459320  # = số dòng fact_vle_daily
