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
def get_br1_school_tma() -> pd.DataFrame:
    """Bài TMA toàn trường theo môn: số bài, số bài trễ, điểm trung bình (câu 7, 8)."""
    return run_query("br1_school_summary")


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
def get_br5_school_summary() -> dict:
    """Số lượt rút toàn trường, số lượt rút từ ngày 0 trở về trước và ngày rút trung vị (câu 15, 16)."""
    return run_query("br5_school_summary").iloc[0].to_dict()


@st.cache_data(ttl=3600)
def _br5_retention_curve_all() -> pd.DataFrame:
    """Đường cong rút lui tích lũy theo tuần của cả 22 đợt (bảng nhỏ, đọc một lần)."""
    return run_query("br5_retention_curve")


def get_br5_retention_curve(cohorts: List[str]) -> pd.DataFrame:
    """Đường cong rút lui tích lũy theo tuần cho các đợt được chọn (dạng "AAA 2013J")."""
    if not cohorts:
        return pd.DataFrame()
    df = _br5_retention_curve_all()
    return df[df["cohort"].isin(cohorts)].reset_index(drop=True)


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
