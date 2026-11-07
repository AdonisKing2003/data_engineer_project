"""Trực quan hóa BR5: Đường cong rút lui tích lũy và tỷ lệ duy trì người học.

Vẽ biểu đồ bậc thang (step-line) so sánh động thái rút lui của các đợt học (BBB 2014J, CCC 2014B, AAA 2013J),
đánh dấu các mốc then chốt: Ngày 0 (Khai giảng) và Ngày 27 (Hạn rút học phí / Ngày rút trung vị).

Chạy:
    python scripts/run_br5.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import duckdb
import pandas as pd
import matplotlib.pyplot as plt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Segoe UI", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
FIG_DIR = ROOT / "docs" / "figures"


def main() -> None:
    con = duckdb.connect()
    p_enroll = WH / "fact_enrollment"
    con.sql(f"CREATE VIEW fact_enrollment AS SELECT * FROM read_parquet('{p_enroll.as_posix()}/*.parquet')")

    # 1. Thống kê tổng quan BR5
    summary = con.sql("""
    SELECT
        COUNTIF(is_withdrawn AND date_unregistration <= 0) AS withdrawn_day_0,
        COUNTIF(is_withdrawn) AS total_withdrawn,
        ROUND(100.0 * COUNTIF(is_withdrawn AND date_unregistration <= 0) / COUNTIF(is_withdrawn), 1) AS pct_day_0,
        MEDIAN(date_unregistration) FILTER (WHERE is_withdrawn) AS median_unreg_day
    FROM fact_enrollment;
    """).fetchone()

    print("=" * 70)
    print("THỐNG KÊ RÚT LUI TOÀN TRƯỜNG (BR5)")
    print(f"- Rút trước/đúng ngày 0: {summary[0]:,} / {summary[1]:,} ({summary[2]}%)")
    print(f"- Ngày rút trung vị: Ngày {int(summary[3])}")
    print("=" * 70)

    # 2. Lấy dữ liệu rút lui theo ngày cho 3 đợt tiêu biểu: BBB 2014J, CCC 2014B, AAA 2013J
    cohorts = [("BBB", "2014J", "#2563EB"), ("CCC", "2014B", "#DC2626"), ("AAA", "2013J", "#059669")]

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    for mod, pres, color in cohorts:
        df = con.sql(f"""
        WITH cohort_base AS (
            SELECT COUNT(*) AS total_students
            FROM fact_enrollment
            WHERE code_module = '{mod}' AND code_presentation = '{pres}'
        ),
        daily_withdrawn AS (
            SELECT
                date_unregistration AS unreg_day,
                COUNT(*) AS n_withdrawn
            FROM fact_enrollment
            WHERE code_module = '{mod}' AND code_presentation = '{pres}'
              AND is_withdrawn AND date_unregistration IS NOT NULL
            GROUP BY date_unregistration
        ),
        cumulative AS (
            SELECT
                d.unreg_day,
                SUM(d.n_withdrawn) OVER (ORDER BY d.unreg_day) AS cum_withdrawn,
                b.total_students,
                ROUND(100.0 * SUM(d.n_withdrawn) OVER (ORDER BY d.unreg_day) / b.total_students, 2) AS cum_withdrawn_pct
            FROM daily_withdrawn d
            CROSS JOIN cohort_base b
        )
        SELECT unreg_day, cum_withdrawn_pct FROM cumulative ORDER BY unreg_day;
        """).df()

        if not df.empty:
            label = f"{mod} {pres} (Cuối kỳ: {df['cum_withdrawn_pct'].iloc[-1]}%)"
            ax.step(df["unreg_day"], df["cum_withdrawn_pct"], where="post", color=color, lw=2.2, label=label)

    # Đánh dấu các mốc quan trọng
    ax.axvline(x=0, ls="--", color="#4B5563", lw=1.5, label="Ngày 0: Khai giảng")
    ax.axvline(x=27, ls=":", color="#D97706", lw=1.8, label="Ngày 27: Trung vị rút & Hạn học phí")

    ax.set_title("Đường cong Rút lui Tích lũy theo Thời gian (BR5 - Retention / Dropout Curve)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Số ngày so với ngày khai giảng (date_unregistration)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Tỷ lệ rút lui tích lũy (%)", fontsize=11, fontweight="bold")
    ax.set_xlim(-30, 240)
    ax.set_ylim(0, 50)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", framealpha=0.9, fontsize=10)

    out_path = FIG_DIR / "br5_retention_curve.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    print(f"✅ Đã lưu biểu đồ BR5: {out_path}")


if __name__ == "__main__":
    main()
