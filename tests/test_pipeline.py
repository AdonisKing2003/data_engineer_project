"""Test cho 1.9, 1.10: chạy lại không nhân đôi, và bản stream khớp bản batch.
Chạy:  pytest -q tests/test_pipeline.py
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"


def load_etl_module(filename):
    """Tên file ETL bắt đầu bằng số nên không import thường được."""
    sys.path.insert(0, str(ROOT / "etl"))
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), ROOT / "etl" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reload_postgres_twice_does_not_duplicate():
    """Nạp dim_week vào PostgreSQL hai lần liên tiếp, số dòng vẫn là 43."""
    if not (WH / "dim_week").exists():
        pytest.skip("chưa chạy 02_clean_dims.py")
    psycopg = pytest.importorskip("psycopg")
    mod = load_etl_module("05_load_pg.py")
    conninfo = (f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
                f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
                f"dbname={os.getenv('POSTGRES_DB', 'oulad')}")
    try:
        conn = psycopg.connect(conninfo, connect_timeout=3, autocommit=True)
    except psycopg.OperationalError as e:
        pytest.skip(f"không kết nối được PostgreSQL: {e}")
    with conn:
        for _ in range(2):
            mod.load_table(conn, "dim_week", {})
        assert conn.execute("select count(*) from dim_week").fetchone()[0] == 43


def test_spark_outputs_use_overwrite():
    """Mọi bảng kho đều ghi qua write_table (mode overwrite), nên chạy lại không nhân đôi."""
    common = (ROOT / "etl" / "common.py").read_text()
    assert 'mode("overwrite")' in common
    for f in ["02_clean_dims.py", "03_facts.py", "06_student_week.py"]:
        src = (ROOT / "etl" / f).read_text()
        assert "write_table(" in src and ".write." not in src, f"{f} ghi bảng không qua write_table"


def test_stream_matches_batch():
    """Kết quả lần chạy stream gần nhất (stream/compare.py) không lệch dòng nào so với batch."""
    p = ROOT / "data" / "stream" / "_compare.json"
    if not p.exists():
        pytest.skip("chưa chạy make stream")
    r = json.loads(p.read_text())
    assert r["rows_compared"] == 1342949
    assert r["clicks_week_mismatch"] == 0
    assert r["clicks_cum_mismatch"] == 0
    assert r["stream_rows_not_in_batch"] == 0
    assert r["total_clicks_stream"] == r["total_clicks_batch"] == 39605099
