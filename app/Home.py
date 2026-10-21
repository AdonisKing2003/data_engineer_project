"""Interactive dashboard for the OULAD teaching and learning analytics."""

from __future__ import annotations

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
        "Đây là tương quan Spearman, không chứng minh click gây ra điểm số. "
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
            hovertemplate="Q1=%{x}<extra></extra>",
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
    st.write("Trang tổng hợp các hiện vật benchmark được bàn giao trong thư mục bench/.")
    result_dirs = [PROJECT_ROOT / "sql" / "bench" / "results", PROJECT_ROOT / "bench" / "results"]
    median_candidates = sorted(
        (path for directory in result_dirs if directory.is_dir()
         for path in directory.glob("*.medians.csv")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not median_candidates:
        st.info("Chưa có CSV trung vị benchmark để hiển thị. Trang này sẽ tự nhận hiện vật sau khi runner tạo xong.")
        return
    csv_path = median_candidates[0]
    try:
        st.dataframe(pd.read_csv(csv_path), hide_index=True, use_container_width=True)
    except Exception as error:
        st.error(f"Không đọc được {csv_path.relative_to(PROJECT_ROOT)}: {error}")
        return
    chart_path = csv_path.with_name(csv_path.name.replace(".medians.csv", ".png"))
    if chart_path.is_file():
        st.image(str(chart_path), caption="So sánh thời gian thực thi theo layout, engine và quy mô")


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
