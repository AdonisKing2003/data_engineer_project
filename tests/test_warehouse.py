"""Test cho 1.4, 1.5: kho khớp cột "Kiểm" trong docs/contract.md (sau này gom vào bộ test 1.10).
Chạy:  pytest -q tests/test_warehouse.py
"""
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
STG = ROOT / "data" / "staging"

TABLES = ["dim_presentation", "dim_student", "dim_assessment", "dim_vle_site", "dim_week",
          "fact_enrollment", "fact_vle_daily", "fact_submission"]


@pytest.fixture(scope="module")
def db():
    con = duckdb.connect()
    for t in TABLES:
        if (WH / t).exists():
            con.sql(f"create view {t} as select * from read_parquet('{WH / t}/*.parquet')")
    return con


def need(*tables):
    missing = [t for t in tables if not (WH / t).exists()]
    if missing:
        pytest.skip(f"chưa chạy ETL ({', '.join(missing)})")


def one(db, sql):
    return db.sql(sql).fetchone()[0]


ROW_COUNTS = {
    "dim_presentation": 22,
    "dim_student": 28785,
    "dim_assessment": 206,
    "dim_vle_site": 6364,
    "dim_week": 43,
    "fact_enrollment": 32593,
    "fact_vle_daily": 8459320,
    "fact_submission": 173912,
}


@pytest.mark.parametrize("table,expected", ROW_COUNTS.items())
def test_row_count(db, table, expected):
    need(table)
    assert one(db, f"select count(*) from {table}") == expected


# (bảng, điều kiện, số dòng thỏa) — cột "Kiểm" của docs/contract.md
CHECKS = [
    ("dim_presentation", "has_exam_result", 6),
    ("dim_presentation", "has_weighted_tma", 19),
    ("dim_student", "imd_unknown", 971),
    ("dim_student", "imd_band = '10-20'", 0),
    ("dim_student", "imd_band is null", 0),
    ("dim_assessment", "assessment_type = 'TMA'", 106),
    ("dim_assessment", "assessment_type = 'CMA'", 76),
    ("dim_assessment", "assessment_type = 'Exam'", 24),
    ("dim_assessment", "deadline_raw is null", 11),
    ("dim_assessment", "deadline is null", 0),
    ("dim_assessment", "deadline_imputed", 11),
    ("dim_assessment", "zero_weight", 56),
    ("dim_assessment", "is_first_weighted_tma", 19),
    ("dim_assessment", "has_submissions", 188),
    ("dim_vle_site", "has_planned_week", 1121),
    ("dim_vle_site", "never_clicked", 96),
    ("dim_week", "is_pre_start", 4),
    ("fact_vle_daily", "n_records > 1", 1614505),
    ("fact_vle_daily", "is_pre_start", 600241),
    ("fact_submission", "is_banked", 1909),
    ("fact_submission", "is_late", 16320),
    ("fact_submission", "is_late and is_banked", 0),
    ("fact_submission", "score_missing", 173),
    ("fact_submission", "is_beyond_course", 85),
    ("fact_submission", "is_pass_score", 166161),
    ("fact_submission", "days_late is null", 1909),
    ("fact_enrollment", "date_registration is null", 45),
    ("fact_enrollment", "is_withdrawn", 10156),
    ("fact_enrollment", "withdrawn_before_start", 3097),
    ("fact_enrollment", "no_vle_activity", 3365),
    ("fact_enrollment", "reg_date_missing", 45),
    ("fact_enrollment", "result_inconsistent", 102),
    ("fact_enrollment", "is_repeat", 4172),
]


@pytest.mark.parametrize("table,cond,expected", CHECKS, ids=[f"{t}:{c}" for t, c, _ in CHECKS])
def test_flag_count(db, table, cond, expected):
    need(table)
    assert one(db, f"select count(*) from {table} where {cond}") == expected


PRIMARY_KEYS = {
    "dim_presentation": "code_module, code_presentation",
    "dim_student": "id_student",
    "dim_assessment": "id_assessment",
    "dim_vle_site": "id_site",
    "dim_week": "week_no",
    "fact_enrollment": "id_student, code_module, code_presentation",
    "fact_vle_daily": "id_student, code_module, code_presentation, id_site, date",
    "fact_submission": "id_student, id_assessment",
}


@pytest.mark.parametrize("table,key", PRIMARY_KEYS.items())
def test_primary_key_unique(db, table, key):
    need(table)
    assert one(db, f"select count(*) - count(distinct ({key})) from {table}") == 0


# (bảng con, cột, bảng cha, cột) — không có khóa ngoại mồ côi
FOREIGN_KEYS = [
    ("fact_vle_daily", "id_student", "dim_student", "id_student"),
    ("fact_vle_daily", "id_site", "dim_vle_site", "id_site"),
    ("fact_vle_daily", "week_no", "dim_week", "week_no"),
    ("fact_vle_daily", "code_module || code_presentation", "dim_presentation", "code_module || code_presentation"),
    ("fact_submission", "id_student", "dim_student", "id_student"),
    ("fact_submission", "id_assessment", "dim_assessment", "id_assessment"),
    ("fact_enrollment", "id_student", "dim_student", "id_student"),
    ("fact_enrollment", "code_module || code_presentation", "dim_presentation", "code_module || code_presentation"),
]


@pytest.mark.parametrize("child,ccol,parent,pcol", FOREIGN_KEYS,
                         ids=[f"{c}.{cc}->{p}" for c, cc, p, _ in FOREIGN_KEYS])
def test_no_orphan_keys(db, child, ccol, parent, pcol):
    need(child, parent)
    assert one(db, f"select count(*) from {child} c where ({ccol}) not in (select {pcol} from {parent})") == 0


def test_click_total_matches_source(db):
    need("fact_vle_daily", "fact_enrollment")
    assert one(db, "select sum(sum_click) from fact_vle_daily") == 39605099
    assert one(db, "select sum(total_clicks) from fact_enrollment") == 39605099
    p = STG / "stg_student_vle"
    if p.exists():
        src = one(db, f"select sum(sum_click) from read_parquet('{p}/*.parquet')")
        assert src == 39605099


def test_score_total_matches_source(db):
    need("fact_submission")
    p = STG / "stg_student_assessment"
    if not p.exists():
        pytest.skip("chưa chạy 01_staging.py")
    src = one(db, f"select sum(score) from read_parquet('{p}/*.parquet')")
    assert one(db, "select sum(score) from fact_submission") == src


def test_first_weighted_tma_bbb_2014j(db):
    """BBB 2014J: bài hạn ngày 19 có trọng số 0, nên TMA đầu tiên phải là 15021."""
    need("dim_assessment")
    got = one(db, """select id_assessment from dim_assessment
                     where is_first_weighted_tma and code_module = 'BBB' and code_presentation = '2014J'""")
    assert got == 15021


def test_week_no_is_floor(db):
    """Ngày −1 phải thuộc tuần −1, không phải tuần 0."""
    need("fact_vle_daily")
    assert one(db, "select count(*) from fact_vle_daily where week_no <> floor(date / 7)") == 0
    assert one(db, "select distinct week_no from fact_vle_daily where date = -1") == -1


def test_br1_tma_late_rate(db):
    """Đáp án câu 7: tỷ lệ trễ chung của TMA = 16,8%."""
    need("fact_submission", "dim_assessment")
    rate = one(db, """select avg(is_late::int) from fact_submission s
                      join dim_assessment a using (id_assessment)
                      where a.assessment_type = 'TMA' and not s.is_banked""")
    assert round(rate * 100, 1) == 16.8
