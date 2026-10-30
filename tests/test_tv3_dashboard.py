"""Focused TV3 checks for backend selection, BR6 suppression, BR8, and the app shell."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import data as app_data  # noqa: E402


def test_query_adapter_defaults_to_bigquery_and_keeps_dataframe_contract(monkeypatch, tmp_path):
    sql_path = tmp_path / "query.sql"
    sql_path.write_text("SELECT 1", encoding="utf-8")
    observed = {}

    def fake_bigquery(query, parameters):
        observed["query"] = query
        observed["parameters"] = parameters
        return pd.DataFrame({"value": [1]})

    monkeypatch.delenv("DATA_BACKEND", raising=False)
    monkeypatch.setattr(app_data, "_query_path", lambda query_id, backend: sql_path)
    monkeypatch.setattr(app_data, "_run_bigquery", fake_bigquery)
    result = app_data.run_query("br2_vle_weekly")

    assert isinstance(result, pd.DataFrame)
    assert result.to_dict("list") == {"value": [1]}
    assert observed == {"query": "SELECT 1", "parameters": None}


def test_bigquery_failure_does_not_fall_back_to_duckdb(monkeypatch, tmp_path):
    sql_path = tmp_path / "query.sql"
    sql_path.write_text("SELECT 1", encoding="utf-8")
    fallback_called = False

    def fail_bigquery(query, parameters):
        raise RuntimeError("BigQuery unavailable")

    def forbidden_fallback(query, parameters):
        nonlocal fallback_called
        fallback_called = True
        raise AssertionError("unexpected DuckDB fallback")

    monkeypatch.setenv("DATA_BACKEND", "bigquery")
    monkeypatch.setattr(app_data, "_query_path", lambda query_id, backend: sql_path)
    monkeypatch.setattr(app_data, "_run_bigquery", fail_bigquery)
    monkeypatch.setattr(app_data, "_run_duckdb", forbidden_fallback)

    with pytest.raises(RuntimeError, match="BigQuery unavailable"):
        app_data.run_query("br2_vle_weekly")
    assert not fallback_called


def test_br6_suppresses_a_band_at_29_distinct_students_but_shows_30():
    duckdb = pytest.importorskip("duckdb")
    sql = (ROOT / "sql" / "br6_imd_gap.sql").read_text(encoding="utf-8")
    sql = sql.replace(
        "read_parquet('data/warehouse/fact_enrollment/*.parquet')", "fact_enrollment"
    ).replace("read_parquet('data/warehouse/dim_student/*.parquet')", "dim_student")

    enrollments = []
    students = []
    for student_id in range(1, 30):
        students.append({"id_student": student_id, "imd_band": "0-10%"})
        enrollments.append(
            {
                "id_student": student_id,
                "code_module": "BBB",
                "code_presentation": "2014J",
                "final_result": "Pass",
                "withdrawn_before_start": False,
            }
        )
    # A 30th enrollment for one of the same 29 low-band students demonstrates
    # that the threshold is distinct students, not enrollment rows.
    enrollments.append(
        {
            "id_student": 1,
            "code_module": "DDD",
            "code_presentation": "2014J",
            "final_result": "Fail",
            "withdrawn_before_start": False,
        }
    )
    for student_id in range(100, 130):
        students.append({"id_student": student_id, "imd_band": "90-100%"})
        enrollments.append(
            {
                "id_student": student_id,
                "code_module": "BBB",
                "code_presentation": "2014J",
                "final_result": "Pass",
                "withdrawn_before_start": False,
            }
        )

    with duckdb.connect() as connection:
        connection.register("fact_enrollment", pd.DataFrame(enrollments))
        connection.register("dim_student", pd.DataFrame(students))
        result = connection.execute(sql).fetchdf().set_index("code_presentation").loc["2014J"]

    assert result["n_students_imd_0_10"] is None or pd.isna(result["n_students_imd_0_10"])
    assert pd.isna(result["n_enrollments_imd_0_10"])
    assert result["n_students_imd_0_10_label"] == "n < 30"
    assert pd.isna(result["rate_imd_0_10_pct"])
    assert result["n_students_imd_90_100"] == 30
    assert result["rate_imd_90_100_pct"] == 100.0
    assert pd.isna(result["gap_pp"])


def test_br8_q20_matches_expected_duckdb_result():
    warehouse = ROOT / "data" / "warehouse"
    if not (warehouse / "fact_enrollment").is_dir():
        pytest.skip("Parquet warehouse has not been built")
    from scripts.run_sql import execute_sql

    sql = (ROOT / "sql" / "br8_forum_week5.sql").read_text(encoding="utf-8")
    result, _, _ = execute_sql(sql, engine="duckdb")
    row = result.iloc[0]
    assert int(row["n_students"]) == 1072
    assert (row["q25_forum_clicks"], row["median_forum_clicks"], row["q75_forum_clicks"]) == (
        0,
        5,
        22,
    )


def test_dashboard_course_page_renders_with_local_duckdb(monkeypatch):
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    monkeypatch.setenv("DATA_BACKEND", "duckdb")
    app_test = streamlit_testing.AppTest.from_file(str(ROOT / "app" / "Home.py")).run(
        timeout=20
    )
    # The app opens on the overview; the course page is a callable page, which
    # AppTest.switch_page cannot target, so select it by its registered hash.
    app_test._page_hash = next(
        page_hash
        for page_hash, info in app_test._registered_pages.items()
        if info["url_pathname"] == "render_course_page"
    )
    app_test.run(timeout=20)
    assert not app_test.exception
    # Only the open tab (BR2) renders: heatmap and top-five trend.
    assert len(app_test.get("plotly_chart")) == 2


def test_br2_dashboard_backend_queries_expose_the_extended_metric_contract():
    expected_columns = {
        "week_no",
        "activity_type",
        "activity_type_click_share",
        "activity_type_total_clicks",
        "enrolled_students",
        "avg_clicks_per_enrolled_student",
        "activity_type_avg_clicks_per_enrolled_student",
    }
    duckdb_sql = (ROOT / "sql" / "br2_dashboard.sql").read_text(encoding="utf-8")
    bigquery_sql = (ROOT / "sql" / "bigquery" / "br2_dashboard.sql").read_text(
        encoding="utf-8"
    )

    for sql in (duckdb_sql, bigquery_sql):
        selected_columns = sql.rsplit("SELECT", maxsplit=1)[1].split("FROM", maxsplit=1)[0]
        normalized_columns = selected_columns.lower()
        for column in expected_columns:
            assert column in normalized_columns
