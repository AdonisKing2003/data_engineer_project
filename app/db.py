"""Module kết nối và đóng gói toàn bộ các hàm nghiệp vụ truy vấn dữ liệu từ kho Parquet (DuckDB) cho ứng dụng Streamlit."""
from pathlib import Path
from typing import List, Optional
import duckdb
import pandas as pd
import streamlit as st

# Tự động nhận diện đường dẫn thư mục warehouse dù chạy từ Windows host hay bên trong Docker
APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
WAREHOUSE_DIR = PROJECT_DIR / "data" / "warehouse"


@st.cache_resource
def get_connection():
    """Khởi tạo kết nối DuckDB in-memory và đăng ký các view trỏ tới Parquet warehouse."""
    con = duckdb.connect(database=":memory:")
    
    tables = [
        "dim_presentation",
        "dim_student",
        "dim_assessment",
        "dim_vle_site",
        "dim_week",
        "fact_enrollment",
        "fact_vle_daily",
        "fact_submission",
        "fact_student_week",
    ]
    
    for table in tables:
        table_path = WAREHOUSE_DIR / table
        if table_path.exists():
            con.execute(f"CREATE OR REPLACE VIEW {table} AS SELECT * FROM read_parquet('{table_path.as_posix()}/*.parquet')")
    
    return con


@st.cache_data(ttl=3600, show_spinner=False)
def run_query(sql: str, params: Optional[list] = None) -> pd.DataFrame:
    """Thực thi câu truy vấn SQL và trả về DataFrame với bộ nhớ đệm (cache)."""
    con = get_connection()
    if params:
        return con.execute(sql, params).df()
    return con.execute(sql).df()


# ==============================================================================
# HÀM THỐNG KÊ TỔNG QUAN & DANH MỤC
# ==============================================================================

@st.cache_data(ttl=3600)
def get_presentations() -> pd.DataFrame:
    """Lấy danh sách các đợt học có sẵn trong kho."""
    sql = """
        SELECT DISTINCT code_module, code_presentation,
               code_module || ' ' || code_presentation AS presentation_label
        FROM dim_presentation
        ORDER BY code_module, code_presentation
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def get_overall_stats() -> dict:
    """Lấy số liệu thống kê tổng quát toàn trường."""
    sql = """
        SELECT 
            (SELECT COUNT(*) FROM dim_student) AS total_students,
            (SELECT COUNT(*) FROM fact_enrollment) AS total_enrollments,
            (SELECT COUNT(*) FROM dim_presentation) AS total_presentations,
            (SELECT COUNT(*) FROM dim_assessment) AS total_assessments
    """
    return run_query(sql).iloc[0].to_dict()


# ==============================================================================
# BR1: NỘP BÀI, TRỄ HẠN & PHÂN PHỐI ĐIỂM
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br1_assessment_stats(code_module: str, code_presentation: str) -> pd.DataFrame:
    """Lấy thống kê tỷ lệ nộp bài, nộp trễ và các phân vị điểm số theo từng bài kiểm tra."""
    sql = """
    WITH assessment_meta AS (
        SELECT
            a.id_assessment,
            a.code_module,
            a.code_presentation,
            a.assessment_type,
            a.deadline,
            a.weight,
            a.assessment_order,
            a.is_first_weighted_tma
        FROM dim_assessment a
        WHERE a.code_module = ? AND a.code_presentation = ?
    ),
    enrolled_at_deadline AS (
        SELECT
            a.id_assessment,
            COUNT(DISTINCT e.id_student) AS n_active_students
        FROM assessment_meta a
        JOIN fact_enrollment e
          ON e.code_module = a.code_module
         AND e.code_presentation = a.code_presentation
        WHERE e.date_unregistration IS NULL OR e.date_unregistration > a.deadline
        GROUP BY a.id_assessment
    ),
    submission_stats AS (
        SELECT
            s.id_assessment,
            COUNT(DISTINCT s.id_student) AS n_submitted_total,
            COUNT(DISTINCT s.id_student) FILTER (WHERE NOT s.is_banked) AS n_submitted_regular,
            COUNT(DISTINCT s.id_student) FILTER (WHERE s.is_banked) AS n_banked,
            COUNT(DISTINCT s.id_student) FILTER (WHERE s.is_late) AS n_late,
            ROUND(MEDIAN(s.score) FILTER (WHERE NOT s.score_missing), 1) AS median_score,
            ROUND(QUANTILE_CONT(s.score, 0.25) FILTER (WHERE NOT s.score_missing), 1) AS p25_score,
            ROUND(QUANTILE_CONT(s.score, 0.75) FILTER (WHERE NOT s.score_missing), 1) AS p75_score,
            ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_pass_score) / COUNT(*) FILTER (WHERE NOT s.score_missing), 1) AS pass_rate_pct
        FROM fact_submission s
        WHERE s.code_module = ? AND s.code_presentation = ?
        GROUP BY s.id_assessment
    )
    SELECT
        a.id_assessment,
        a.assessment_type || ' ' || CAST(a.id_assessment AS VARCHAR) AS assessment_label,
        a.assessment_type,
        a.assessment_order,
        a.deadline,
        a.weight,
        a.is_first_weighted_tma,
        COALESCE(e.n_active_students, 0) AS active_students,
        COALESCE(s.n_submitted_regular, 0) AS submitted_regular,
        COALESCE(s.n_banked, 0) AS banked_students,
        COALESCE(s.n_late, 0) AS late_submissions,
        CASE 
            WHEN COALESCE(e.n_active_students, 0) = 0 THEN 0.0
            ELSE ROUND(100.0 * COALESCE(s.n_submitted_regular, 0) / e.n_active_students, 1)
        END AS submission_rate_pct,
        CASE 
            WHEN COALESCE(s.n_submitted_regular, 0) = 0 OR a.assessment_type != 'TMA' THEN 0.0
            ELSE ROUND(100.0 * COALESCE(s.n_late, 0) / s.n_submitted_regular, 1)
        END AS late_rate_pct,
        s.p25_score,
        s.median_score,
        s.p75_score,
        s.pass_rate_pct
    FROM assessment_meta a
    LEFT JOIN enrolled_at_deadline e USING (id_assessment)
    LEFT JOIN submission_stats s USING (id_assessment)
    ORDER BY a.deadline, a.id_assessment;
    """
    return run_query(sql, [code_module, code_presentation, code_module, code_presentation])


@st.cache_data(ttl=3600)
def get_br1_assessment_scores(code_module: str, code_presentation: str) -> pd.DataFrame:
    """Lấy danh sách điểm số chi tiết của từng bài kiểm tra để vẽ biểu đồ Box Plot."""
    sql = """
    SELECT 
        a.assessment_type || ' ' || CAST(a.id_assessment AS VARCHAR) AS assessment_label,
        a.deadline,
        s.score
    FROM dim_assessment a
    JOIN fact_submission s USING (id_assessment)
    WHERE a.code_module = ? AND a.code_presentation = ?
      AND s.score IS NOT NULL
    ORDER BY a.deadline, a.id_assessment
    """
    return run_query(sql, [code_module, code_presentation])


# ==============================================================================
# BR4: CẢNH BÁO SỚM THEO TUẦN (WEEKLY SNAPSHOT AS-OF)
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br4_at_risk_students(
    code_module: Optional[str] = None,
    code_presentation: Optional[str] = None,
    week_no: int = 4
) -> pd.DataFrame:
    """
    Truy vấn cảnh báo sớm sinh viên có nguy cơ học tập tại tuần week_no.
    Nếu code_module và code_presentation được chỉ định, lọc theo đợt học; ngược lại tính toàn trường.
    """
    filter_pres_clause = ""
    params = [week_no]
    if code_module and code_presentation:
        filter_pres_clause = "AND w.code_module = ? AND w.code_presentation = ?"
        params.extend([code_module, code_presentation])

    sql = f"""
    WITH cohort AS (
        SELECT
            w.id_student,
            w.code_module,
            w.code_presentation,
            w.week_no,
            w.clicks_cum,
            w.clicks_week,
            w.avg_score_cum,
            w.n_tma_missed_cum,
            p.clicks_week AS clicks_prev_week
        FROM fact_student_week w
        LEFT JOIN fact_student_week p
          ON p.id_student = w.id_student
         AND p.code_module = w.code_module
         AND p.code_presentation = w.code_presentation
         AND p.week_no = w.week_no - 1
        WHERE w.week_no = ?
          AND w.is_enrolled
          {filter_pres_clause}
    ),
    cohort_p25 AS (
        SELECT
            code_module,
            code_presentation,
            QUANTILE_CONT(clicks_cum, 0.25) AS p25_clicks
        FROM cohort
        GROUP BY code_module, code_presentation
    ),
    scored AS (
        SELECT
            c.id_student,
            c.code_module,
            c.code_presentation,
            c.clicks_cum,
            c.clicks_week,
            c.avg_score_cum,
            c.n_tma_missed_cum,
            p.p25_clicks,
            (c.clicks_cum < p.p25_clicks) AS flag_low_clicks,
            (c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0) AS flag_inactive_2w,
            (c.n_tma_missed_cum > 0) AS flag_missed_tma,
            (COALESCE(c.avg_score_cum < 40, FALSE)) AS flag_low_score,
            (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
             CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
             CAST(c.n_tma_missed_cum > 0 AS INT64) +
             CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) AS risk_score
        FROM cohort c
        JOIN cohort_p25 p USING (code_module, code_presentation)
    )
    SELECT
        s.*,
        e.final_result,
        (e.final_result IN ('Fail', 'Withdrawn')) AS is_unsuccessful
    FROM scored s
    LEFT JOIN fact_enrollment e 
      ON e.id_student = s.id_student 
     AND e.code_module = s.code_module 
     AND e.code_presentation = s.code_presentation
    """
    return run_query(sql, params)


# ==============================================================================
# BR5: ĐƯỜNG CONG RÚT LUI TÍCH LŨY & TỶ LỆ DUY TRÌ
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br5_withdrawal_summary() -> pd.DataFrame:
    """Lấy thống kê tỷ lệ rút lui của toàn bộ 22 đợt học tại các mốc ngày then chốt (ngày 0, ngày 27)."""
    sql = """
    WITH presentation_base AS (
        SELECT code_module, code_presentation, COUNT(*) AS total_students
        FROM fact_enrollment
        GROUP BY code_module, code_presentation
    ),
    presentation_milestones AS (
        SELECT
            e.code_module,
            e.code_presentation,
            COUNT(*) FILTER (WHERE e.is_withdrawn AND e.date_unregistration <= 0) AS with_day_0,
            COUNT(*) FILTER (WHERE e.is_withdrawn AND e.date_unregistration <= 27) AS with_day_27,
            COUNT(*) FILTER (WHERE e.is_withdrawn) AS with_total,
            MEDIAN(e.date_unregistration) FILTER (WHERE e.is_withdrawn AND e.date_unregistration IS NOT NULL) AS median_unreg_day
        FROM fact_enrollment e
        GROUP BY e.code_module, e.code_presentation
    )
    SELECT
        m.code_module || ' ' || m.code_presentation AS presentation,
        b.total_students,
        m.with_day_0,
        ROUND(100.0 * m.with_day_0 / b.total_students, 1) AS pct_withdrawn_day_0,
        m.with_day_27,
        ROUND(100.0 * m.with_day_27 / b.total_students, 1) AS pct_withdrawn_day_27,
        m.with_total,
        ROUND(100.0 * m.with_total / b.total_students, 1) AS pct_withdrawn_total,
        m.median_unreg_day
    FROM presentation_milestones m
    JOIN presentation_base b USING (code_module, code_presentation)
    ORDER BY pct_withdrawn_total DESC;
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def get_br5_retention_curve(cohorts: List[str]) -> pd.DataFrame:
    """
    Truy vấn đường cong rút lui tích lũy theo tuần cho danh sách các đợt học được chọn.
    cohorts: Danh sách chuỗi có định dạng ['BBB 2014J', 'CCC 2014B', ...]
    """
    if not cohorts:
        return pd.DataFrame()

    conditions = []
    params = []
    for c in cohorts:
        m, p = c.split(" ")
        conditions.append("(p.code_module = ? AND p.code_presentation = ?)")
        params.extend([m, p])
    where_cohorts = " OR ".join(conditions)

    sql = f"""
    WITH presentation_weeks AS (
        SELECT
            p.code_module,
            p.code_presentation,
            p.code_module || ' ' || p.code_presentation AS cohort,
            w.week_no,
            w.day_to
        FROM dim_presentation p
        CROSS JOIN dim_week w
        WHERE ({where_cohorts})
          AND w.week_no >= -4 AND w.week_no < p.n_weeks
    ),
    enrollment_base AS (
        SELECT
            code_module,
            code_presentation,
            COUNT(*) AS total_students
        FROM fact_enrollment
        GROUP BY code_module, code_presentation
    ),
    weekly_dropouts AS (
        SELECT
            pw.cohort,
            pw.week_no,
            pw.day_to,
            COUNT(*) FILTER (WHERE e.date_unregistration IS NOT NULL AND e.date_unregistration <= pw.day_to) AS cum_withdrawn_students
        FROM presentation_weeks pw
        LEFT JOIN fact_enrollment e
          ON e.code_module = pw.code_module
         AND e.code_presentation = pw.code_presentation
        GROUP BY pw.cohort, pw.week_no, pw.day_to
    )
    SELECT
        w.cohort,
        w.week_no,
        w.day_to,
        w.cum_withdrawn_students,
        b.total_students,
        ROUND(100.0 * w.cum_withdrawn_students / b.total_students, 2) AS cum_withdrawal_rate_pct,
        ROUND(100.0 * (b.total_students - w.cum_withdrawn_students) / b.total_students, 2) AS retention_rate_pct
    FROM weekly_dropouts w
    JOIN enrollment_base b 
      ON b.code_module = SPLIT_PART(w.cohort, ' ', 1) 
     AND b.code_presentation = SPLIT_PART(w.cohort, ' ', 2)
    ORDER BY w.cohort, w.week_no;
    """
    return run_query(sql, params)


# ==============================================================================
# BR7: BENCHMARK PHÂN VỊ LỚP VÀ TIẾN ĐỘ CÁ NHÂN
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br7_students_in_presentation(code_module: str, code_presentation: str) -> List[int]:
    """Lấy danh sách mã sinh viên (id_student) thuộc một đợt học cụ thể."""
    sql = """
    SELECT DISTINCT id_student
    FROM fact_enrollment
    WHERE code_module = ? AND code_presentation = ?
    ORDER BY id_student
    """
    df = run_query(sql, [code_module, code_presentation])
    return df["id_student"].tolist()


@st.cache_data(ttl=3600)
def get_br7_cohort_benchmark(code_module: str, code_presentation: str) -> pd.DataFrame:
    """Truy vấn dải phân vị (Q25, Median, Q75) về tương tác VLE và điểm số theo tuần của cả lớp."""
    sql = """
    SELECT
        week_no,
        COUNT(*) AS n_active_students,
        ROUND(QUANTILE_CONT(clicks_cum, 0.25)) AS q25_clicks,
        ROUND(QUANTILE_CONT(clicks_cum, 0.50)) AS median_clicks,
        ROUND(QUANTILE_CONT(clicks_cum, 0.75)) AS q75_clicks,
        ROUND(QUANTILE_CONT(avg_score_cum, 0.25) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS q25_score,
        ROUND(QUANTILE_CONT(avg_score_cum, 0.50) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS median_score,
        ROUND(QUANTILE_CONT(avg_score_cum, 0.75) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS q75_score
    FROM fact_student_week
    WHERE code_module = ? AND code_presentation = ?
      AND is_enrolled
    GROUP BY week_no
    ORDER BY week_no;
    """
    return run_query(sql, [code_module, code_presentation])


@st.cache_data(ttl=3600)
def get_br7_student_progress(code_module: str, code_presentation: str, id_student: int) -> pd.DataFrame:
    """Truy vấn tiến trình học tập cá nhân theo từng tuần của một sinh viên."""
    sql = """
    SELECT
        w.week_no,
        w.clicks_cum,
        w.clicks_week,
        w.avg_score_cum,
        w.n_tma_missed_cum,
        w.is_enrolled,
        e.final_result
    FROM fact_student_week w
    JOIN fact_enrollment e 
      ON e.id_student = w.id_student
     AND e.code_module = w.code_module
     AND e.code_presentation = w.code_presentation
    WHERE w.id_student = ?
      AND w.code_module = ?
      AND w.code_presentation = ?
    ORDER BY w.week_no;
    """
    return run_query(sql, [id_student, code_module, code_presentation])
