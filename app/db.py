"""Module facade đóng gói toàn bộ các hàm nghiệp vụ truy vấn dữ liệu cho các trang của TV2.
Đồng bộ 100% với kiến trúc app.data và kho SQL độc lập (DuckDB / BigQuery).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import sys
import pandas as pd
import streamlit as st

# Đảm bảo cả thư mục gốc data_engineer_project và app đều có trong sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_APP_DIR = Path(__file__).resolve().parent
for _p in (str(_PROJECT_ROOT), str(_APP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from app.data import QUERY_FILES, _bigquery_client, _run_duckdb, run_query as _data_run_query
except ModuleNotFoundError:
    from data import QUERY_FILES, _bigquery_client, _run_duckdb, run_query as _data_run_query


def run_query(sql_or_name: str, parameters=None) -> pd.DataFrame:
    """Chạy truy vấn theo mã định danh trong QUERY_FILES hoặc chuỗi SQL trực tiếp."""
    if sql_or_name in QUERY_FILES:
        return _data_run_query(sql_or_name, parameters)
    backend = os.getenv("DATA_BACKEND", "bigquery").strip().lower()
    if backend == "bigquery":
        from google.cloud import bigquery
        project = os.getenv("GCP_PROJECT_ID", "dataengineergroup32").strip()
        dataset = os.getenv("BQ_DATASET", "oulad").strip()
        client = _bigquery_client(project, os.getenv("BQ_LOCATION", "US"))
        job_config = bigquery.QueryJobConfig(default_dataset=f"{project}.{dataset}")
        return client.query_and_wait(sql_or_name, job_config=job_config).to_dataframe(create_bqstorage_client=False)
    return _run_duckdb(sql_or_name, None)


@st.cache_data(ttl=3600)
def get_presentations() -> pd.DataFrame:
    """Lấy danh sách các đợt học có sẵn trong kho."""
    return run_query("presentations")


@st.cache_data(ttl=3600)
def get_overall_stats() -> dict:
    """Lấy số liệu thống kê tổng quát toàn trường."""
    df = run_query("overall_stats")
    return df.iloc[0].to_dict()


# ==============================================================================
# BR1: NỘP BÀI, TRỄ HẠN & PHÂN PHỐI ĐIỂM
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br1_assessment_stats(code_module: str, code_presentation: str) -> pd.DataFrame:
    """Lấy thống kê tỷ lệ nộp bài, nộp trễ và các phân vị điểm số theo từng bài kiểm tra."""
    return run_query(
        "br1_assessment_stats",
        {"code_module": code_module, "code_presentation": code_presentation},
    )


@st.cache_data(ttl=3600)
def get_br1_assessment_scores(code_module: str, code_presentation: str) -> pd.DataFrame:
    """Lấy danh sách điểm số chi tiết của từng bài kiểm tra để vẽ biểu đồ Box Plot."""
    return run_query(
        "br1_assessment_scores",
        {"code_module": code_module, "code_presentation": code_presentation},
    )


# ==============================================================================
# BR4: CẢNH BÁO SỚM THEO TUẦN (WEEKLY SNAPSHOT AS-OF)
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br4_at_risk_students(
    code_module: Optional[str] = None,
    code_presentation: Optional[str] = None,
    week_no: int = 4,
) -> pd.DataFrame:
    """Truy vấn cảnh báo sớm sinh viên có nguy cơ học tập tại tuần week_no."""
    if code_module and code_presentation:
        return run_query(
            "br4_at_risk_list",
            {
                "week_no": week_no,
                "code_module": code_module,
                "code_presentation": code_presentation,
            },
        )
    return run_query("br4_at_risk_all", {"week_no": week_no})


# ==============================================================================
# BR5: ĐƯỜNG CONG RÚT LUI TÍCH LŨY & TỶ LỆ DUY TRÌ
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br5_withdrawal_summary() -> pd.DataFrame:
    """Lấy thống kê tỷ lệ rút lui của toàn bộ 22 đợt học tại các mốc ngày then chốt (ngày 0, ngày 27)."""
    return run_query("br5_withdrawal_summary")


@st.cache_data(ttl=3600)
def get_br5_retention_curve(cohorts: List[str]) -> pd.DataFrame:
    """Truy vấn đường cong rút lui tích lũy theo tuần cho danh sách các đợt học được chọn."""
    if not cohorts:
        return pd.DataFrame()

    backend = os.getenv("DATA_BACKEND", "bigquery").strip().lower()

    if backend == "bigquery":
        conditions = [
            f"(p.code_module = '{c.split(' ')[0]}' AND p.code_presentation = '{c.split(' ')[1]}')"
            for c in cohorts
        ]
        where_clause = " OR ".join(conditions)
        sql = f"""
        WITH presentation_weeks AS (
            SELECT p.code_module, p.code_presentation,
                   p.code_module || ' ' || p.code_presentation AS cohort,
                   w.week_no, w.day_to
            FROM dim_presentation p
            CROSS JOIN dim_week w
            WHERE ({where_clause}) AND w.week_no >= -4 AND w.week_no < p.n_weeks
        ),
        enrollment_base AS (
            SELECT code_module, code_presentation, COUNT(*) AS total_students
            FROM fact_enrollment GROUP BY code_module, code_presentation
        ),
        weekly_dropouts AS (
            SELECT pw.cohort, pw.week_no, pw.day_to,
                   COUNTIF(e.date_unregistration IS NOT NULL AND e.date_unregistration <= pw.day_to) AS cum_withdrawn_students
            FROM presentation_weeks pw
            LEFT JOIN fact_enrollment e
              ON e.code_module = pw.code_module AND e.code_presentation = pw.code_presentation
            GROUP BY pw.cohort, pw.week_no, pw.day_to
        )
        SELECT w.cohort, w.week_no, w.day_to, w.cum_withdrawn_students, b.total_students,
               ROUND(100.0 * w.cum_withdrawn_students / b.total_students, 2) AS cum_withdrawal_rate_pct,
               ROUND(100.0 * (b.total_students - w.cum_withdrawn_students) / b.total_students, 2) AS retention_rate_pct
        FROM weekly_dropouts w
        JOIN enrollment_base b 
          ON b.code_module = SPLIT(w.cohort, ' ')[OFFSET(0)] 
         AND b.code_presentation = SPLIT(w.cohort, ' ')[OFFSET(1)]
        ORDER BY w.cohort, w.week_no;
        """
        from google.cloud import bigquery
        from app.data import _bigquery_client
        project = os.getenv("GCP_PROJECT_ID", "dataengineergroup32").strip()
        dataset = os.getenv("BQ_DATASET", "oulad").strip()
        client = _bigquery_client(project, os.getenv("BQ_LOCATION", "US"))
        job_config = bigquery.QueryJobConfig(default_dataset=f"{project}.{dataset}")
        return client.query_and_wait(sql, job_config=job_config).to_dataframe(create_bqstorage_client=False)

    # DuckDB local
    import duckdb
    wh = Path(__file__).resolve().parents[1] / "data" / "warehouse"
    conditions = [
        f"(p.code_module = '{c.split(' ')[0]}' AND p.code_presentation = '{c.split(' ')[1]}')"
        for c in cohorts
    ]
    where_clause = " OR ".join(conditions)
    sql = f"""
    WITH presentation_weeks AS (
        SELECT p.code_module, p.code_presentation,
               p.code_module || ' ' || p.code_presentation AS cohort,
               w.week_no, w.day_to
        FROM dim_presentation p
        CROSS JOIN dim_week w
        WHERE ({where_clause}) AND w.week_no >= -4 AND w.week_no < p.n_weeks
    ),
    enrollment_base AS (
        SELECT code_module, code_presentation, COUNT(*) AS total_students
        FROM fact_enrollment GROUP BY code_module, code_presentation
    ),
    weekly_dropouts AS (
        SELECT pw.cohort, pw.week_no, pw.day_to,
               COUNT(*) FILTER (WHERE e.date_unregistration IS NOT NULL AND e.date_unregistration <= pw.day_to) AS cum_withdrawn_students
        FROM presentation_weeks pw
        LEFT JOIN fact_enrollment e
          ON e.code_module = pw.code_module AND e.code_presentation = pw.code_presentation
        GROUP BY pw.cohort, pw.week_no, pw.day_to
    )
    SELECT w.cohort, w.week_no, w.day_to, w.cum_withdrawn_students, b.total_students,
           ROUND(100.0 * w.cum_withdrawn_students / b.total_students, 2) AS cum_withdrawal_rate_pct,
           ROUND(100.0 * (b.total_students - w.cum_withdrawn_students) / b.total_students, 2) AS retention_rate_pct
    FROM weekly_dropouts w
    JOIN enrollment_base b 
      ON b.code_module = SPLIT_PART(w.cohort, ' ', 1) 
     AND b.code_presentation = SPLIT_PART(w.cohort, ' ', 2)
    ORDER BY w.cohort, w.week_no;
    """
    with duckdb.connect(":memory:") as con:
        con.execute(f"CREATE VIEW dim_presentation AS SELECT * FROM read_parquet('{wh.as_posix()}/dim_presentation/*.parquet')")
        con.execute(f"CREATE VIEW dim_week AS SELECT * FROM read_parquet('{wh.as_posix()}/dim_week/*.parquet')")
        con.execute(f"CREATE VIEW fact_enrollment AS SELECT * FROM read_parquet('{wh.as_posix()}/fact_enrollment/*.parquet')")
        return con.execute(sql).df()


# ==============================================================================
# BR7: BENCHMARK PHÂN VỊ LỚP VÀ TIẾN ĐỘ CÁ NHÂN
# ==============================================================================

@st.cache_data(ttl=3600)
def get_br7_students_in_presentation(code_module: str, code_presentation: str) -> List[int]:
    """Lấy danh sách mã sinh viên (id_student) thuộc một đợt học cụ thể."""
    df = run_query(
        "br7_students_in_presentation",
        {"code_module": code_module, "code_presentation": code_presentation},
    )
    return df["id_student"].tolist()


@st.cache_data(ttl=3600)
def get_br7_cohort_benchmark(code_module: str, code_presentation: str) -> pd.DataFrame:
    """Truy vấn dải phân vị (Q25, Median, Q75) về tương tác VLE và điểm số theo tuần của cả lớp."""
    return run_query(
        "br7_cohort_benchmark",
        {"code_module": code_module, "code_presentation": code_presentation},
    )


@st.cache_data(ttl=3600)
def get_br7_student_progress(code_module: str, code_presentation: str, id_student: int) -> pd.DataFrame:
    """Truy vấn tiến trình học tập cá nhân theo từng tuần của một sinh viên."""
    return run_query(
        "br7_student_progress",
        {
            "id_student": id_student,
            "code_module": code_module,
            "code_presentation": code_presentation,
        },
    )
