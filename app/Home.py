import streamlit as st
import sys
from pathlib import Path

# Thêm đường dẫn gốc vào sys.path để import db module
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db

st.set_page_config(
    page_title="OULAD Learning Analytics | Nhóm 32",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border-left: 4px solid #2563EB;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #111827;
    }
    .metric-lbl {
        font-size: 0.85rem;
        text-transform: uppercase;
        color: #6B7280;
        letter-spacing: 0.05em;
    }
    .br-card {
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .br-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        border-color: #93C5FD;
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #DBEAFE;
        color: #1E40AF;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-title">🎓 OULAD Learning Analytics Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Hệ thống Phân tích Học tập & Cảnh báo Sớm · Open University Dataset · Nhóm 32 (TV2)</div>', unsafe_allow_html=True)

# Lấy số liệu tổng quát
try:
    stats = db.get_overall_stats()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #3B82F6;">
            <div class="metric-lbl">Tổng sinh viên</div>
            <div class="metric-val">{stats['total_students']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #10B981;">
            <div class="metric-lbl">Lượt đăng ký khóa học</div>
            <div class="metric-val">{stats['total_enrollments']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #F59E0B;">
            <div class="metric-lbl">Số đợt học (Cohorts)</div>
            <div class="metric-val">{stats['total_presentations']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #8B5CF6;">
            <div class="metric-lbl">Số bài kiểm tra</div>
            <div class="metric-val">{stats['total_assessments']:,}</div>
        </div>
        """, unsafe_allow_html=True)
except Exception as e:
    st.warning(f"Đang tải dữ liệu từ kho... ({e})")

st.markdown("---")

# Giới thiệu phân hệ do Thành viên 2 (TV2) phụ trách
st.subheader("📌 Các bài toán nghiệp vụ do Thành viên 2 (TV2) phụ trách")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("""
    <div class="br-card">
        <span class="badge">BR4 · Trang Cảnh báo</span>
        <h4 style="margin:0 0 6px 0; color:#1F2937;">🚨 Hệ thống Cảnh báo Sớm Sinh viên Nguy cơ</h4>
        <p style="font-size:0.9rem; color:#4B5563; margin-bottom:8px;">
            Nhận diện sinh viên có nguy cơ bỏ học hoặc rớt môn theo nguyên tắc <i>Weekly Snapshot As-of</i> (tại tuần w chỉ dùng dữ liệu phát sinh đến hết tuần w).
        </p>
        <ul style="font-size:0.85rem; color:#6B7280; padding-left:18px; margin:0;">
            <li>Đánh giá 4 dấu hiệu: Clicks thấp P25, Mất tương tác 2 tuần, Bỏ thi TMA, Điểm TB &lt; 40.</li>
            <li>Đảm bảo tính chống rò rỉ nhãn (Anti-leakage Guarantee).</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="br-card">
        <span class="badge">BR1 · Trang Học phần</span>
        <h4 style="margin:0 0 6px 0; color:#1F2937;">📝 Tình hình Nộp bài, Trễ hạn & Điểm số</h4>
        <p style="font-size:0.9rem; color:#4B5563; margin-bottom:8px;">
            Theo dõi tiến độ nộp bài của sinh viên qua từng bài kiểm tra (TMA, CMA, Exam).
        </p>
        <ul style="font-size:0.85rem; color:#6B7280; padding-left:18px; margin:0;">
            <li>Mẫu số chính xác: Chỉ tính sinh viên còn đang theo học tại hạn nộp bài.</li>
            <li>Tách biệt bài chuyển điểm (is_banked) và phân tích tỷ lệ nộp trễ hạn.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col_right:
    st.markdown("""
    <div class="br-card">
        <span class="badge">BR5 · Trang Cảnh báo</span>
        <h4 style="margin:0 0 6px 0; color:#1F2937;">📉 Đường cong Rút lui Tích lũy (Dropout Curve)</h4>
        <p style="font-size:0.9rem; color:#4B5563; margin-bottom:8px;">
            Phân tích tỷ lệ duy trì người học (Retention) và đường cong rút lui tích lũy theo ngày của 22 đợt học.
        </p>
        <ul style="font-size:0.85rem; color:#6B7280; padding-left:18px; margin:0;">
            <li>Biểu đồ đường bậc thang (Step-line curve) so sánh giữa các đợt học.</li>
            <li>Phân tích thời điểm rút then chốt: trước khai giảng vs trong học kỳ.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="br-card">
        <span class="badge">BR7 · Trang Sinh viên</span>
        <h4 style="margin:0 0 6px 0; color:#1F2937;">📊 Benchmark Tiến độ Cá nhân so với Lớp</h4>
        <p style="font-size:0.9rem; color:#4B5563; margin-bottom:8px;">
            Cung cấp góc nhìn tự đánh giá cho người học: so sánh mức độ tương tác của cá nhân với phân vị cả lớp.
        </p>
        <ul style="font-size:0.85rem; color:#6B7280; padding-left:18px; margin:0;">
            <li>Trực quan hóa dải phân vị Q25 - Trung vị (Median Q50) - Q75 của cả lớp.</li>
            <li>Xác định thứ hạng phần trăm (Percentile Rank) hiện tại của sinh viên.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.info("👈 **Hướng dẫn**: Sử dụng thanh điều hướng ở cột bên trái để chuyển sang **Trang Cảnh báo (BR4 & BR5)**, **Trang Học phần (BR1)** hoặc **Trang Sinh viên (BR7)**.")
