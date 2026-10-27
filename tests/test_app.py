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


def test_attention_button_opens_offering(app):
    """Đợt rút nhiều nhất là CCC 2014B (câu 17); bấm nút thì trang cảnh báo mở đúng đợt đó."""
    at, pages = app
    open_page(at, pages, "")
    at.button(key="warning_CCC 2014B").click().run()
    assert not at.exception
    assert at.selectbox(key="br4_offering").value == "CCC 2014B"


def test_offering_is_shared_across_pages(app):
    at, pages = app
    open_page(at, pages, "render_course_page")
    at.selectbox(key="course_offering").set_value("CCC 2014B").run()
    for name, key in [("Hoc_phan", "br1_offering"), ("Canh_bao", "br4_offering"), ("Sinh_vien", "br7_offering")]:
        open_page(at, pages, name)
        assert at.selectbox(key=key).value == "CCC 2014B", name
