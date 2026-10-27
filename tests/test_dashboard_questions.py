"""Chấm 20 câu hỏi mẫu qua dashboard: mỗi câu mở đúng trang, chọn đợt/tuần như đề hỏi, rồi tìm đáp án chuẩn
trong những gì trang hiển thị (ô số, bảng, chú thích, dữ liệu biểu đồ). Không chạy SQL riêng ngoài app.

tests/test_questions.py kiểm SQL của 20 câu; file này kiểm người dùng có tìm được đáp án trên app không.
Câu đánh dấu xfail là câu dashboard chưa trả lời được; xfail strict nên khi trang được sửa, test báo XPASS
để gỡ dấu. Chạy trên kho Parquet (DATA_BACKEND=duckdb):
    pytest -q -rx tests/test_dashboard_questions.py

Lưu ý cho chương Đánh giá: câu 15 (30,4%) và câu 16 (ngày 27) đạt nhưng là số viết cứng trong
app/pages/2_Canh_bao.py, không tính từ dữ liệu.
"""
import base64
import json
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
BR3_TAB = "Click trước hạn TMA và điểm"


@pytest.fixture
def dashboard(monkeypatch):
    # Mỗi câu một AppTest mới: một câu hỏng (ví dụ chọn giá trị không có) không kéo theo câu sau.
    if not (WH / "fact_student_week").exists():
        pytest.skip("Chưa có dữ liệu warehouse")
    monkeypatch.setenv("DATA_BACKEND", "duckdb")
    at = AppTest.from_file(str(ROOT / "app" / "Home.py"), default_timeout=120).run()
    # Lấy mã trang ngay sau lần chạy đầu: mở một trang dạng file làm danh sách này đổi.
    pages = {info["url_pathname"]: h for h, info in at._registered_pages.items()}
    return at, pages


def open_page(dashboard, name):
    at, pages = dashboard
    at._page_hash = pages[name]
    at.run()
    assert not at.exception, at.exception[0].value
    return at


def metrics(at):
    return {m.label: m.value for m in at.metric}


def metric_help(at, label):
    return next(m.proto.help for m in at.metric if m.label == label)


def _decode(value):
    """Plotly 6 ghi mảng số dạng base64 trong spec của AppTest."""
    if isinstance(value, dict):
        if "bdata" in value and "dtype" in value:
            return np.frombuffer(base64.b64decode(value["bdata"]), dtype=np.dtype(value["dtype"])).tolist()
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def charts(at):
    return [_decode(json.loads(chart.proto.spec)) for chart in at.get("plotly_chart")]


def choose_course_offering(at, label, tab=None):
    at.selectbox(key="course_offering").set_value(label)
    if tab is not None:
        # AppTest không giữ tab đang chọn qua lần chạy sau (trình duyệt thì giữ), nên đặt lại.
        at.session_state["course_tab"] = tab
    at.run()


def choose_sidebar_offering(at, label):
    at.sidebar.selectbox[0].set_value(label).run()


def q01(d):
    at = open_page(d, "")
    shown = metrics(at)
    assert (shown["Sinh viên"], shown["Lượt đăng ký"]) == ("28,785", "32,593")


def q02(d):
    at = open_page(d, "")
    shown = metrics(at)
    assert [shown.get(r) for r in ("Pass", "Withdrawn", "Fail", "Distinction")] == ["37.9%", "31.2%", "21.6%", "9.3%"]


def q03(d):
    at = open_page(d, "")
    top = at.dataframe[0].value.sort_values("n_enrollments", ascending=False).iloc[0]
    assert (top.offering, int(top.n_enrollments)) == ("CCC 2014J", 2498)


def q04(d):
    at = open_page(d, "")
    assert metrics(at)["Chưa từng vào VLE"] == "3,365 lượt"
    assert "10.3%" in metric_help(at, "Chưa từng vào VLE")


def q05(d):
    at = open_page(d, "Hoc_phan")
    choose_sidebar_offering(at, "AAA 2013J")
    table = at.dataframe[0].value
    row = table[table["Mã bài"] == 1752].iloc[0]
    assert (round(float(row["% Nộp"]), 1), int(row["SV còn học"])) == (96.5, 372)


def q06(d):
    at = open_page(d, "Hoc_phan")
    choose_sidebar_offering(at, "BBB 2014J")
    table = at.dataframe[0].value
    worst = table[table["Loại"] == "TMA"].sort_values("% Trễ (TMA)", ascending=False).iloc[0]
    assert (int(worst["Mã bài"]), round(float(worst["% Trễ (TMA)"]), 1)) == (15023, 22.1)


def q07(d):
    at = open_page(d, "Hoc_phan")
    # Ô "Tỷ lệ nộp trễ TB (TMA)" là trung bình các bài của một đợt, không phải tỷ lệ chung mọi TMA.
    assert "16.8%" in metrics(at).values()


def q08(d):
    at = open_page(d, "Hoc_phan")
    text = " ".join(str(v) for v in metrics(at).values())
    assert "EEE" in text and "81.2" in text


def q09(d):
    at = open_page(d, "render_course_page")
    choose_course_offering(at, "Toàn trường")
    shown = metrics(at)
    assert shown.get("Loại học liệu nhiều click nhất") == "oucontent"
    assert "11,206,803" in metric_help(at, "Loại học liệu nhiều click nhất")
    assert "28.3%" in metric_help(at, "Loại học liệu nhiều click nhất")


def q10(d):
    at = open_page(d, "render_course_page")
    choose_course_offering(at, "Toàn trường")
    shown = metrics(at)
    assert shown.get("Tuần nhiều click nhất") == "Tuần 2"
    assert "2,307,080" in metric_help(at, "Tuần nhiều click nhất")


def q11(d):
    at = open_page(d, "render_course_page")
    choose_course_offering(at, "FFF 2014J")
    shown = metrics(at)
    assert shown["Sinh viên còn học cuối tuần"] == "2,140"
    assert shown["Trung bình toàn tuần"] == "119.2 click/sinh viên"


def q12(d):
    at = open_page(d, "render_course_page")
    choose_course_offering(at, "AAA 2013J", tab=BR3_TAB)
    titles = [c["layout"]["title"]["text"] for c in charts(at) if "title" in c["layout"]]
    assert any("19 kỳ" in title for title in titles)
    choose_course_offering(at, "GGG 2014J", tab=BR3_TAB)
    assert any("GGG không có TMA có trọng số" in info.value for info in at.info)


def q13(d):
    at = open_page(d, "render_course_page")
    choose_course_offering(at, "AAA 2013J", tab=BR3_TAB)
    row = at.dataframe[0].value.iloc[0]
    assert (int(row["n"]), round(float(row["rho"]), 2)) == (358, 0.37)


def q14(d):
    at = open_page(d, "Canh_bao")  # mặc định: toàn trường, tuần 4, bật chế độ đối soát
    shown = metrics(at)
    assert (shown["Số SV cảnh báo nguy cơ"], shown["Độ chính xác (Precision)"]) == ("3,958", "80.6%")


def q15(d):
    at = open_page(d, "Canh_bao")
    assert metrics(at)["Tỷ lệ rút trước/đúng ngày 0"] == "30.4%"


def q16(d):
    at = open_page(d, "Canh_bao")
    assert metrics(at)["Ngày rút trung vị"] == "Ngày 27"


def q17(d):
    at = open_page(d, "Canh_bao")
    assert metrics(at)["Đợt rút cao nhất"] == "CCC 2014B: 46.4%"


def q18(d):
    at = open_page(d, "render_faculty_page")
    table = at.dataframe[0].value
    row = table[table["code_presentation"] == "2014J"].iloc[0]
    assert (
        round(float(row["rate_imd_0_10_pct"]), 1),
        round(float(row["rate_imd_90_100_pct"]), 1),
        round(float(row["gap_pp"]), 1),
    ) == (41.1, 63.3, 22.2)


def q19(d):
    at = open_page(d, "Sinh_vien")  # mặc định AAA 2014J
    median = next(
        trace for chart in charts(at) for trace in chart["data"] if "Trung vị" in str(trace.get("name"))
    )
    assert round(float(dict(zip(median["x"], median["y"]))[10])) == 593


def q20(d):
    at = open_page(d, "render_student_page")
    shown = metrics(at)
    assert (shown["Sinh viên"], shown["Trung vị"]) == ("1,072", "5 click")


NOT_ANSWERED = {
    7: "Trang Nộp bài & điểm chỉ xem từng đợt; không có tỷ lệ trễ chung mọi TMA",
    8: "Trang Nộp bài & điểm chỉ xem từng đợt; không có điểm TMA trung bình theo môn",
    9: "Trang Hoạt động học tập chỉ xem từng đợt; không có tổng click toàn trường theo loại",
    10: "Trang Hoạt động học tập chỉ xem từng đợt; không có tổng click toàn trường theo tuần",
}
QUESTIONS = {number: globals()[f"q{number:02d}"] for number in range(1, 21)}


@pytest.mark.parametrize(
    "number",
    [
        pytest.param(n, marks=pytest.mark.xfail(strict=True, reason=NOT_ANSWERED[n])) if n in NOT_ANSWERED else n
        for n in QUESTIONS
    ],
)
def test_dashboard_answers_question(dashboard, number):
    QUESTIONS[number](dashboard)
