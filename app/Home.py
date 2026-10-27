"""Interactive dashboard for the OULAD teaching and learning analytics."""

from __future__ import annotations

import json
import os
import sys
from math import atanh, isfinite, sqrt, tanh
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data import run_query  # noqa: E402


st.set_page_config(page_title="OULAD Analytics", page_icon="📊", layout="wide")


def load_query(
    query_id: str,
    parameters: Mapping[str, Any] | Sequence[Any] | None = None,
) -> pd.DataFrame:
    backend = os.getenv("DATA_BACKEND", "bigquery").strip().lower()
    return _load_query_cached(query_id, parameters, backend)


@st.cache_data(ttl=300)
def _load_query_cached(
    query_id: str,
    parameters: Mapping[str, Any] | Sequence[Any] | None,
    backend: str,
) -> pd.DataFrame:
    # Include the configured backend in the cache key so local and cloud
    # results cannot be reused across a backend switch.
    return run_query(query_id, parameters)


def show_query_error(label: str, error: Exception) -> None:
    st.error(f"Không tải được {label}: {error}")
    backend = os.getenv("DATA_BACKEND", "bigquery").strip().lower()
    if backend == "bigquery":
        st.caption(
            "Kiểm tra GCP_PROJECT_ID, BQ_DATASET, quyền truy cập và thông tin xác thực "
            "Google Cloud trong môi trường đang chạy ứng dụng."
        )
    elif backend == "duckdb":
        st.caption("Kiểm tra các bảng Parquet trong data/warehouse/ và cài đặt DuckDB.")


def render_course_page() -> None:
    st.title("Học phần")
    analysis = st.selectbox(
        "Phân tích",
        ["BR2 — Click VLE theo tuần", "BR3 — Click trước hạn TMA và điểm"],
        key="course_analysis",
    )
    if analysis.startswith("BR3"):
        render_br3_analysis()
    else:
        render_br2_analysis()


def render_br2_analysis() -> None:
    st.caption("BR2 — lượt click VLE theo tuần và loại hoạt động.")
    try:
        offerings = load_query("br2_offerings")
    except Exception as error:
        show_query_error("danh sách học phần BR2", error)
        return
    if offerings.empty:
        st.warning("Chưa có học phần nào để hiển thị cho BR2.")
        return

    required_offering_columns = {"code_module", "code_presentation"}
    missing_offering_columns = sorted(required_offering_columns - set(offerings.columns))
    if missing_offering_columns:
        st.error(
            "Danh sách học phần BR2 thiếu các cột theo hợp đồng: "
            f"{', '.join(missing_offering_columns)}"
        )
        return
    offerings = offerings.dropna(subset=["code_module", "code_presentation"])
    modules = sorted(offerings["code_module"].astype(str).unique().tolist())
    if not modules:
        st.warning("Chưa có học phần hợp lệ để hiển thị cho BR2.")
        return
    selected_module = st.selectbox("Học phần", modules, key="br2_module")
    presentations = sorted(
        offerings.loc[
            offerings["code_module"].astype(str) == selected_module, "code_presentation"
        ].astype(str).unique().tolist()
    )
    selected_presentation = st.selectbox(
        "Kỳ học", presentations, key="br2_presentation"
    )
    parameters = {
        "code_module": selected_module,
        "code_presentation": selected_presentation,
    }
    try:
        selected = load_query("br2_dashboard", parameters)
        deadlines = load_query("br2_tma_deadlines", parameters)
    except Exception as error:
        show_query_error("kết quả BR2", error)
        return
    if selected.empty:
        st.warning("Truy vấn BR2 chưa trả về dữ liệu cho học phần và kỳ đã chọn.")
        return

    required_dashboard_columns = {
        "week_no",
        "activity_type",
        "activity_type_click_share",
        "activity_type_total_clicks",
        "enrolled_students",
        "avg_clicks_per_enrolled_student",
        "activity_type_avg_clicks_per_enrolled_student",
    }
    missing_dashboard_columns = sorted(required_dashboard_columns - set(selected.columns))
    if missing_dashboard_columns:
        st.error(
            "Kết quả BR2 thiếu các cột theo hợp đồng: "
            f"{', '.join(missing_dashboard_columns)}"
        )
        return
    if "week_no" not in deadlines.columns:
        st.error("Danh sách hạn TMA BR2 phải có cột week_no.")
        return
    due_weeks = sorted(
        {
            int(week)
            for week in pd.to_numeric(deadlines["week_no"], errors="coerce").dropna()
        }
    )
    selected["week_no"] = pd.to_numeric(selected["week_no"], errors="coerce")
    selected = selected.dropna(subset=["week_no"])
    if selected.empty:
        st.warning("BR2 chưa có tuần hợp lệ cho học phần và kỳ đã chọn.")
        return
    selected["week_no"] = selected["week_no"].astype(int)
    selected = selected.sort_values(["week_no", "activity_type"])

    weeks = sorted(selected["week_no"].unique().tolist())
    default_week_index = weeks.index(0) if 0 in weeks else 0
    selected_week = st.selectbox(
        "Tuần",
        weeks,
        index=default_week_index,
        format_func=lambda week: f"Tuần {week}",
        key="br2_week",
    )
    selected_week_rows = selected.loc[selected["week_no"] == selected_week]
    week_summary = selected_week_rows.iloc[0]

    def click_average_label(value: Any) -> str:
        if pd.isna(value):
            return "—"
        return f"{float(value):.1f} click/sinh viên"

    def activity_average(activity_type: str) -> Any:
        activity_rows = selected_week_rows.loc[
            selected_week_rows["activity_type"] == activity_type,
            "activity_type_avg_clicks_per_enrolled_student",
        ]
        return activity_rows.iloc[0] if not activity_rows.empty else None

    st.subheader(f"Tóm tắt tuần {selected_week}")
    st.caption(
        "Cỡ mẫu là sinh viên còn học vào cuối tuần, kể cả sinh viên không có click."
    )
    cohort_size = week_summary["enrolled_students"]
    cohort_label = "—" if pd.isna(cohort_size) else f"{int(cohort_size):,}"
    overall_average = click_average_label(
        week_summary["avg_clicks_per_enrolled_student"]
    )
    forum_average = click_average_label(activity_average("forumng"))
    content_average = click_average_label(activity_average("oucontent"))
    cohort_metric, overall_metric, forum_metric, content_metric = st.columns(4)
    cohort_metric.metric("Sinh viên còn học cuối tuần", cohort_label)
    overall_metric.metric("Trung bình toàn tuần", overall_average)
    forum_metric.metric("Forumng", forum_average)
    content_metric.metric("Oucontent", content_average)

    heatmap_data = selected.pivot(
        index="activity_type", columns="week_no", values="activity_type_click_share"
    )
    activity_order = (
        selected.groupby("activity_type", as_index=False)["activity_type_total_clicks"]
        .sum()
        .sort_values("activity_type_total_clicks", ascending=False)["activity_type"]
        .tolist()
    )
    heatmap_data = heatmap_data.reindex(activity_order)
    heatmap = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.to_numpy() * 100,
            x=heatmap_data.columns.astype(int),
            y=heatmap_data.index,
            colorscale="Blues",
            colorbar={"title": "Tỷ trọng click (%)"},
            hovertemplate="Tuần %{x}<br>%{y}<br>Tỷ trọng: %{z:.1f}%<extra></extra>",
        )
    )
    for week in due_weeks:
        heatmap.add_vline(x=week, line_dash="dot", line_color="#d97706", opacity=0.75)
    heatmap.update_layout(
        title="Tỷ trọng click theo tuần và loại hoạt động",
        xaxis_title="Tuần",
        yaxis_title="Loại hoạt động",
        height=600,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    st.plotly_chart(heatmap, use_container_width=True, key="br2_heatmap")
    if due_weeks:
        st.caption(
            "Đường chấm màu cam đánh dấu tuần hạn TMA của kỳ đã chọn: "
            + ", ".join(str(week) for week in due_weeks)
            + "."
        )
    else:
        st.caption("Kỳ đã chọn không có hạn TMA để đánh dấu.")

    top_five = activity_order[:5]
    trend = selected.loc[selected["activity_type"].isin(top_five)]
    line = go.Figure()
    for activity_type in top_five:
        activity = trend.loc[trend["activity_type"] == activity_type].sort_values("week_no")
        line.add_trace(
            go.Scatter(
                x=activity["week_no"],
                y=activity["activity_type_total_clicks"],
                mode="lines+markers",
                name=activity_type,
                hovertemplate="Tuần %{x}<br>Click: %{y:,}<extra>%{fullData.name}</extra>",
            )
        )
    for week in due_weeks:
        line.add_vline(x=week, line_dash="dot", line_color="#9aa4b2", opacity=0.65)
    line.update_layout(
        title="Xu hướng click của 5 loại hoạt động nhiều nhất",
        xaxis_title="Tuần",
        yaxis_title="Tổng lượt click",
        height=420,
        legend={"orientation": "h", "y": 1.12, "x": 0},
        margin={"l": 20, "r": 20, "t": 80, "b": 20},
    )
    st.plotly_chart(line, use_container_width=True, key="br2_top_five")


def _fisher_interval(rho: float | None, n: int) -> tuple[float | None, float | None]:
    if rho is None or not isfinite(rho) or n <= 3:
        return None, None
    if rho <= -1 or rho >= 1:
        endpoint = -1.0 if rho < 0 else 1.0
        return endpoint, endpoint
    margin = 1.96 / sqrt(n - 3)
    z = atanh(rho)
    return tanh(z - margin), tanh(z + margin)


def render_br3_analysis() -> None:
    st.subheader("BR3 — Click trước hạn TMA đầu tiên và điểm bài")
    st.caption(
        "Tương quan, không phải nhân quả: hệ số Spearman không chứng minh click gây ra điểm số. "
        "Mẫu gồm các bài TMA đầu tiên có trọng số, không banked và có điểm."
    )
    try:
        summaries = load_query("br3_summary")
    except Exception as error:
        show_query_error("tóm tắt BR3", error)
        return
    if summaries.empty:
        st.warning("Truy vấn tóm tắt BR3 chưa trả về dữ liệu.")
        return

    required_summary_columns = {"code_module", "code_presentation", "n", "rho"}
    missing_summary_columns = sorted(required_summary_columns - set(summaries.columns))
    if missing_summary_columns:
        st.error(
            "Tóm tắt BR3 thiếu các cột theo hợp đồng: "
            f"{', '.join(missing_summary_columns)}"
        )
        return
    summaries = summaries[
        ["code_module", "code_presentation", "n", "rho"]
    ].copy()
    summaries["code_module"] = summaries["code_module"].astype(str)
    summaries["code_presentation"] = summaries["code_presentation"].astype(str)
    summaries["n"] = pd.to_numeric(summaries["n"], errors="coerce")
    summaries["rho"] = pd.to_numeric(summaries["rho"], errors="coerce")
    summaries = summaries.dropna(subset=["n"]).sort_values(
        ["code_module", "code_presentation"]
    )
    if summaries.empty:
        st.warning("Tóm tắt BR3 không có cỡ mẫu hợp lệ để hiển thị.")
        return

    intervals = summaries.apply(
        lambda row: _fisher_interval(
            None if pd.isna(row["rho"]) else float(row["rho"]), int(row["n"])
        ),
        axis=1,
    )
    summaries["ci_95_lower"] = [interval[0] for interval in intervals]
    summaries["ci_95_upper"] = [interval[1] for interval in intervals]

    forest = go.Figure()
    for _, row in summaries.iterrows():
        label = f"{row['code_module']} {row['code_presentation']}"
        if pd.notna(row["ci_95_lower"]) and pd.notna(row["ci_95_upper"]):
            forest.add_trace(
                go.Scatter(
                    x=[row["ci_95_lower"], row["ci_95_upper"]],
                    y=[label, label],
                    mode="lines",
                    line={"color": "#94a3b8", "width": 3},
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
    forest.add_trace(
        go.Scatter(
            x=summaries["rho"],
            y=summaries.apply(
                lambda row: f"{row['code_module']} {row['code_presentation']}", axis=1
            ),
            mode="markers",
            marker={"color": "#2563eb", "size": 9},
            customdata=summaries[["n", "ci_95_lower", "ci_95_upper"]].to_numpy(),
            hovertemplate=(
                "%{y}<br>ρ=%{x:.3f}<br>n=%{customdata[0]}"
                "<br>95% CI: %{customdata[1]:.3f}–%{customdata[2]:.3f}<extra></extra>"
            ),
            name="Spearman ρ",
        )
    )
    forest.add_vline(x=0, line_dash="dash", line_color="#64748b")
    forest.update_layout(
        title=f"Khoảng tin cậy 95% theo kỳ ({len(summaries)} kỳ)",
        xaxis={"title": "Spearman ρ", "range": [-1, 1]},
        yaxis={"title": "Kỳ học", "autorange": "reversed"},
        height=max(430, 28 * len(summaries) + 100),
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    st.plotly_chart(forest, use_container_width=True, key="br3_forest")

    modules = sorted(summaries["code_module"].unique().tolist())
    if "GGG" not in modules:
        modules.append("GGG")
    selected_module = st.selectbox("Học phần", modules, key="br3_module")
    if selected_module == "GGG":
        st.info("GGG không có TMA có trọng số, nên không có cặp hợp lệ để tính BR3.")
        return

    presentations = sorted(
        summaries.loc[
            summaries["code_module"] == selected_module, "code_presentation"
        ].unique().tolist()
    )
    if not presentations:
        st.warning("Không tìm thấy kỳ học BR3 cho học phần đã chọn.")
        return
    selected_presentation = st.selectbox(
        "Kỳ học", presentations, key="br3_presentation"
    )
    selected_summary = summaries.loc[
        (summaries["code_module"] == selected_module)
        & (summaries["code_presentation"] == selected_presentation)
    ]
    try:
        selected_details = load_query(
            "br3_dashboard",
            {
                "code_module": selected_module,
                "code_presentation": selected_presentation,
            },
        )
    except Exception as error:
        show_query_error("các cặp sinh viên BR3 đã chọn", error)
        return
    if selected_details.empty:
        st.warning("Không có cặp sinh viên BR3 cho học phần và kỳ đã chọn.")
        return
    required_detail_columns = {"clicks_before_deadline", "score"}
    missing_detail_columns = sorted(
        required_detail_columns - set(selected_details.columns)
    )
    if missing_detail_columns:
        st.error(
            "Các cặp BR3 thiếu các cột theo hợp đồng: "
            f"{', '.join(missing_detail_columns)}"
        )
        return

    scatter = go.Figure()
    scatter.add_trace(
        go.Scatter(
            x=selected_details["clicks_before_deadline"] + 1,
            y=selected_details["score"],
            mode="markers",
            name=f"{selected_module} {selected_presentation}",
            marker={"size": 5, "opacity": 0.35},
            customdata=selected_details[["clicks_before_deadline"]],
            hovertemplate="Click trước hạn: %{customdata[0]}<br>Điểm: %{y}<extra></extra>",
        )
    )
    scatter.update_layout(
        title=(
            f"Click trước hạn và điểm TMA: {selected_module} {selected_presentation} "
            "(trục x là log(1 + click))"
        ),
        xaxis={"title": "1 + click trước hạn", "type": "log"},
        yaxis={"title": "Điểm TMA", "range": [0, 100]},
        height=460,
        margin={"l": 20, "r": 20, "t": 80, "b": 20},
    )
    st.plotly_chart(scatter, use_container_width=True, key="br3_scatter")
    st.dataframe(
        selected_summary[
            ["code_module", "code_presentation", "n", "rho", "ci_95_lower", "ci_95_upper"]
        ].round({"rho": 3, "ci_95_lower": 3, "ci_95_upper": 3}),
        hide_index=True,
        use_container_width=True,
    )


def render_faculty_page() -> None:
    st.title("Khoa")
    st.subheader("Khoảng cách kết quả theo nhóm IMD")
    measure = st.radio(
        "Chỉ số tỷ lệ",
        ["Pass/Distinction", "Distinction"],
        horizontal=True,
        key="br6_measure",
    )
    rate_low = "rate_imd_0_10_pct" if measure == "Pass/Distinction" else "rate_distinction_imd_0_10_pct"
    rate_high = (
        "rate_imd_90_100_pct"
        if measure == "Pass/Distinction"
        else "rate_distinction_imd_90_100_pct"
    )
    gap_column = "gap_pp" if measure == "Pass/Distinction" else "distinction_gap_pp"
    st.caption(
        "Tỷ lệ tính trên enrollment; ngưỡng suppression dựa trên số sinh viên duy nhất. "
        "Các tỷ lệ và khoảng cách bị suppression không được hiển thị."
    )
    try:
        results = load_query("br6_imd_gap")
    except Exception as error:
        show_query_error("kết quả BR6", error)
        return
    if results.empty:
        st.warning("Truy vấn BR6 chưa trả về dữ liệu.")
        return
    required = {"code_presentation", rate_low, rate_high, gap_column}
    missing = sorted(required - set(results.columns))
    if missing:
        st.error(f"Kết quả BR6 thiếu các cột theo hợp đồng: {', '.join(missing)}")
        return

    figure = go.Figure()
    for _, row in results.iterrows():
        low, high = row[rate_low], row[rate_high]
        if pd.notna(low) and pd.notna(high):
            figure.add_shape(
                type="line",
                x0=float(low),
                x1=float(high),
                y0=row["code_presentation"],
                y1=row["code_presentation"],
                line={"color": "#9aa4b2", "width": 2},
                layer="below",
            )

    for rate_column, label, color in (
        (rate_low, "IMD 0–10%", "#2563eb"),
        (rate_high, "IMD 90–100%", "#d97706"),
    ):
        visible = results.loc[results[rate_column].notna()]
        count_label = (
            "n_students_imd_0_10_label"
            if rate_column == rate_low
            else "n_students_imd_90_100_label"
        )
        custom_columns = [c for c in [count_label] if c in visible.columns]
        figure.add_trace(
            go.Scatter(
                x=visible[rate_column],
                y=visible["code_presentation"],
                mode="markers",
                name=label,
                marker={"size": 12, "color": color},
                customdata=visible[custom_columns].to_numpy() if custom_columns else None,
                hovertemplate=(
                    f"Kỳ: %{{y}}<br>{label}: %{{x:.1f}}%<br>Cỡ mẫu: %{{customdata[0]}}<extra></extra>"
                    if custom_columns
                    else f"Kỳ: %{{y}}<br>{label}: %{{x:.1f}}%<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        height=360,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        xaxis={"title": f"Tỷ lệ {measure} (%)", "range": [0, 100], "ticksuffix": "%"},
        yaxis={
            "title": "Kỳ",
            "categoryorder": "array",
            "categoryarray": results["code_presentation"].tolist()[::-1],
        },
        legend={"orientation": "h", "y": 1.12, "x": 0},
    )
    st.plotly_chart(figure, use_container_width=True, key="br6_dumbbell")

    columns = ["code_module", "code_presentation"]
    for suffix in ("0_10", "90_100"):
        for column in (
            f"n_students_imd_{suffix}_label",
            f"n_enrollments_imd_{suffix}",
            f"{rate_low}" if suffix == "0_10" else f"{rate_high}",
        ):
            if column in results.columns and column not in columns:
                columns.append(column)
    columns.append(gap_column)
    st.dataframe(results[[c for c in columns if c in results.columns]], hide_index=True, use_container_width=True)


def render_student_page() -> None:
    st.title("Sinh viên")
    st.subheader("BR8 — Hoạt động diễn đàn của nhóm đạt")
    st.caption("BBB 2013J, tuần 5, loại hoạt động forumng; sinh viên không có click được tính là 0.")
    try:
        result = load_query("br8_forum_week5")
    except Exception as error:
        show_query_error("kết quả BR8", error)
        return
    if result.empty or int(result.loc[0, "n_students"]) < 30:
        st.warning("Không đủ cỡ mẫu để hiển thị tóm tắt BR8.")
        return
    row = result.iloc[0]
    q25 = float(row["q25_forum_clicks"])
    median = float(row["median_forum_clicks"])
    q75 = float(row["q75_forum_clicks"])
    left, middle, right = st.columns(3)
    left.metric("Sinh viên", f"{int(row['n_students']):,}")
    middle.metric("Trung vị", f"{median:g} click")
    right.metric("Khoảng tứ phân vị", f"{q25:g}–{q75:g} click")

    chart = go.Figure()
    label = "Pass/Distinction"
    chart.add_trace(
        go.Scatter(
            x=[q25, q75],
            y=[label, label],
            mode="lines",
            line={"color": "#60a5fa", "width": 24},
            name="Khoảng tứ phân vị",
            hovertemplate="Click: %{x}<extra></extra>",
        )
    )
    chart.add_trace(
        go.Scatter(
            x=[median],
            y=[label],
            mode="markers",
            marker={"color": "#1d4ed8", "size": 16, "symbol": "line-ns"},
            name="Trung vị",
            hovertemplate="Trung vị: %{x} click<extra></extra>",
        )
    )
    chart.update_layout(
        title="Số click forumng trong tuần 5",
        xaxis={"title": "Click", "rangemode": "tozero"},
        yaxis={"title": "Nhóm kết quả"},
        height=250,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    st.plotly_chart(chart, use_container_width=True, key="br8_quantiles")


def render_quality_page() -> None:
    st.title("Chất lượng & benchmark")
    st.write("Kết quả chỉ được hiển thị khi runner công bố một lượt benchmark thành công.")

    results_dir = PROJECT_ROOT / "bench" / "results"
    success_pointer = results_dir / "latest_success.json"
    if not success_pointer.is_file():
        st.info(
            "Chưa có lượt benchmark thành công được công bố. Sau khi nhóm xác nhận M3, "
            "hoàn tất preflight và chạy runner, kết quả sẽ xuất hiện tại đây."
        )
        return

    try:
        pointer = json.loads(success_pointer.read_text(encoding="utf-8"))
    except Exception as error:
        st.error(f"Không đọc được `bench/results/latest_success.json`: {error}")
        return

    run_id = pointer.get("run_id") if isinstance(pointer, dict) else None
    if (
        not isinstance(run_id, str)
        or not run_id.strip()
        or run_id in {".", ".."}
        or Path(run_id).name != run_id
    ):
        st.error("Con trỏ benchmark không có `run_id` hợp lệ.")
        return

    run_dir = results_dir / run_id
    try:
        run_root = run_dir.resolve()
        run_root.relative_to(results_dir.resolve())
    except (OSError, ValueError):
        st.error(f"Đường dẫn lượt benchmark `{run_id}` nằm ngoài thư mục kết quả.")
        return
    manifest_path = run_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as error:
        st.error(f"Không đọc được manifest cho lượt `{run_id}`: {error}")
        return
    if not isinstance(manifest, dict) or manifest.get("status") != "success":
        st.info(f"Lượt `{run_id}` chưa được đánh dấu thành công; không hiển thị kết quả.")
        return
    if manifest.get("run_id") != run_id:
        st.error(f"`run_id` trong manifest không khớp với con trỏ `{run_id}`.")
        return

    artifacts = manifest.get("artifacts")
    median_name = artifacts.get("medians_csv") if isinstance(artifacts, dict) else None
    if not isinstance(median_name, str) or not median_name.strip():
        st.error(f"Manifest của lượt `{run_id}` không chỉ định `artifacts.medians_csv`.")
        return
    try:
        csv_path = (run_dir / median_name).resolve()
        csv_path.relative_to(run_root)
    except (OSError, ValueError):
        st.error(f"Đường dẫn CSV trung vị trong manifest không hợp lệ cho lượt `{run_id}`.")
        return
    if not csv_path.is_file():
        st.error(f"Không tìm thấy CSV trung vị được manifest chỉ định: {csv_path.name}")
        return
    try:
        medians = pd.read_csv(csv_path)
    except Exception as error:
        st.error(f"Không đọc được CSV trung vị của lượt `{run_id}`: {error}")
        return

    median_column = next(
        (column for column in ("median_s", "median_elapsed_seconds", "median_seconds")
         if column in medians.columns),
        None,
    )
    runs_column = next(
        (column for column in ("runs", "measured_runs") if column in medians.columns),
        None,
    )
    chart_columns = {"engine", "scale", "layout", "workload"}
    missing_columns = sorted(chart_columns - set(medians.columns))
    if median_column is None or runs_column is None or missing_columns:
        missing = missing_columns[:]
        if median_column is None:
            missing.append("median_s/median_elapsed_seconds")
        if runs_column is None:
            missing.append("runs/measured_runs")
        st.error("CSV trung vị thiếu các cột cần thiết: " + ", ".join(missing))
        return

    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict):
        st.error(f"Manifest của lượt `{run_id}` không có phạm vi `coverage` hợp lệ.")
        return
    try:
        planned = int(coverage["planned"])
        selected = int(coverage["selected"])
    except (KeyError, TypeError, ValueError):
        st.error(f"Manifest của lượt `{run_id}` thiếu số tổ hợp trong `coverage`.")
        return
    excluded = coverage.get("excluded")
    if isinstance(excluded, dict):
        excluded_items = [
            {"combination": combination, "reason": reason}
            for combination, reason in excluded.items()
        ]
    elif isinstance(excluded, list):
        excluded_items = excluded
    else:
        st.error(f"Manifest của lượt `{run_id}` không có danh sách `coverage.excluded` hợp lệ.")
        return
    if selected != len(medians) or selected + len(excluded_items) != planned:
        st.error(
            f"Phạm vi trong manifest của lượt `{run_id}` không khớp với CSV trung vị."
        )
        return

    workloads = {"br1_q07", "br2_q09", "br4_q14", "br6_q18"}
    expected_cells = {
        (engine, scale, layout, workload)
        for engine in ("bq", "pg")
        for scale in (1, 5)
        for layout in ("star", "3nf", "wide")
        for workload in workloads
    }
    expected_excluded = {
        ("bq", 5, "wide", workload) for workload in workloads
    }

    def scope_key(engine: object, scale: object, layout: object, workload: object):
        try:
            normalized_scale = int(str(scale).lower().removesuffix("x").strip())
        except (TypeError, ValueError):
            return None
        normalized_layout = "3nf" if str(layout) == "three_nf" else str(layout)
        return str(engine), normalized_scale, normalized_layout, str(workload)

    selected_cells = {
        scope_key(row.engine, row.scale, row.layout, row.workload)
        for row in medians.itertuples(index=False)
    }
    excluded_cells = set()
    for item in excluded_items:
        if not isinstance(item, dict):
            continue
        combination = item.get("combination")
        if not isinstance(combination, dict):
            combination = item
        key = scope_key(
            combination.get("engine"),
            combination.get("scale"),
            combination.get("layout"),
            combination.get("workload"),
        )
        if key is not None:
            excluded_cells.add(key)
    if (
        planned != 48
        or selected != 44
        or len(excluded_items) != 4
        or None in selected_cells
        or selected_cells != expected_cells - expected_excluded
        or excluded_cells != expected_excluded
    ):
        st.error(
            f"Run `{run_id}` không khớp ma trận benchmark 44/48 đã chốt."
        )
        return

    measured_runs = pd.to_numeric(medians[runs_column], errors="coerce").dropna()
    if measured_runs.empty:
        run_count_label = "—"
    else:
        run_counts = sorted({int(value) if float(value).is_integer() else float(value)
                             for value in measured_runs})
        if len(run_counts) == 1:
            run_count_label = f"{run_counts[0]} / tổ hợp"
        else:
            run_count_label = f"{run_counts[0]}–{run_counts[-1]} / tổ hợp"

    st.caption(f"Run ID: `{run_id}`")
    completed_at_utc = manifest.get("completed_at_utc")
    if completed_at_utc:
        st.caption(f"Thời điểm run thành công gần nhất: {completed_at_utc}")
    scope_col, excluded_col, repetitions_col = st.columns(3)
    scope_col.metric("Phạm vi", f"{selected}/{planned}")
    excluded_col.metric("Tổ hợp loại trừ", len(excluded_items))
    repetitions_col.metric("Lượt đo theo CSV", run_count_label)

    chart_name = artifacts.get("chart_html") if isinstance(artifacts, dict) else None
    if isinstance(chart_name, str) and chart_name.strip():
        try:
            chart_path = (run_dir / chart_name).resolve()
            chart_path.relative_to(run_root)
        except (OSError, ValueError):
            chart_path = None
        if chart_path is not None and chart_path.is_file():
            st.download_button(
                "Tải biểu đồ HTML tương tác",
                data=chart_path.read_bytes(),
                file_name=f"benchmark-{run_id}.html",
                mime="text/html",
            )

    st.subheader("Tổ hợp bị loại trừ")
    if excluded_items:
        exclusion_rows = []
        for item in excluded_items:
            if isinstance(item, dict):
                combination = item.get("combination")
                if combination is None:
                    combination = {
                        field: item[field]
                        for field in ("engine", "scale", "layout", "workload")
                        if field in item
                    }
                if isinstance(combination, dict):
                    parts = []
                    for field in ("engine", "scale", "layout", "workload"):
                        value = combination.get(field)
                        if value is not None:
                            label = str(value)
                            if field == "scale" and not label.lower().endswith("x"):
                                label += "x"
                            parts.append(label)
                    combination_label = " · ".join(parts) or str(combination)
                else:
                    combination_label = str(combination or item.get("id") or "—")
                reason = item.get("reason") or item.get("exclusion_reason") or "Không ghi lý do trong manifest"
            else:
                combination_label = str(item)
                reason = "Không ghi lý do trong manifest"
            exclusion_rows.append({"Tổ hợp": combination_label, "Lý do": reason})
        st.dataframe(pd.DataFrame(exclusion_rows), hide_index=True, use_container_width=True)
    else:
        st.info("Manifest không ghi chi tiết các tổ hợp bị loại trừ.")

    median_values = pd.to_numeric(medians[median_column], errors="coerce")
    chart_data = medians.copy()
    chart_data["_median_seconds"] = median_values
    chart_data["_scale"] = pd.to_numeric(
        chart_data["scale"].astype(str).str.replace("x", "", regex=False).str.strip(),
        errors="coerce",
    )
    chart_data = chart_data.dropna(subset=["_median_seconds", "_scale"])
    if chart_data.empty:
        st.error("CSV trung vị không có thời lượng số hợp lệ để vẽ biểu đồ.")
        return

    st.subheader("Trung vị thời gian theo layout")
    workloads = sorted(chart_data["workload"].astype(str).unique())
    scales = sorted(chart_data["_scale"].astype(int).unique())
    selector_workload, selector_scale = st.columns(2)
    selected_workload = selector_workload.selectbox(
        "Workload", workloads, key="quality_benchmark_workload"
    )
    selected_scale = selector_scale.selectbox(
        "Quy mô", scales, format_func=lambda value: f"{value}x", key="quality_benchmark_scale"
    )
    selected_rows = chart_data.loc[
        (chart_data["workload"].astype(str) == selected_workload)
        & (chart_data["_scale"] == selected_scale)
    ]
    layout_names = {"3nf": "partial normalization", "three_nf": "partial normalization"}
    engine_names = {"bq": "BigQuery", "pg": "PostgreSQL"}
    figure = go.Figure()
    for engine in sorted(selected_rows["engine"].astype(str).unique()):
        engine_rows = selected_rows.loc[selected_rows["engine"].astype(str) == engine]
        layouts = engine_rows["layout"].astype(str)
        figure.add_trace(
            go.Bar(
                name=engine_names.get(engine, engine),
                x=[layout_names.get(layout, layout) for layout in layouts],
                y=engine_rows["_median_seconds"],
                customdata=engine_rows[runs_column],
                hovertemplate="%{x}<br>Median: %{y:.3f} s<br>Runs: %{customdata}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(
        title=f"{selected_workload} · {selected_scale}x",
        barmode="group",
        xaxis_title="Layout",
        yaxis_title="Median time (seconds)",
        template="plotly_white",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        legend_title_text="Engine",
    )
    st.plotly_chart(figure, use_container_width=True, key="quality_benchmark_medians")

    st.subheader("Bảng trung vị")
    visible_columns = ["engine", "scale", "layout", "workload", median_column, runs_column]
    st.dataframe(medians[visible_columns], hide_index=True, use_container_width=True)


# st.navigation disables auto-discovery of app/pages/, so TV2's page scripts
# (BR1, BR4/BR5, BR7) are registered here explicitly.
navigation = st.navigation(
    [
        st.Page(render_course_page, title="Học phần", icon="📚"),
        st.Page("pages/1_Hoc_phan.py", title="Học phần: nộp bài & điểm (BR1)", icon="📝"),
        st.Page("pages/2_Canh_bao.py", title="Cảnh báo", icon="⚠️"),
        st.Page(render_faculty_page, title="Khoa", icon="🏫"),
        st.Page(render_student_page, title="Sinh viên", icon="🎓"),
        st.Page("pages/4_Sinh_vien.py", title="Sinh viên: tiến độ so với lớp (BR7)", icon="📊"),
        st.Page(render_quality_page, title="Chất lượng & benchmark", icon="📈"),
    ],
    position="sidebar",
)
navigation.run()
