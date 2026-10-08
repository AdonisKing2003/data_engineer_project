"""Việc 1.9, bước 1: chia studentVle thành từng file CSV theo ngày, làm nguồn để phát lại.

Đọc staging (dữ liệu click gốc, chưa gộp trùng) và ghi data/stream/days/day_<thứ tự>_<ngày>.csv.
Thứ tự đứng đầu tên file để sắp xếp theo tên cũng là sắp xếp theo ngày (kể cả ngày âm).

Chạy trong container:
    python stream/split_days.py
"""
import shutil
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "staging" / "stg_student_vle"
DAYS_DIR = ROOT / "data" / "stream" / "days"


def main():
    if not SRC.exists():
        raise SystemExit(f"Thiếu {SRC}. Chạy make staging trước.")
    shutil.rmtree(DAYS_DIR, ignore_errors=True)
    DAYS_DIR.mkdir(parents=True)

    con = duckdb.connect()
    con.sql(f"create view clicks as select * from read_parquet('{SRC}/*.parquet')")
    days = [r[0] for r in con.sql("select distinct date from clicks order by date").fetchall()]
    total = 0
    for i, day in enumerate(days):
        out = DAYS_DIR / f"day_{i:03d}_{day}.csv"
        con.sql(f"copy (select * from clicks where date = {day}) to '{out}' (header, delimiter ',')")
        total += con.sql(f"select count(*) from read_csv('{out}')").fetchone()[0]
    print(f"Đã chia {total:,} dòng click thành {len(days)} file theo ngày "
          f"(ngày {days[0]} đến {days[-1]}) trong {DAYS_DIR}")


if __name__ == "__main__":
    main()
