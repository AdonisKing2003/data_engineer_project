import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

# Thêm đường dẫn app vào sys.path
APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db
from state import select_offering

st.set_page_config(
    page_title="Nộp bài & điểm | OULAD",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Nộp bài, trễ hạn & phân phối điểm")
st.caption("Dành cho trưởng môn và giảng viên (BR1).")

# Bộ lọc chọn đợt học, dùng chung với các trang khác
pres_df = db.get_presentations()
pres_labels = pres_df["presentation_label"].tolist()

# Mặc định BBB 2014J nếu chưa chọn đợt nào ở trang khác
selected_pres = select_offering(
    pres_labels, key="br1_offering", default="BBB 2014J",
    label="Chọn đợt học để phân tích:", container=st.sidebar,
)

mod, pres = selected_pres.split(" ")

# Truy vấn chi tiết các bài kiểm tra của đợt học thông qua db module
df_assessments = db.get_br1_assessment_stats(mod, pres)

if df_assessments.empty:
    st.warning("Không có dữ liệu bài kiểm tra cho đợt học này.")
else:
    # KPI metrics tổng quan
    total_assessments = len(df_assessments)
    tma_df = df_assessments[df_assessments["assessment_type"] == "TMA"]
    avg_sub_rate = round(df_assessments["submission_rate_pct"].mean(), 1)
    avg_late_rate = round(tma_df["late_rate_pct"].mean(), 1) if not tma_df.empty else 0.0
    med_score = round(df_assessments["median_score"].median(), 1)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số bài kiểm tra", total_assessments)
    c2.metric("Tỷ lệ nộp bài TB", f"{avg_sub_rate}%")
    c3.metric("Tỷ lệ nộp trễ TB (TMA)", f"{avg_late_rate}%")
    c4.metric("Điểm trung vị đợt", med_score)

    st.markdown("---")

    # Biểu đồ Plotly: Tỷ lệ nộp vs Tỷ lệ trễ
    st.subheader(f"📊 Tiến độ Nộp bài & Tỷ lệ Trễ hạn — {selected_pres}")
    
    fig_rates = go.Figure()
    fig_rates.add_trace(go.Bar(
        x=df_assessments["assessment_label"],
        y=df_assessments["submission_rate_pct"],
        name="Tỷ lệ nộp bài (%)",
        marker_color="#2563EB",
        text=df_assessments["submission_rate_pct"].apply(lambda v: f"{v}%"),
        textposition="outside"
    ))
    fig_rates.add_trace(go.Bar(
        x=df_assessments["assessment_label"],
        y=df_assessments["late_rate_pct"],
        name="Tỷ lệ trễ hạn TMA (%)",
        marker_color="#EF4444",
        text=df_assessments["late_rate_pct"].apply(lambda v: f"{v}%" if v > 0 else ""),
        textposition="outside"
    ))
    fig_rates.update_layout(
        barmode="group",
        height=380,
        yaxis=dict(title="Tỷ lệ phần trăm (%)", range=[0, 115]),
        xaxis=dict(title="Bài kiểm tra"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_rates, use_container_width=True)

    # Biểu đồ Box Plot: Phân phối điểm số (lấy dữ liệu điểm thực tế của từng bài)
    st.subheader(f"📦 Phân phối Điểm số từng bài kiểm tra — {selected_pres}")
    
    df_scores = db.get_br1_assessment_scores(mod, pres)
    
    if not df_scores.empty:
        fig_box = px.box(
            df_scores, x="assessment_label", y="score",
            color="assessment_label",
            points="outliers",
            labels={"assessment_label": "Bài kiểm tra", "score": "Điểm số (0 - 100)"}
        )
        # Thêm đường mốc 40 điểm đạt
        fig_box.add_hline(y=40, line_dash="dash", line_color="#10B981", annotation_text="Ngưỡng đạt (40 điểm)")
        fig_box.update_layout(height=400, showlegend=False, yaxis=dict(range=[0, 105]))
        st.plotly_chart(fig_box, use_container_width=True)

    # Bảng số liệu chi tiết
    st.subheader("📋 Bảng thống kê chi tiết theo từng bài kiểm tra")
    st.dataframe(
        df_assessments[[
            "id_assessment", "assessment_type", "deadline", "weight",
            "active_students", "submitted_regular", "banked_students", "late_submissions",
            "submission_rate_pct", "late_rate_pct", "p25_score", "median_score", "p75_score", "pass_rate_pct"
        ]].rename(columns={
            "id_assessment": "Mã bài",
            "assessment_type": "Loại",
            "deadline": "Hạn nộp (ngày)",
            "weight": "Trọng số (%)",
            "active_students": "SV còn học",
            "submitted_regular": "Bài nộp hợp lệ",
            "banked_students": "Chuyển điểm",
            "late_submissions": "Số bài trễ",
            "submission_rate_pct": "% Nộp",
            "late_rate_pct": "% Trễ (TMA)",
            "p25_score": "Điểm Q25",
            "median_score": "Trung vị điểm",
            "p75_score": "Điểm Q75",
            "pass_rate_pct": "% Đạt (>=40)"
        }),
        use_container_width=True
    )
