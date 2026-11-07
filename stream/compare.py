"""Việc 1.9, bước 4: so kết quả stream với bản batch fact_student_week (việc 1.8).

- Bản stream: với mỗi (SV, đợt, tuần) lấy dòng có batch_id lớn nhất trong data/stream/out/updates.
- So trên toàn bộ khung SV × tuần của bản batch: tuần không có trong bản stream tính là 0 click.
  clicks_cum của bản stream = cộng dồn clicks_week theo tuần.
- Ghi báo cáo chênh lệch ra data/stream/_compare.json. Lệch thì thoát với mã lỗi.

Chạy trong container:
    python stream/compare.py
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {  # nguồn -> (thư mục cập nhật, mẫu file, file báo cáo)
    "file":  (ROOT / "data" / "stream" / "out" / "updates", "*.parquet", "_compare.json"),
    "kafka": (ROOT / "data" / "stream" / "out_kafka" / "updates", "*/*.parquet", "_compare_kafka.json"),
}
BATCH = ROOT / "data" / "warehouse" / "fact_student_week"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=SOURCES, default="file")
    updates, pattern, report_name = SOURCES[ap.parse_args().source]
    files = f"{updates}/{pattern}"
    report_path = ROOT / "data" / "stream" / report_name
    for p, hint in [(updates, "make stream hoặc make stream-kafka"), (BATCH, "make student-week")]:
        if not p.exists():
            sys.exit(f"Thiếu {p}. Chạy {hint} trước.")

    con = duckdb.connect()
    con.sql(f"""create view stream_latest as
        select * exclude (batch_id) from read_parquet('{files}')
        qualify row_number() over (partition by id_student, code_module, code_presentation, week_no
                                   order by batch_id desc) = 1""")
    con.sql(f"""create view compared as
        select b.id_student, b.code_module, b.code_presentation, b.week_no,
               b.clicks_week as batch_week, b.clicks_cum as batch_cum,
               coalesce(s.clicks_week, 0) as stream_week,
               sum(coalesce(s.clicks_week, 0)) over (
                   partition by b.id_student, b.code_module, b.code_presentation order by b.week_no
               ) as stream_cum
        from read_parquet('{BATCH}/*.parquet') b
        left join stream_latest s using (id_student, code_module, code_presentation, week_no)""")

    r = con.sql("""select count(*),
                          count(*) filter (batch_week <> stream_week),
                          count(*) filter (batch_cum <> stream_cum),
                          sum(batch_week), sum(stream_week)
                   from compared""").fetchone()
    stream_only = con.sql(f"""select count(*) from stream_latest s anti join
        read_parquet('{BATCH}/*.parquet') b using (id_student, code_module, code_presentation, week_no)""").fetchone()[0]
    n_updates = con.sql(f"select count(*) from read_parquet('{files}')").fetchone()[0]

    report = {
        "rows_compared": r[0],
        "clicks_week_mismatch": r[1],
        "clicks_cum_mismatch": r[2],
        "total_clicks_batch": int(r[3]),
        "total_clicks_stream": int(r[4]),
        "stream_rows_not_in_batch": stream_only,
        "stream_update_rows_written": n_updates,
        "stream_rows_latest": con.sql("select count(*) from stream_latest").fetchone()[0],
    }
    report_path.write_text(json.dumps(report, indent=2))
    for k, v in report.items():
        print(f"{k:28s} {v:>12,}")
    ok = report["clicks_week_mismatch"] == report["clicks_cum_mismatch"] == stream_only == 0
    if not ok:
        sys.exit("Stream và batch LỆCH, xem số ở trên.")
    print("Xong 1.9: bản stream khớp bản batch trên clicks_week và clicks_cum.")


if __name__ == "__main__":
    main()
