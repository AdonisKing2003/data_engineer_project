"""Regression checks for the TV3 lecturer-feedback implementation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import data as app_data  # noqa: E402


def test_query_parameter_mapping_uses_declared_order_for_duckdb():
    assert app_data._duckdb_parameters(
        "br2_tma_deadlines",
        {"code_presentation": "2014J", "code_module": "BBB"},
    ) == ("BBB", "2014J")


def test_query_parameter_mapping_rejects_missing_and_extra_names():
    with pytest.raises(ValueError, match="missing: code_presentation"):
        app_data._ordered_named_parameters(
            "br2_tma_deadlines", {"code_module": "BBB"}
        )

    with pytest.raises(ValueError, match="unsupported: code_site"):
        app_data._ordered_named_parameters(
            "br2_tma_deadlines",
            {
                "code_module": "BBB",
                "code_presentation": "2014J",
                "code_site": "not-a-supported-filter",
            },
        )


@pytest.mark.parametrize(
    ("code_module", "code_presentation", "expected_weeks"),
    [
        ("FFF", "2014J", [3, 7, 13, 19, 28]),
        ("BBB", "2014J", [2, 7, 15, 21, 28]),
    ],
)
def test_br2_tma_deadlines_follow_selected_offering(
    monkeypatch, code_module, code_presentation, expected_weeks
):
    if not (ROOT / "data" / "warehouse" / "dim_assessment").is_dir():
        pytest.skip("Parquet warehouse has not been built")
    monkeypatch.setenv("DATA_BACKEND", "duckdb")

    result = app_data.run_query(
        "br2_tma_deadlines",
        {"code_module": code_module, "code_presentation": code_presentation},
    )

    assert result.columns.tolist() == ["week_no"]
    assert result["week_no"].astype(int).tolist() == expected_weeks


def test_br2_dashboard_query_is_scoped_to_selected_offering(monkeypatch):
    if not (ROOT / "data" / "warehouse" / "fact_vle_daily").is_dir():
        pytest.skip("Parquet warehouse has not been built")
    monkeypatch.setenv("DATA_BACKEND", "duckdb")

    result = app_data.run_query(
        "br2_dashboard",
        {"code_module": "BBB", "code_presentation": "2014J"},
    )
    raw = app_data.run_query("br2_vle_weekly")
    expected = raw.loc[
        (raw["code_module"] == "BBB")
        & (raw["code_presentation"] == "2014J"),
        [
            "week_no",
            "activity_type",
            "activity_type_click_share",
            "activity_type_total_clicks",
            "enrolled_students",
            "avg_clicks_per_enrolled_student",
            "activity_type_avg_clicks_per_enrolled_student",
        ],
    ]
    from scripts.validate_tv3_marts import assert_frames_equal

    assert not result.empty
    assert_frames_equal(
        expected,
        result,
        columns=(
            "week_no",
            "activity_type",
            "activity_type_click_share",
            "activity_type_total_clicks",
            "enrolled_students",
            "avg_clicks_per_enrolled_student",
            "activity_type_avg_clicks_per_enrolled_student",
        ),
        keys=("week_no", "activity_type"),
        unique_keys=True,
    )


def test_br2_dashboard_fff_2014j_week_zero_matches_cohort_and_average_oracle(
    monkeypatch,
):
    if not (ROOT / "data" / "warehouse" / "fact_vle_daily").is_dir():
        pytest.skip("Parquet warehouse has not been built")
    monkeypatch.setenv("DATA_BACKEND", "duckdb")

    result = app_data.run_query(
        "br2_dashboard",
        {"code_module": "FFF", "code_presentation": "2014J"},
    )
    week_zero = result.loc[result["week_no"] == 0].set_index("activity_type")

    assert len(week_zero) == 20
    assert week_zero["enrolled_students"].nunique() == 1
    assert int(week_zero["enrolled_students"].iloc[0]) == 2140
    assert week_zero["avg_clicks_per_enrolled_student"].nunique() == 1
    assert int(week_zero["activity_type_total_clicks"].sum()) == 255054
    assert round(float(week_zero["avg_clicks_per_enrolled_student"].iloc[0]), 1) == 119.2
    assert round(
        float(week_zero.loc["forumng", "activity_type_avg_clicks_per_enrolled_student"]),
        1,
    ) == 38.5
    assert round(
        float(week_zero.loc["oucontent", "activity_type_avg_clicks_per_enrolled_student"]),
        1,
    ) == 25.4
    assert (
        week_zero["activity_type_avg_clicks_per_enrolled_student"]
        == week_zero["activity_type_total_clicks"] / 2140
    ).all()
    zero_click_types = week_zero.loc[week_zero["activity_type_total_clicks"] == 0]
    assert not zero_click_types.empty
    assert (zero_click_types["activity_type_avg_clicks_per_enrolled_student"] == 0).all()


def test_br3_summary_and_selected_student_slice_keep_private_ids_internal(monkeypatch):
    if not (ROOT / "data" / "warehouse" / "fact_submission").is_dir():
        pytest.skip("Parquet warehouse has not been built")
    monkeypatch.setenv("DATA_BACKEND", "duckdb")

    summary = app_data.run_query("br3_summary")
    details = app_data.run_query(
        "br3_dashboard",
        {"code_module": "BBB", "code_presentation": "2014J"},
    )

    assert len(summary) == 19
    assert "id_student" not in summary.columns
    assert "id_student" not in details.columns
    assert set(details["code_module"]) == {"BBB"}
    assert set(details["code_presentation"]) == {"2014J"}
    assert len(details) == int(summary.loc[
        (summary["code_module"] == "BBB")
        & (summary["code_presentation"] == "2014J"),
        "n",
    ].iloc[0])


def _choose(app_test, key: str, value: str) -> None:
    control = next(control for control in app_test.selectbox if control.key == key)
    control.set_value(value)


def _open_course_page(app_test) -> None:
    # The app opens on the overview; the course page is a callable page, which
    # AppTest.switch_page cannot target, so select it by its registered hash.
    app_test._page_hash = next(
        page_hash
        for page_hash, info in app_test._registered_pages.items()
        if info["url_pathname"] == "render_course_page"
    )
    app_test.run(timeout=20)


def _open_br3_tab(app_test) -> None:
    # The course tabs rerun on change and only the open tab renders.
    app_test.session_state["course_tab"] = "Click trước hạn TMA và điểm"
    app_test.run(timeout=20)


def _br2_heatmap_tma_weeks(app_test) -> list[int]:
    heatmap = next(
        chart
        for chart in app_test.get("plotly_chart")
        if chart.proto.id.endswith("-br2_heatmap")
    )
    figure = json.loads(heatmap.proto.spec)
    return sorted(
        int(shape["x0"])
        for shape in figure["layout"].get("shapes", [])
        if shape.get("type") == "line"
        and shape.get("line", {}).get("color") == "#d97706"
    )


def test_course_page_switches_to_br3_and_ggg_explains_missing_tma(monkeypatch):
    pytest.importorskip("streamlit.testing.v1")
    if not (ROOT / "data" / "warehouse" / "fact_submission").is_dir():
        pytest.skip("Parquet warehouse has not been built")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("DATA_BACKEND", "duckdb")
    app_test = AppTest.from_file(str(ROOT / "app" / "Home.py")).run(timeout=20)
    _open_course_page(app_test)
    _open_br3_tab(app_test)
    assert not app_test.exception
    assert len(app_test.get("plotly_chart")) >= 1  # BR3 forest plot

    _choose(app_test, "course_offering", "GGG 2014J")
    # AppTest does not carry the selected tab into the next run (a browser does,
    # checked by hand), so reopen the BR3 tab before rerunning.
    _open_br3_tab(app_test)
    assert not app_test.exception
    assert any("GGG không có TMA có trọng số" in element.value for element in app_test.info)


def test_br2_course_page_uses_selected_tma_weeks_and_updates_heatmap_markers(
    monkeypatch,
):
    pytest.importorskip("streamlit.testing.v1")
    if not (ROOT / "data" / "warehouse" / "fact_vle_daily").is_dir():
        pytest.skip("Parquet warehouse has not been built")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("DATA_BACKEND", "duckdb")
    app_test = AppTest.from_file(str(ROOT / "app" / "Home.py")).run(timeout=20)
    _open_course_page(app_test)
    _choose(app_test, "course_offering", "FFF 2014J")
    app_test.run(timeout=20)
    assert _br2_heatmap_tma_weeks(app_test) == [3, 7, 13, 19, 28]

    _choose(app_test, "course_offering", "BBB 2014J")
    app_test.run(timeout=20)
    assert not app_test.exception
    assert _br2_heatmap_tma_weeks(app_test) == [2, 7, 15, 21, 28]
    assert any(
        "2, 7, 15, 21, 28" in element.value
        for element in app_test.caption
    )


def test_br2_week_selector_defaults_to_zero_and_updates_week_metrics(monkeypatch):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    import pandas as pd

    dashboard_rows = []
    for week_no, enrolled, overall_avg, activity_values in (
        (0, 10, 119.2, {"forumng": 38.5, "oucontent": 25.4}),
        (2, 5, 20.0, {"forumng": 15.0, "oucontent": 5.0}),
    ):
        for activity_type, activity_average in activity_values.items():
            dashboard_rows.append(
                {
                    "week_no": week_no,
                    "activity_type": activity_type,
                    "activity_type_click_share": activity_average / overall_avg,
                    "activity_type_total_clicks": activity_average * enrolled,
                    "enrolled_students": enrolled,
                    "avg_clicks_per_enrolled_student": overall_avg,
                    "activity_type_avg_clicks_per_enrolled_student": activity_average,
                }
            )

    def fake_run_query(query_id, parameters=None):
        if query_id == "overview_offerings":
            return pd.DataFrame()  # the overview page opens first; this test checks the course page
        if query_id == "br2_offerings":
            return pd.DataFrame(
                [{"code_module": "ZZZ", "code_presentation": "9999X"}]
            )
        if query_id == "br2_dashboard":
            return pd.DataFrame(dashboard_rows)
        if query_id == "br2_tma_deadlines":
            return pd.DataFrame({"week_no": [0, 2]})
        raise AssertionError(f"Unexpected query: {query_id}")

    monkeypatch.setenv("DATA_BACKEND", "duckdb")
    monkeypatch.setattr(app_data, "run_query", fake_run_query)
    st.cache_data.clear()
    app_test = AppTest.from_file(str(ROOT / "app" / "Home.py")).run(timeout=20)
    _open_course_page(app_test)

    assert not app_test.exception
    week_selector = next(
        (control for control in app_test.selectbox if control.key == "br2_week"), None
    )
    assert week_selector is not None, {
        "selectboxes": [(control.label, control.key) for control in app_test.selectbox],
        "errors": [element.value for element in app_test.error],
        "warnings": [element.value for element in app_test.warning],
    }
    assert week_selector.value == 0
    default_metrics = {metric.label: metric.value for metric in app_test.metric}
    assert default_metrics["Sinh viên còn học cuối tuần"] == "10"
    assert default_metrics["Trung bình toàn tuần"] == "119.2 click/sinh viên"
    assert default_metrics["Forumng"] == "38.5 click/sinh viên"
    assert default_metrics["Oucontent"] == "25.4 click/sinh viên"

    week_selector.set_value(2)
    app_test.run(timeout=20)
    selected_metrics = {metric.label: metric.value for metric in app_test.metric}
    assert selected_metrics["Sinh viên còn học cuối tuần"] == "5"
    assert selected_metrics["Trung bình toàn tuần"] == "20.0 click/sinh viên"
    assert selected_metrics["Forumng"] == "15.0 click/sinh viên"
    assert selected_metrics["Oucontent"] == "5.0 click/sinh viên"


def test_parameterized_bigquery_calls_reject_missing_parameters_before_query(
    monkeypatch, tmp_path
):
    query = tmp_path / "query.sql"
    query.write_text("SELECT @code_module, @code_presentation", encoding="utf-8")
    monkeypatch.setenv("DATA_BACKEND", "bigquery")
    monkeypatch.setattr(app_data, "_query_path", lambda query_id, backend: query)
    called = False

    def fake_bigquery(query_text, parameters):
        nonlocal called
        called = True
        raise AssertionError("query should be rejected before backend execution")

    monkeypatch.setattr(app_data, "_run_bigquery", fake_bigquery)
    with pytest.raises(ValueError, match="missing: code_module, code_presentation"):
        app_data.run_query("br2_dashboard")
    assert not called


def test_parity_comparison_applies_numeric_tolerance_and_keeps_duplicates():
    pd = pytest.importorskip("pandas")
    from scripts.validate_tv3_marts import assert_frames_equal, frame_hash

    expected = pd.DataFrame({"key": [1, 2, 2], "value": [10.0, 20.0, 20.0]})
    actual = pd.DataFrame({"key": [2, 1, 2], "value": [20.0, 10.0 + 1e-9, 20.0]})
    assert_frames_equal(expected, actual, columns=("key", "value"), keys=("key",))
    assert frame_hash(expected, ("key", "value"), ("key",)) == frame_hash(
        actual, ("key", "value"), ("key",)
    )

    with pytest.raises(AssertionError, match="row count differs"):
        assert_frames_equal(
            expected,
            actual.iloc[:-1],
            columns=("key", "value"),
            keys=("key",),
        )


