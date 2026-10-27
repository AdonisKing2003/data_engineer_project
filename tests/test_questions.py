"""Test cho 20 câu hỏi mẫu: mỗi file sql/questions/qNN.sql chạy trên kho Parquet (DuckDB) phải ra đúng đáp án chuẩn.

Đáp án lấy từ docs/checklist_tuan2.md (tính độc lập từ CSV gốc bằng dap_an_cau_hoi_mau.sql).
Các file viết bằng SQL chung nên cũng chạy được trên BigQuery, PostgreSQL:
    python scripts/run_sql.py sql/questions/q05.sql --engine pg
"""
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
QUESTIONS = ROOT / "sql" / "questions"
TABLES = ["dim_presentation", "dim_student", "dim_assessment", "dim_vle_site", "dim_week",
          "fact_enrollment", "fact_vle_daily", "fact_submission", "fact_student_week"]

# câu -> hàm nhận danh sách dòng kết quả, trả về True nếu đúng đáp án
EXPECTED = {
    1: lambda r: r[0] == (32593, 28785),
    2: lambda r: [(x[0], x[2]) for x in r] == [("Pass", 37.9), ("Withdrawn", 31.2), ("Fail", 21.6), ("Distinction", 9.3)],
    3: lambda r: r[0] == ("CCC", "2014J", 2498),
    4: lambda r: r[0] == (3365, 10.3),
    5: lambda r: r[0] == (372, 359, 96.5),
    6: lambda r: r[0] == (15023, 152, 22.1),
    7: lambda r: r[0] == (16320, 16.8),
    8: lambda r: r[0] == ("EEE", 81.2) and r[-1] == ("GGG", 68.5),
    9: lambda r: r[0] == ("oucontent", 11206803, 39605099, 28.3),
    10: lambda r: r[0] == (2, 2307080),
    11: lambda r: r[0][:5] == ("FFF", "2014J", 0, 2140, 255054) and round(r[0][5], 1) == 119.2,
    12: lambda r: r[0] == (19, 3, "GGG 2013J, GGG 2014B, GGG 2014J"),
    13: lambda r: r[0][2] == 358 and round(r[0][3], 2) == 0.37,
    14: lambda r: r[0] == (27250, 3958, 80.6, 43.5),
    15: lambda r: r[0] == (3089, 10156, 30.4),
    16: lambda r: r[0][1] == 27,
    17: lambda r: r[0] == ("CCC", "2014B", 46.4),
    18: lambda r: r[0][2:] == (41.1, 63.3, 22.2),
    19: lambda r: r[0] == (336, 593),
    20: lambda r: r[0] == (1072, 0, 5, 22),
}


@pytest.fixture(scope="module")
def db():
    con = duckdb.connect()
    for t in TABLES:
        if not (WH / t).exists():
            pytest.skip(f"Chưa có dữ liệu warehouse: {t}")
        con.sql(f"create view {t} as select * from read_parquet('{WH / t}/*.parquet')")
    return con


@pytest.mark.parametrize("number", sorted(EXPECTED))
def test_question_answer(db, number):
    path = QUESTIONS / f"q{number:02d}.sql"
    assert path.exists(), f"Thiếu {path.relative_to(ROOT)}"
    rows = db.sql(path.read_text(encoding="utf-8")).fetchall()
    rows = [tuple(float(v) if isinstance(v, float) else v for v in row) for row in rows]
    assert EXPECTED[number](rows), f"q{number:02d} ra {rows[:3]}"
