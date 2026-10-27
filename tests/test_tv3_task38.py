"""DuckDB and opt-in BigQuery AppTest demos for the TV3 pages.

The tests use local DuckDB when the required Parquet tables exist. Set
RUN_TV3_BIGQUERY_DEMO=1 to run against the configured BigQuery dataset.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import sys
from math import atanh, sqrt, tanh
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import data as app_data  # noqa: E402


HOME = ROOT / "app" / "Home.py"


def _configure_backend(
    monkeypatch: pytest.MonkeyPatch,
    required_tables: tuple[str, ...],
) -> str:
    pytest.importorskip("streamlit.testing.v1")
    pytest.importorskip("plotly.graph_objects")
    if os.getenv("RUN_TV3_BIGQUERY_DEMO", "").strip() == "1":
        backend = "bigquery"
    else:
        missing = [
            table
            for table in required_tables
            if not (ROOT / "data" / "warehouse" / table).is_dir()
        ]
        if missing:
            pytest.skip(
                "Build the local Parquet warehouse or set RUN_TV3_BIGQUERY_DEMO=1; "
                f"missing: {', '.join(missing)}"
            )
        backend = "duckdb"
    monkeypatch.setenv("DATA_BACKEND", backend)
    return backend


def _assert_rendered(app_test) -> None:
    assert not app_test.exception, [str(exception) for exception in app_test.exception]
    assert not app_test.error, [error.value for error in app_test.error]


def _run_home():
    streamlit = pytest.importorskip("streamlit")
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    streamlit.cache_data.clear()
    app_test = streamlit_testing.AppTest.from_file(str(HOME)).run(timeout=120)
    _assert_rendered(app_test)
    return app_test


def _open_page(app_test, page_name: str):
    pages = {
        info["url_pathname"]: page_hash
        for page_hash, info in app_test._registered_pages.items()
    }
    assert page_name in pages, f"Registered Streamlit pages: {sorted(pages)}"
    app_test._page_hash = pages[page_name]
    app_test.run(timeout=120)
    _assert_rendered(app_test)
    return app_test


def _select(app_test, key: str, value: str) -> None:
    control = next(control for control in app_test.selectbox if control.key == key)
    control.set_value(value)
    app_test.run(timeout=120)
    _assert_rendered(app_test)


def _figure(app_test, key: str):
    plotly = pytest.importorskip("plotly.graph_objects")
    chart = next(
        chart
        for chart in app_test.get("plotly_chart")
        if chart.proto.id.endswith(f"-{key}")
    )
    spec = _decode_plotly_value(json.loads(chart.proto.spec))
    return plotly.Figure(spec)


def _decode_plotly_value(value):
    """Decode Plotly 6 typed-array objects in an AppTest chart spec."""
    if isinstance(value, dict):
        if "bdata" in value and "dtype" in value:
            array = np.frombuffer(
                base64.b64decode(value["bdata"]),
                dtype=np.dtype(value["dtype"]),
            )
            shape = value.get("shape")
            if isinstance(shape, str):
                shape = ast.literal_eval(shape)
            if shape is not None:
                if isinstance(shape, (int, np.integer)):
                    shape = (int(shape),)
                array = array.reshape(tuple(shape))
            return array.tolist()
        return {key: _decode_plotly_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_plotly_value(item) for item in value]
    return value


def _metrics(app_test) -> dict[str, str]:
    return {metric.label: metric.value for metric in app_test.metric}


def test_br2_bigquery_app_demo_matches_week_zero_and_renders_heatmap_top_five(
    monkeypatch: pytest.MonkeyPatch,
):
    _configure_backend(
        monkeypatch,
        ("fact_vle_daily", "fact_enrollment", "dim_presentation", "dim_vle_site", "dim_assessment"),
    )
    parameters = {"code_module": "FFF", "code_presentation": "2014J"}
    dashboard = app_data.run_query("br2_dashboard", parameters)
    deadlines = app_data.run_query("br2_tma_deadlines", parameters)

    week_zero = dashboard.loc[dashboard["week_no"] == 0].set_index("activity_type")
    assert len(week_zero) == 20
    assert week_zero["enrolled_students"].nunique() == 1
    assert int(week_zero["enrolled_students"].iloc[0]) == 2140
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

    activity_totals = dashboard.groupby("activity_type")[
        "activity_type_total_clicks"
    ].sum()
    expected_order = activity_totals.sort_values(ascending=False).index.tolist()
    expected_top_five = expected_order[:5]
    expected_due_weeks = deadlines["week_no"].astype(int).tolist()
    assert expected_due_weeks == [3, 7, 13, 19, 28]

    app_test = _run_home()
    _select(app_test, "br2_module", "FFF")
    _select(app_test, "br2_presentation", "2014J")
    assert _metrics(app_test)["Sinh viên còn học cuối tuần"] == "2,140"
    assert _metrics(app_test)["Trung bình toàn tuần"] == "119.2 click/sinh viên"
    assert _metrics(app_test)["Forumng"] == "38.5 click/sinh viên"
    assert _metrics(app_test)["Oucontent"] == "25.4 click/sinh viên"

    heatmap = _figure(app_test, "br2_heatmap")
    heatmap_data = dashboard.pivot(
        index="activity_type",
        columns="week_no",
        values="activity_type_click_share",
    ).reindex(expected_order)
    assert list(heatmap.data[0].y) == expected_order
    np.testing.assert_allclose(
        np.asarray(heatmap.data[0].z, dtype=float),
        heatmap_data.to_numpy(dtype=float) * 100,
        rtol=0,
        atol=1e-9,
        equal_nan=True,
    )
    due_markers = sorted(
        int(round(shape.x0))
        for shape in heatmap.layout.shapes
        if shape.type == "line" and shape.line.color == "#d97706"
    )
    assert due_markers == expected_due_weeks

    top_five_chart = _figure(app_test, "br2_top_five")
    assert [trace.name for trace in top_five_chart.data] == expected_top_five
    for trace in top_five_chart.data:
        expected_activity = dashboard.loc[
            dashboard["activity_type"] == trace.name
        ].sort_values("week_no")
        np.testing.assert_array_equal(
            np.asarray(trace.y, dtype=float),
            expected_activity["activity_type_total_clicks"].to_numpy(dtype=float),
        )


def test_br3_bigquery_app_demo_shows_log_scatter_forest_warning_and_ggg(
    monkeypatch: pytest.MonkeyPatch,
):
    _configure_backend(
        monkeypatch,
        ("fact_vle_daily", "fact_submission", "dim_assessment"),
    )
    summaries = app_data.run_query("br3_summary")
    assert len(summaries) == 19
    assert int(summaries["n"].sum()) == 21693
    oracle = summaries.loc[
        (summaries["code_module"] == "AAA")
        & (summaries["code_presentation"] == "2013J")
    ].iloc[0]
    assert int(oracle["n"]) == 358
    assert round(float(oracle["rho"]), 2) == 0.37

    parameters = {"code_module": "AAA", "code_presentation": "2013J"}
    details = app_data.run_query("br3_dashboard", parameters)
    assert len(details) == 358
    zero_click_count = int((details["clicks_before_deadline"] == 0).sum())
    # The documented 186 zero-click pairs are aggregated across all presentations.
    assert zero_click_count > 0

    app_test = _run_home()
    _select(app_test, "course_analysis", "BR3 — Click trước hạn TMA và điểm")
    _select(app_test, "br3_module", "AAA")
    _select(app_test, "br3_presentation", "2013J")
    assert any(
        "tương quan, không phải nhân quả" in caption.value.lower()
        for caption in app_test.caption
    )

    scatter_figure = _figure(app_test, "br3_scatter")
    assert scatter_figure.layout.xaxis.type == "log"
    np.testing.assert_array_equal(
        np.asarray(scatter_figure.data[0].x, dtype=float),
        details["clicks_before_deadline"].to_numpy(dtype=float) + 1,
    )
    assert int(np.count_nonzero(np.asarray(scatter_figure.data[0].x) == 1)) == zero_click_count
    np.testing.assert_array_equal(
        np.asarray(scatter_figure.data[0].y, dtype=float),
        details["score"].to_numpy(dtype=float),
    )

    forest = _figure(app_test, "br3_forest")
    marker = next(trace for trace in forest.data if trace.name == "Spearman ρ")
    assert len(marker.x) == 19
    label = "AAA 2013J"
    index = list(marker.y).index(label)
    assert int(marker.customdata[index][0]) == int(oracle["n"])
    assert float(marker.x[index]) == pytest.approx(float(oracle["rho"]), abs=1e-12)
    rho = float(oracle["rho"])
    margin = 1.96 / sqrt(int(oracle["n"]) - 3)
    expected_ci = (tanh(atanh(rho) - margin), tanh(atanh(rho) + margin))
    ci_line = next(
        trace
        for trace in forest.data
        if trace.mode == "lines" and list(trace.y) == [label, label]
    )
    np.testing.assert_allclose(np.asarray(ci_line.x, dtype=float), expected_ci, atol=1e-12)

    _select(app_test, "br3_module", "GGG")
    assert any("GGG không có TMA có trọng số" in info.value for info in app_test.info)
    assert not any(
        chart.proto.id.endswith("-br3_scatter")
        for chart in app_test.get("plotly_chart")
    )


def test_br6_bigquery_app_demo_matches_q18_and_both_dumbbell_measures(
    monkeypatch: pytest.MonkeyPatch,
):
    _configure_backend(
        monkeypatch,
        ("fact_enrollment", "dim_student"),
    )
    results = app_data.run_query("br6_imd_gap")
    assert results["code_presentation"].tolist() == [
        "2013B",
        "2013J",
        "2014B",
        "2014J",
    ]
    assert results["code_module"].eq("BBB,DDD,FFF").all()
    q18 = results.loc[results["code_presentation"] == "2014J"].iloc[0]
    assert float(q18["rate_imd_0_10_pct"]) == 41.1
    assert float(q18["rate_imd_90_100_pct"]) == 63.3
    assert float(q18["gap_pp"]) == 22.2
    assert float(q18["rate_distinction_imd_0_10_pct"]) == 4.6
    assert float(q18["rate_distinction_imd_90_100_pct"]) == 16.3
    assert float(q18["distinction_gap_pp"]) == 11.7

    app_test = _open_page(_run_home(), "render_faculty_page")
    pass_chart = _figure(app_test, "br6_dumbbell")
    assert [trace.name for trace in pass_chart.data] == [
        "IMD 0–10%",
        "IMD 90–100%",
    ]
    assert list(pass_chart.data[0].y) == results["code_presentation"].tolist()
    np.testing.assert_allclose(
        np.asarray(pass_chart.data[0].x, dtype=float),
        results["rate_imd_0_10_pct"].to_numpy(dtype=float),
    )
    np.testing.assert_allclose(
        np.asarray(pass_chart.data[1].x, dtype=float),
        results["rate_imd_90_100_pct"].to_numpy(dtype=float),
    )

    measure = next(radio for radio in app_test.radio if radio.key == "br6_measure")
    measure.set_value("Distinction")
    app_test.run(timeout=120)
    _assert_rendered(app_test)
    distinction_chart = _figure(app_test, "br6_dumbbell")
    np.testing.assert_allclose(
        np.asarray(distinction_chart.data[0].x, dtype=float),
        results["rate_distinction_imd_0_10_pct"].to_numpy(dtype=float),
    )
    np.testing.assert_allclose(
        np.asarray(distinction_chart.data[1].x, dtype=float),
        results["rate_distinction_imd_90_100_pct"].to_numpy(dtype=float),
    )


def test_br8_bigquery_app_demo_shows_zero_inclusive_forum_quantiles(
    monkeypatch: pytest.MonkeyPatch,
):
    _configure_backend(
        monkeypatch,
        ("fact_enrollment", "fact_vle_daily", "dim_vle_site"),
    )
    result = app_data.run_query("br8_forum_week5")
    row = result.iloc[0]
    assert int(row["n_students"]) == 1072
    assert (
        int(row["q25_forum_clicks"]),
        int(row["median_forum_clicks"]),
        int(row["q75_forum_clicks"]),
    ) == (0, 5, 22)

    app_test = _open_page(_run_home(), "render_student_page")
    metrics = _metrics(app_test)
    assert metrics["Sinh viên"] == "1,072"
    assert metrics["Trung vị"] == "5 click"
    assert metrics["Khoảng tứ phân vị"] == "0–22 click"

    quantiles = _figure(app_test, "br8_quantiles")
    assert list(quantiles.data[0].x) == [0, 22]
    assert quantiles.data[0].hovertemplate == "Click: %{x}<extra></extra>"
    assert list(quantiles.data[1].x) == [5]
    assert list(quantiles.data[0].y) == ["Pass/Distinction", "Pass/Distinction"]
    assert quantiles.layout.xaxis.rangemode == "tozero"
