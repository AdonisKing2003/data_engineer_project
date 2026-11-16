"""Phân tích độ nhạy ngưỡng của quy tắc cảnh báo sớm BR4 (bảng "căn cứ chọn ngưỡng" trong báo cáo).

Chạy lại đúng truy vấn sql/br4_at_risk_all.sql trên kho Parquet (DuckDB), mỗi lần thay một ngưỡng,
giữ nguyên phần còn lại, rồi tính độ chính xác (precision) và độ bao phủ (recall) so với kết quả cuối kỳ.

Các phương án:
  - từng dấu hiệu riêng lẻ (click tích lũy dưới P25, hai tuần không click, bỏ TMA, điểm dưới 40);
  - số dấu hiệu tối thiểu: >=1, >=2 (đang dùng), >=3, đủ 4;
  - ngưỡng click P10 và P50 thay cho P25, giữ quy tắc >=2 dấu hiệu.

Chạy:
    python scripts/br4_threshold_sensitivity.py              # tuần 4
    python scripts/br4_threshold_sensitivity.py --week 4 8 12
    python scripts/br4_threshold_sensitivity.py --csv docs/br4_threshold_sensitivity.csv

Kết quả tuần 4 (kho 1x): >=2 dấu hiệu cho 3.958 SV, 3.189 cảnh báo đúng, precision 80,6%, recall 26,9%,
khớp Bảng hiệu quả BR4 trong báo cáo.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
SQL_FILE = ROOT / "sql" / "br4_at_risk_all.sql"

P25_EXPR = "QUANTILE_CONT(clicks_cum, 0.25)"

FLAGS = [
    ("Có dấu hiệu click tích lũy dưới P25", "flag_low_clicks = 1"),
    ("Có dấu hiệu hai tuần không click", "flag_inactive_2w = 1"),
    ("Có dấu hiệu bỏ bài TMA", "flag_missed_tma = 1"),
    ("Có dấu hiệu điểm trung bình dưới 40", "flag_low_score = 1"),
]
MIN_SIGNALS = [
    ("Từ 1 dấu hiệu trở lên", "risk_score >= 1"),
    ("Từ 2 dấu hiệu trở lên (đang dùng)", "risk_score >= 2"),
    ("Từ 3 dấu hiệu trở lên", "risk_score >= 3"),
    ("Đủ 4 dấu hiệu", "risk_score >= 4"),
]
CLICK_PERCENTILES = [
    ("Từ 2 dấu hiệu, ngưỡng click P10 thay cho P25", 0.10),
    ("Từ 2 dấu hiệu, ngưỡng click P50 thay cho P25", 0.50),
]


def get_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for t in ("fact_student_week", "fact_enrollment"):
        p = WH / t
        if not p.is_dir():
            raise FileNotFoundError(f"Không tìm thấy thư mục kho dữ liệu: {p} (chạy make all trước)")
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p.as_posix()}/*.parquet')")
    return con


def load_sql() -> str:
    sql = SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")
    if P25_EXPR not in sql:
        raise ValueError(f"{SQL_FILE} không còn chứa {P25_EXPR}; cần cập nhật script")
    return sql


def score(con: duckdb.DuckDBPyConnection, sql: str, week: int) -> tuple[int, int]:
    """Tạo bảng tạm r cho tuần week; trả về (số SV còn học, số SV cuối cùng rớt hoặc rút)."""
    con.execute(f"CREATE OR REPLACE TEMP TABLE r AS {sql}", [week])
    n, pos = con.execute("SELECT COUNT(*), SUM(is_unsuccessful) FROM r").fetchone()
    return int(n), int(pos)


def evaluate(con: duckdb.DuckDBPyConnection, cond: str, positives: int) -> tuple[int, int, float, float]:
    flagged, tp = con.execute(
        f"SELECT COUNT(*), COALESCE(SUM(is_unsuccessful), 0) FROM r WHERE {cond}"
    ).fetchone()
    precision = tp / flagged if flagged else 0.0
    recall = tp / positives if positives else 0.0
    return int(flagged), int(tp), precision, recall


def run_week(con: duckdb.DuckDBPyConnection, sql: str, week: int) -> list[dict]:
    rows = []
    n, pos = score(con, sql, week)
    for name, cond in FLAGS + MIN_SIGNALS:
        flagged, tp, p, r = evaluate(con, cond, pos)
        rows.append(dict(week=week, scenario=name, enrolled=n, positives=pos,
                         flagged=flagged, true_positive=tp, precision=p, recall=r))
    for name, q in CLICK_PERCENTILES:
        variant = sql.replace(P25_EXPR, f"QUANTILE_CONT(clicks_cum, {q})")
        n_v, pos_v = score(con, variant, week)
        flagged, tp, p, r = evaluate(con, "risk_score >= 2", pos_v)
        rows.append(dict(week=week, scenario=name, enrolled=n_v, positives=pos_v,
                         flagged=flagged, true_positive=tp, precision=p, recall=r))
    return rows


def fmt_int(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%".replace(".", ",")


def print_table(rows: list[dict]) -> None:
    for week in sorted({r["week"] for r in rows}):
        sub = [r for r in rows if r["week"] == week]
        print(f"\nTuần {week}: {fmt_int(sub[0]['enrolled'])} SV còn học, "
              f"{fmt_int(sub[0]['positives'])} SV cuối cùng rớt hoặc rút "
              f"(tỷ lệ nền {fmt_pct(sub[0]['positives'] / sub[0]['enrolled'])})")
        print(f"  {'Phương án':<48}{'Vào DS':>9}{'Đúng':>9}{'Precision':>11}{'Recall':>9}")
        for r in sub:
            print(f"  {r['scenario']:<48}{fmt_int(r['flagged']):>9}{fmt_int(r['true_positive']):>9}"
                  f"{fmt_pct(r['precision']):>11}{fmt_pct(r['recall']):>9}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week", type=int, nargs="+", default=[4], help="tuần cần tính (mặc định 4)")
    parser.add_argument("--csv", type=Path, help="ghi kết quả ra file CSV")
    args = parser.parse_args()

    con = get_connection()
    sql = load_sql()
    rows = [row for week in args.week for row in run_week(con, sql, week)]
    print_table(rows)

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nĐã ghi {args.csv}")


if __name__ == "__main__":
    main()
