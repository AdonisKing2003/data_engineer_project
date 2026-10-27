"""Test khói cho dashboard: mọi trang mở được không lỗi, và đợt học chọn ở trang này được trang khác dùng lại.

Chạy trên kho Parquet (DATA_BACKEND=duckdb) để không tốn quota BigQuery.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"


@pytest.fixture
def app(monkeypatch):
    if not (WH / "fact_student_week").exists():
        pytest.skip("Chưa có dữ liệu warehouse")
    monkeypatch.setenv("DATA_BACKEND", "duckdb")
    at = AppTest.from_file(str(ROOT / "app" / "Home.py"), default_timeout=240).run()
    # AppTest chỉ chuyển được trang dạng file; trang dạng hàm thì gán thẳng mã trang
    pages = {info["url_pathname"]: h for h, info in at._registered_pages.items()}
    return at, pages


def open_page(at, pages, name):
    at._page_hash = pages[name]
    return at.run()


def test_every_page_renders(app):
    at, pages = app
    assert len(pages) == 8
    for name in pages:
        open_page(at, pages, name)
        assert not at.exception, f"Trang {name or 'Tổng quan'}: {at.exception[0].value}"
        assert not at.error, f"Trang {name or 'Tổng quan'}: {at.error[0].value}"


def test_overview_matches_contract(app):
    at, pages = app
    open_page(at, pages, "")
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Sinh viên"] == "28,785"
    assert metrics["Tỷ lệ đạt"] == "47.2%"  # 15.385 / 32.593 lượt Pass + Distinction
    assert metrics["Tỷ lệ rút"] == "31.2%"  # câu 2
    assert metrics["Chưa từng vào VLE"] == "3,365 lượt"  # câu 4


def test_attention_lists_worst_offerings(app):
    """Đợt rút nhiều nhất là CCC 2014B (câu 17), đợt đạt ít nhất cũng là CCC 2014B (34,2%)."""
    at, pages = app
    open_page(at, pages, "")
    lines = [m.value for m in at.markdown]
    assert "CCC 2014B · **46.4%**" in lines
    assert "CCC 2014B · **34.2%**" in lines


def test_offering_is_kept_when_returning_to_page(app):
    """Đợt chọn ở trang Hoạt động học tập được giữ khi sang trang khác rồi quay lại."""
    at, pages = app
    open_page(at, pages, "render_course_page")
    at.selectbox(key="course_offering").set_value("CCC 2014B").run()
    open_page(at, pages, "")
    open_page(at, pages, "render_course_page")
    assert at.selectbox(key="course_offering").value == "CCC 2014B"
