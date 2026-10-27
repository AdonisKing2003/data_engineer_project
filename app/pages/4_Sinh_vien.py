import streamlit as st
import pandas as pd
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
    page_title="Tiến độ so với lớp | OULAD",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Tiến độ của tôi so với cả lớp")
st.caption("Dành cho sinh viên tự đánh giá: so click tích lũy với dải phân vị của lớp (BR7).")

# Bộ lọc chọn đợt học, dùng chung với các trang khác
pres_df = db.get_presentations()
pres_labels = pres_df["presentation_label"].tolist()

selected_pres = select_offering(
    pres_labels, key="br7_offering", default="AAA 2014J",
    label="Chọn đợt học:", container=st.sidebar,
)
mod, pres = selected_pres.split(" ")

# Lấy danh sách sinh viên trong đợt học này thông qua db module
student_list = db.get_br7_students_in_presentation(mod, pres)

if not student_list:
    st.warning("Không có dữ liệu sinh viên cho đợt học này.")
    st.stop()

# Chọn sinh viên
# Quản lý sinh viên đang chọn trong session_state
if "current_student_id" not in st.session_state or st.session_state["current_student_id"] not in student_list:
    st.session_state["current_student_id"] = student_list[0]

col_sel, col_btn = st.columns([3, 1])
with col_btn:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    if st.button("🎲 Chọn ngẫu nhiên sinh viên"):
        import random
        st.session_state["current_student_id"] = random.choice(student_list)
        st.rerun()

with col_sel:
    curr_idx = student_list.index(st.session_state["current_student_id"])
    selected_student = st.selectbox(
        "Chọn mã sinh viên (id_student):",
        student_list,
        index=curr_idx,
        help="Chọn một sinh viên để xem đồ thị tiến độ so với dải phân vị cả lớp."
    )
    st.session_state["current_student_id"] = selected_student

# ------------------------------------------------------------------------------
# 1. TRUY VẤN DẢI PHÂN VỊ CỦA CẢ LỚP THEO TUẦN (COHORT BENCHMARK)
# ------------------------------------------------------------------------------
df_cohort = db.get_br7_cohort_benchmark(mod, pres)

# ------------------------------------------------------------------------------
# 2. TRUY VẤN TIẾN TRÌNH CÁ NHÂN CỦA SINH VIÊN
# ------------------------------------------------------------------------------
df_student = db.get_br7_student_progress(mod, pres, selected_student)

if df_student.empty:
    st.info(f"Sinh viên {selected_student} không có dữ liệu hoạt động theo tuần.")
    st.stop()

# Thông tin tổng quan sinh viên
latest_record = df_student.iloc[-1]
final_res = latest_record["final_result"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Mã sinh viên", f"SV #{selected_student}")
c2.metric("Clicks tích lũy", f"{latest_record['clicks_cum']:,}")
c3.metric("Điểm TB tích lũy", f"{latest_record['avg_score_cum']:.1f}" if pd.notnull(latest_record['avg_score_cum']) else "Chưa có")
c4.metric("Kết quả cuối kỳ", final_res)

st.markdown("---")

# ------------------------------------------------------------------------------
# 3. BIỂU ĐỒ SO SÁNH CLICKS CỦA SINH VIÊN VỚI DẢI PHÂN VỊ CẢ LỚP
# ------------------------------------------------------------------------------
st.subheader("📈 So sánh Tương tác (Clicks tích lũy) với Dải phân vị Cả lớp")

# Merge dữ liệu để vẽ biểu đồ
student_subset = df_student[["week_no", "clicks_cum", "avg_score_cum"]].rename(
    columns={"clicks_cum": "clicks_cum_student", "avg_score_cum": "avg_score_cum_student"}
)
merged_df = pd.merge(df_cohort, student_subset, on="week_no", how="left")

fig_clicks = go.Figure()

# Đường giới hạn trên Q75 (dùng để tô dải màu)
fig_clicks.add_trace(go.Scatter(
    x=merged_df["week_no"],
    y=merged_df["q75_clicks"],
    mode="lines",
    line=dict(width=0),
    showlegend=False,
    hoverinfo="skip"
))

# Đường giới hạn dưới Q25 và tô bóng dải Q25 - Q75
fig_clicks.add_trace(go.Scatter(
    x=merged_df["week_no"],
    y=merged_df["q25_clicks"],
    mode="lines",
    line=dict(width=0),
    fill="tonexty",
    fillcolor="rgba(59, 130, 246, 0.15)",
    name="Khoảng 50% giữa của lớp (Q25 - Q75)",
    hoverinfo="skip"
))

# Đường trung vị cả lớp (Median Q50)
fig_clicks.add_trace(go.Scatter(
    x=merged_df["week_no"],
    y=merged_df["median_clicks"],
    mode="lines",
    line=dict(color="#2563EB", width=2, dash="dash"),
    name="Trung vị cả lớp (Median Q50)"
))

# Đường clicks của sinh viên đang chọn
fig_clicks.add_trace(go.Scatter(
    x=merged_df["week_no"],
    y=merged_df["clicks_cum_student"],
    mode="lines+markers",
    line=dict(color="#DC2626", width=3),
    marker=dict(size=6, color="#DC2626"),
    name=f"Sinh viên #{selected_student}"
))

fig_clicks.update_layout(
    height=420,
    xaxis=dict(title="Tuần học (Week No)"),
    yaxis=dict(title="Số clicks tích lũy"),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_clicks, use_container_width=True)

# ------------------------------------------------------------------------------
# 4. ĐÁNH GIÁ THỨ HẠNG PHÂN VỊ CỦA SINH VIÊN (PERCENTILE RANK)
# ------------------------------------------------------------------------------
st.subheader("🎯 Đánh giá Vị thế Học tập Hiện tại")

# Chọn tuần để đánh giá phân vị (mặc định lấy tuần 10 hoặc tuần cuối cùng)
eval_week = st.slider("Chọn tuần đánh giá:", min_value=0, max_value=int(merged_df["week_no"].max()), value=min(10, int(merged_df["week_no"].max())))

sql_rank = """
WITH cohort AS (
    SELECT
        id_student,
        clicks_cum,
        PERCENT_RANK() OVER (ORDER BY clicks_cum) * 100.0 AS click_pct_rank
    FROM fact_student_week
    WHERE code_module = ? AND code_presentation = ?
      AND week_no = ?
      AND is_enrolled
)
SELECT
    ROUND(click_pct_rank, 1) AS click_rank,
    clicks_cum
FROM cohort
WHERE id_student = ?;
"""
rank_df = db.run_query(sql_rank, [mod, pres, eval_week, int(selected_student)])

if not rank_df.empty:
    student_rank = rank_df.iloc[0]["click_rank"]
    student_clicks = int(rank_df["clicks_cum"].iloc[0])
    
    col_rank_val, col_rank_desc = st.columns([1, 3])
    with col_rank_val:
        st.metric("Phân vị Phần trăm (Percentile)", f"Top {100 - student_rank:.1f}%", help="Cao hơn bao nhiêu % sinh viên trong lớp")
    with col_rank_desc:
        if student_rank >= 75:
            st.success(f"🌟 **Rất tích cực**: Sinh viên có {student_clicks:,} clicks tại tuần {eval_week}, vượt qua 75% bạn cùng lớp. Tiếp tục phát huy!")
        elif student_rank >= 25:
            st.info(f"👍 **Ổn định**: Sinh viên có {student_clicks:,} clicks tại tuần {eval_week}, nằm trong mức hoạt động phổ biến của lớp (vùng 50% giữa).")
        else:
            st.warning(f"⚠️ **Cần tăng cường**: Sinh viên có {student_clicks:,} clicks tại tuần {eval_week}, thuộc nhóm 25% tương tác thấp nhất lớp. Cần chủ động truy cập thêm tài liệu học tập VLE.")
else:
    st.info(f"Sinh viên không có tương tác hoặc đã rút lui tại tuần {eval_week}.")
