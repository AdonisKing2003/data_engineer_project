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
    page_title="Cảnh báo sớm & rút lui | OULAD",
    page_icon="🚨",
    layout="wide"
)

# Custom CSS cho bảng cảnh báo và thẻ số liệu
st.markdown("""
<style>
    .page-header {
        font-size: 2rem;
        font-weight: 700;
        color: #991B1B;
        margin-bottom: 0.2rem;
    }
    .page-desc {
        font-size: 1rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .kpi-box {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-title {
        font-size: 0.8rem;
        color: #6B7280;
        text-transform: uppercase;
        font-weight: 600;
    }
    .kpi-number {
        font-size: 1.6rem;
        font-weight: 700;
        color: #111827;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-header">🚨 Phân hệ Cảnh báo Sớm & Rút lui</div>', unsafe_allow_html=True)
st.markdown('<div class="page-desc">Dành cho cố vấn học tập: danh sách sinh viên cần can thiệp theo tuần (BR4) và đường cong rút lui tích lũy (BR5)</div>', unsafe_allow_html=True)

# Lấy danh sách đợt học
pres_df = db.get_presentations()
pres_options = ["Tất cả các đợt (Toàn trường)"] + pres_df["presentation_label"].tolist()

# Sidebar: Bộ lọc chung, mặc định toàn trường nếu chưa chọn đợt nào ở trang khác
st.sidebar.header("🔍 Bộ lọc điều khiển")
selected_pres_label = select_offering(
    pres_options, key="br4_offering", default=pres_options[0],
    label="Chọn đợt học:", container=st.sidebar,
)

tab1, tab2 = st.tabs(["🚨 Cảnh báo sớm sinh viên nguy cơ theo tuần", "📉 Đường cong rút lui tích lũy"])

# ==============================================================================
# TAB 1: BR4 - CẢNH BÁO SỚM THEO TUẦN (WEEKLY SNAPSHOT AS-OF)
# ==============================================================================
with tab1:
    st.subheader("Cảnh báo sớm Sinh viên có nguy cơ học tập (Weekly Snapshot As-of)")
    st.caption("Nguyên tắc: Tại tuần w, chỉ sử dụng dữ liệu phát sinh đến hết tuần w. Sinh viên có từ 2 dấu hiệu nguy cơ trở lên sẽ được đưa vào danh sách can thiệp.")
    
    col_sb1, col_sb2 = st.columns([2, 2])
    with col_sb1:
        selected_week = st.slider("Tuần Snapshot (As-of Week):", min_value=0, max_value=39, value=4, step=1)
    with col_sb2:
        eval_mode = st.toggle("🔬 Bật chế độ đối soát hồi cứu (Evaluation Mode)", value=True, 
                              help="JOIN thêm cột kết quả cuối kỳ (final_result) từ bảng fact_enrollment để đo Precision & Coverage. Không ảnh hưởng đến danh sách cảnh báo (Chống rò rỉ dữ liệu).")

    # Lấy dữ liệu cảnh báo sớm thông qua db module
    mod, pres = (None, None)
    if selected_pres_label != "Tất cả các đợt (Toàn trường)":
        mod, pres = selected_pres_label.split(" ")

    with st.spinner("Đang truy vấn dữ liệu từ DuckDB..."):
        df_br4 = db.get_br4_at_risk_students(code_module=mod, code_presentation=pres, week_no=selected_week)

    if df_br4.empty:
        st.warning(f"Không có sinh viên nào đang theo học tại tuần {selected_week} trong phạm vi đã chọn.")
    else:
        total_students = len(df_br4)
        at_risk_df = df_br4[df_br4["risk_score"] >= 2].copy()
        n_at_risk = len(at_risk_df)
        risk_rate = round(100.0 * n_at_risk / total_students, 1) if total_students > 0 else 0.0

        # Hiển thị KPI cards
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Tổng SV đang học (Tuần)", f"{total_students:,}")
        k2.metric("Số SV cảnh báo nguy cơ", f"{n_at_risk:,}", delta=f"{risk_rate}% của lớp", delta_color="inverse")

        if eval_mode:
            n_unsuccessful_total = df_br4["is_unsuccessful"].sum()
            base_rate = round(100.0 * n_unsuccessful_total / total_students, 1) if total_students > 0 else 0.0
            
            n_true_positive = at_risk_df["is_unsuccessful"].sum()
            precision = round(100.0 * n_true_positive / n_at_risk, 1) if n_at_risk > 0 else 0.0
            coverage = round(100.0 * n_true_positive / n_unsuccessful_total, 1) if n_unsuccessful_total > 0 else 0.0
            
            k3.metric("Độ chính xác (Precision)", f"{precision}%", delta=f"Tỷ lệ nền: {base_rate}%")
            k4.metric("Độ bao phủ (Coverage / Recall)", f"{coverage}%", delta=f"{n_true_positive:,} / {n_unsuccessful_total:,} SV hỏng")
        else:
            k3.metric("Nguy cơ rất cao (Risk 3-4)", f"{(df_br4['risk_score'] >= 3).sum():,}")
            k4.metric("Nguy cơ vừa (Risk 2)", f"{(df_br4['risk_score'] == 2).sum():,}")

        st.markdown("---")

        # Biểu đồ phân bổ 4 cờ nguy cơ
        col_chart, col_dist = st.columns([3, 2])
        with col_chart:
            st.markdown("##### 📊 Tần suất xuất hiện của 4 dấu hiệu nguy cơ")
            flag_counts = {
                "Clicks thấp (Dưới P25)": df_br4["flag_low_clicks"].sum(),
                "Mất tương tác 2 tuần liên tiếp": df_br4["flag_inactive_2w"].sum(),
                "Bỏ ít nhất 1 bài TMA": df_br4["flag_missed_tma"].sum(),
                "Điểm trung bình < 40": df_br4["flag_low_score"].sum(),
            }
            flag_df = pd.DataFrame(list(flag_counts.items()), columns=["Dấu hiệu nguy cơ", "Số lượng sinh viên"])
            fig_flags = px.bar(
                flag_df, x="Số lượng sinh viên", y="Dấu hiệu nguy cơ", orientation="h",
                text="Số lượng sinh viên", color="Số lượng sinh viên",
                color_continuous_scale="Reds"
            )
            fig_flags.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            st.plotly_chart(fig_flags, use_container_width=True)

        with col_dist:
            st.markdown("##### 🎯 Phân bổ Điểm nguy cơ (0 - 4)")
            risk_dist = df_br4["risk_score"].value_counts().sort_index().reset_index()
            risk_dist.columns = ["Điểm nguy cơ", "Số sinh viên"]
            fig_risk = px.pie(
                risk_dist, values="Số sinh viên", names="Điểm nguy cơ",
                color="Điểm nguy cơ",
                color_discrete_map={0: "#10B981", 1: "#60A5FA", 2: "#FBBF24", 3: "#F97316", 4: "#EF4444"}
            )
            fig_risk.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_risk, use_container_width=True)

        # Bảng danh sách sinh viên nguy cơ
        st.markdown(f"##### 📋 Danh sách sinh viên nguy cơ cần can thiệp ({n_at_risk:,} sinh viên)")
        
        # Sắp xếp theo mức độ rủi ro giảm dần, clicks tăng dần
        display_df = at_risk_df.sort_values(by=["risk_score", "clicks_cum"], ascending=[False, True]).copy()
        
        # Tạo cột hiển thị trực quan
        display_df["Mức nguy cơ"] = display_df["risk_score"].apply(lambda s: f"🔴 Rất cao ({s})" if s >= 3 else f"🟠 Vừa ({s})")
        display_df["Cờ: Clicks < P25"] = display_df["flag_low_clicks"].apply(lambda x: "🚩 Có" if x else "—")
        display_df["Cờ: Không click 2w"] = display_df["flag_inactive_2w"].apply(lambda x: "🚩 Có" if x else "—")
        display_df["Cờ: Bỏ TMA"] = display_df["flag_missed_tma"].apply(lambda x: "🚩 Có" if x else "—")
        display_df["Cờ: Điểm < 40"] = display_df["flag_low_score"].apply(lambda x: "🚩 Có" if x else "—")
        display_df["Điểm TB"] = display_df["avg_score_cum"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "Chưa có")

        cols_to_show = [
            "id_student", "code_module", "code_presentation", "Mức nguy cơ",
            "Cờ: Clicks < P25", "Cờ: Không click 2w", "Cờ: Bỏ TMA", "Cờ: Điểm < 40",
            "clicks_cum", "clicks_week", "Điểm TB", "n_tma_missed_cum"
        ]
        if eval_mode:
            cols_to_show.append("final_result")

        st.dataframe(
            display_df[cols_to_show].rename(columns={
                "id_student": "Mã SV",
                "code_module": "Môn",
                "code_presentation": "Đợt",
                "clicks_cum": "Clicks tích lũy",
                "clicks_week": "Clicks tuần này",
                "n_tma_missed_cum": "Số TMA bỏ lỡ",
                "final_result": "Kết quả cuối kỳ"
            }),
            use_container_width=True,
            height=360
        )

        # Nút xuất CSV danh sách hành động
        csv_data = display_df[cols_to_show].to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Tải danh sách can thiệp (CSV)",
            data=csv_data,
            file_name=f"danh_sach_canh_bao_tuan_{selected_week}.csv",
            mime="text/csv"
        )


# ==============================================================================
# TAB 2: BR5 - ĐƯỜNG CONG RÚT LUI TÍCH LŨY (RETENTION / DROPOUT CURVE)
# ==============================================================================
with tab2:
    st.subheader("Đường cong Rút lui Tích lũy & Tỷ lệ Duy trì Người học")
    st.caption("Phân tích động thái rút lui (Unregistration) theo thời gian. Mốc then chốt: Ngày 0 (Khai giảng) và Ngày 27 (Hạn chót rút học phí).")

    # Multiselect các đợt học để vẽ biểu đồ so sánh chồng đợt
    all_pres_list = pres_df["presentation_label"].tolist()
    default_pres = [p for p in ["BBB 2014J", "CCC 2014B", "AAA 2013J"] if p in all_pres_list]
    if not default_pres and all_pres_list:
        default_pres = all_pres_list[:3]

    selected_cohorts = st.multiselect("Chọn các đợt học để so sánh:", all_pres_list, default=default_pres)

    # Thống kê tổng quan 22 đợt
    summary_df = db.get_br5_withdrawal_summary()

    # 3 Metrics cốt lõi của BR5
    b1, b2, b3 = st.columns(3)
    b1.metric("Tỷ lệ rút trước/đúng ngày 0", "30.4%", help="3.089 / 10.156 lượt rút toàn trường xảy ra trước hoặc đúng ngày khai giảng.")
    b2.metric("Ngày rút trung vị", "Ngày 27", help="50% sinh viên rút lui đưa ra quyết định trước hoặc đúng ngày 27 (cuối tuần 3).")
    top_with = summary_df.iloc[0]
    b3.metric("Đợt rút cao nhất", f"{top_with['presentation']}: {top_with['pct_withdrawn_total']}%")

    st.markdown("---")

    # Truy vấn dữ liệu theo tuần cho các đợt đã chọn
    if selected_cohorts:
        curve_df = db.get_br5_retention_curve(selected_cohorts)

        # Vẽ biểu đồ Step-line với Plotly
        fig_curve = px.line(
            curve_df, x="week_no", y="cum_withdrawal_rate_pct", color="cohort",
            line_shape="hv",  # Step-line
            markers=True,
            title="Đường cong Tỷ lệ Rút lui Tích lũy (% sinh viên đã rút lui)",
            labels={
                "week_no": "Tuần học (Week No)",
                "cum_withdrawal_rate_pct": "Tỷ lệ rút lui tích lũy (%)",
                "cohort": "Đợt học"
            }
        )
        # Thêm đường mốc ngày 0 (tuần 0) và ngày 27 (tuần 3)
        fig_curve.add_vline(x=0, line_dash="dash", line_color="#EF4444", annotation_text="Khai giảng (Tuần 0)", annotation_position="top left")
        fig_curve.add_vline(x=3, line_dash="dash", line_color="#F59E0B", annotation_text="Hạn phí (Tuần 3 - Ngày 27)", annotation_position="bottom right")
        fig_curve.update_layout(height=420, hovermode="x unified")
        st.plotly_chart(fig_curve, use_container_width=True)

    # Bảng số liệu tổng hợp 22 đợt
    with st.expander("📊 Bảng thống kê chi tiết tỷ lệ rút lui của tất cả 22 đợt học"):
        st.dataframe(
            summary_df.rename(columns={
                "presentation": "Đợt học",
                "total_students": "Tổng SV đăng ký",
                "with_day_0": "Rút ngày <= 0",
                "pct_withdrawn_day_0": "% Rút ngày <= 0",
                "with_day_27": "Rút ngày <= 27",
                "pct_withdrawn_day_27": "% Rút ngày <= 27",
                "with_total": "Tổng rút lui",
                "pct_withdrawn_total": "% Rút toàn kỳ",
                "median_unreg_day": "Ngày rút trung vị"
            }),
            use_container_width=True
        )
