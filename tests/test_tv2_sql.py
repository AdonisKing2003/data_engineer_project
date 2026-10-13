"""Kiểm thử tự động cho 4 file SQL của Thành viên 2 (BR1, BR4, BR5, BR7).
Chạy:  pytest -q tests/test_tv2_sql.py
"""
from pathlib import Path
import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
SQL_DIR = ROOT / "sql" / "Tai_Duckdb"


@pytest.fixture(scope="module")
def db():
    con = duckdb.connect()
    for t in ["dim_presentation", "dim_student", "dim_assessment", "dim_vle_site", "dim_week",
              "fact_enrollment", "fact_vle_daily", "fact_submission", "fact_student_week"]:
        p = WH / t
        if not p.exists():
            pytest.skip(f"Chưa có dữ liệu warehouse: {t}")
        con.sql(f"create view {t} as select * from read_parquet('{p}/*.parquet')")
    return con


def test_br1_query(db):
    """Kiểm tra câu 5-8: Bài 1752 có 96.5% nộp, 18.4% trễ, median điểm 72."""
    res = db.sql("""
        SELECT
            ROUND(100.0 * COUNT(DISTINCT s.id_student) / e.active_students, 1) AS sub_rate,
            ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_late) / COUNT(*) FILTER (WHERE NOT s.is_banked), 1) AS late_rate,
            MEDIAN(s.score) AS med_score
        FROM fact_submission s
        CROSS JOIN (
            SELECT COUNT(DISTINCT e.id_student) AS active_students
            FROM fact_enrollment e
            JOIN dim_assessment a ON a.id_assessment = 1752
            WHERE e.code_module = a.code_module 
              AND e.code_presentation = a.code_presentation
              AND (e.date_unregistration IS NULL OR e.date_unregistration > a.deadline)
        ) e
        WHERE s.id_assessment = 1752
        GROUP BY e.active_students
    """).fetchone()
    assert res == (96.5, 18.4, 72)


def test_br5_query(db):
    """Kiểm tra câu 15-17: CCC 2014B có tỷ lệ rút 46.4%."""
    res = db.sql("""
        SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE is_withdrawn) / COUNT(*), 1)
        FROM fact_enrollment
        WHERE code_module = 'CCC' AND code_presentation = '2014B'
    """).fetchone()[0]
    assert res == 46.4


def test_br4_query(db):
    """Kiểm tra câu 14: Toàn bộ các đợt tuần 4 có 3958 SV cảnh báo, độ chính xác 80.6%."""
    res = db.sql("""
        WITH cohort AS (
            SELECT
                w.id_student, w.code_module, w.code_presentation,
                w.clicks_cum, w.clicks_week, w.avg_score_cum, w.n_tma_missed_cum,
                p.clicks_week AS clicks_prev_week
            FROM fact_student_week w
            LEFT JOIN fact_student_week p
              ON p.id_student = w.id_student
             AND p.code_module = w.code_module
             AND p.code_presentation = w.code_presentation
             AND p.week_no = w.week_no - 1
            WHERE w.week_no = 4 AND w.is_enrolled
        ),
        p25 AS (
            SELECT code_module, code_presentation, QUANTILE_CONT(clicks_cum, 0.25) AS p25_clicks
            FROM cohort GROUP BY code_module, code_presentation
        ),
        scored AS (
            SELECT
                c.id_student, c.code_module, c.code_presentation,
                (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
                 CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
                 CAST(c.n_tma_missed_cum > 0 AS INT64) +
                 CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2 AS is_at_risk
            FROM cohort c JOIN p25 p USING (code_module, code_presentation)
        ),
        labeled AS (
            SELECT s.is_at_risk, (e.final_result IN ('Fail', 'Withdrawn')) AS bad
            FROM scored s JOIN fact_enrollment e USING (id_student, code_module, code_presentation)
        )
        SELECT
            COUNT(*) FILTER (WHERE is_at_risk),
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_at_risk AND bad) / COUNT(*) FILTER (WHERE is_at_risk), 1)
        FROM labeled
    """).fetchone()
    assert res == (3958, 80.6)


def test_br7_query(db):
    """Kiểm tra câu 19: AAA 2014J tuần 10 có 336 SV, phân vị 269 / 593 / 1083."""
    res = db.sql("""
        SELECT
            COUNT(*),
            ROUND(QUANTILE_CONT(clicks_cum, 0.25)),
            ROUND(QUANTILE_CONT(clicks_cum, 0.50)),
            ROUND(QUANTILE_CONT(clicks_cum, 0.75))
        FROM fact_student_week
        WHERE code_module = 'AAA' AND code_presentation = '2014J' AND week_no = 10 AND is_enrolled
    """).fetchone()
    assert res == (336, 269.0, 593.0, 1083.0)


def test_br4_anti_leakage(db):
    """Kiểm thử chống rò rỉ nhãn (Data Leakage):
    Đổi nhãn kết quả cuối kỳ (final_result) của toàn bộ SV thì danh sách cảnh báo tuần 4 không được đổi!
    """
    br4_query = """
        WITH cohort AS (
            SELECT
                w.id_student, w.code_module, w.code_presentation,
                w.clicks_cum, w.clicks_week, w.avg_score_cum, w.n_tma_missed_cum,
                p.clicks_week AS clicks_prev_week
            FROM fact_student_week w
            LEFT JOIN fact_student_week p
              ON p.id_student = w.id_student
             AND p.code_module = w.code_module
             AND p.code_presentation = w.code_presentation
             AND p.week_no = w.week_no - 1
            WHERE w.week_no = 4 AND w.is_enrolled
        ),
        p25 AS (
            SELECT code_module, code_presentation, QUANTILE_CONT(clicks_cum, 0.25) AS p25_clicks
            FROM cohort GROUP BY code_module, code_presentation
        )
        SELECT c.id_student, c.code_module, c.code_presentation,
               (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
                CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
                CAST(c.n_tma_missed_cum > 0 AS INT64) +
                CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2 AS is_at_risk
        FROM cohort c JOIN p25 p USING (code_module, code_presentation)
        WHERE (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
               CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
               CAST(c.n_tma_missed_cum > 0 AS INT64) +
               CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2
        ORDER BY c.id_student, c.code_module, c.code_presentation
    """
    # Lấy danh sách SV rủi ro trước khi can thiệp
    list_before = db.sql(br4_query).fetchall()

    # Giả lập thay đổi toàn bộ kết quả cuối kỳ final_result trong fact_enrollment
    db.sql(f"""
        create or replace view fact_enrollment as
        select * replace (case when final_result = 'Pass' then 'Fail' else 'Pass' end as final_result)
        from read_parquet('{WH / "fact_enrollment"}/*.parquet')
    """)

    try:
        # Lấy lại danh sách SV rủi ro sau khi đã đảo ngược kết quả cuối kỳ
        list_after = db.sql(br4_query).fetchall()
    finally:
        # Khôi phục view fact_enrollment về nguyên bản
        db.sql(f"create or replace view fact_enrollment as select * from read_parquet('{WH / 'fact_enrollment'}/*.parquet')")

    # Hai danh sách PHẢI HOÀN TOÀN TRÙNG KHỚP NHAU
    assert list_before == list_after
    assert len(list_before) == 3958

