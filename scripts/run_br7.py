"""Trực quan hóa BR7: Benchmark tiến độ học tập cá nhân so với phân vị cả lớp theo tuần.

Vẽ dải phân vị Q25 - Median (Q50) - Q75 của đợt học AAA 2014J qua 20 tuần học,
và đường click tích lũy thực tế của sinh viên 32885.

Chạy:
    python scripts/run_br7.py
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
    p = WH / "fact_student_week"
    con.sql(f'CREATE VIEW fact_student_week AS SELECT * FROM read_parquet(\'{p.as_posix()}/*.parquet\')')

    mod, pres = "AAA", "2014J"
    sample_student_id = 32885

    # 1. Lấy phân vị cả lớp theo tuần
    df_cohort = con.sql(f"""
    SELECT
        week_no,
        COUNT(*) AS active_students,
        ROUND(quantile_cont(clicks_cum, 0.25), 0) AS p25_clicks,
        ROUND(quantile_cont(clicks_cum, 0.50), 0) AS median_clicks,
        ROUND(quantile_cont(clicks_cum, 0.75), 0) AS p75_clicks
    FROM fact_student_week
    WHERE code_module = '{mod}' AND code_presentation = '{pres}'
      AND is_enrolled AND week_no BETWEEN 0 AND 20
    GROUP BY week_no
    ORDER BY week_no;
    """).df()

    # 2. Lấy click tích lũy của sinh viên mẫu
    df_student = con.sql(f"""
    SELECT
        week_no,
        clicks_cum AS student_clicks_cum
    FROM fact_student_week
    WHERE code_module = '{mod}' AND code_presentation = '{pres}'
      AND id_student = {sample_student_id} AND week_no BETWEEN 0 AND 20
    ORDER BY week_no;
    """).df()

    print("=" * 80)
    print(f"THỐNG KÊ PHÂN VỊ LỚP {mod} {pres} (BR7, ĐẶC BIỆT TUẦN 10)")
    print("=" * 80)
    w10 = df_cohort[df_cohort["week_no"] == 10].iloc[0]
    print(f"- Tuần 10: {int(w10['active_students'])} SV; Q25={int(w10['p25_clicks'])}, Median={int(w10['median_clicks'])}, Q75={int(w10['p75_clicks'])}")
    print("=" * 80)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    # Vẽ dải phân vị Q25 - Q75 (vùng bóng mờ)
    ax.fill_between(df_cohort["week_no"], df_cohort["p25_clicks"], df_cohort["p75_clicks"],
                    color="#93C5FD", alpha=0.35, label="Khoảng tứ phân vị cả lớp (Q25 – Q75)")

    # Vẽ đường trung vị (Median Q50)
    ax.plot(df_cohort["week_no"], df_cohort["median_clicks"], "o-", color="#1D4ED8", lw=2.2, label="Trung vị cả lớp (Median Q50)")

    # Vẽ đường của sinh viên mẫu
    if not df_student.empty:
        merged = pd.merge(df_cohort, df_student, on="week_no", how="left")
        ax.plot(merged["week_no"], merged["student_clicks_cum"], "s--", color="#DC2626", lw=2.5,
                label=f"Sinh viên {sample_student_id}")

    # Đánh dấu tuần 10 (câu hỏi nghiệp vụ mẫu Q19)
    ax.axvline(x=10, ls=":", color="#4B5563", alpha=0.7)
    ax.annotate(f"Tuần 10\nMedian={int(w10['median_clicks'])}", (10, w10["median_clicks"]),
                textcoords="offset points", xytext=(15, -15),
                ha="left", fontsize=9, fontweight="bold", color="#1E3A8A")

    ax.set_title(f"Theo dõi Tiến độ Học tập Cá nhân so với Phân vị Cả lớp — {mod} {pres} (BR7)", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Tuần học (week_no)", fontsize=10, fontweight="bold")
    ax.set_ylabel("Lượt click tích lũy (clicks_cum)", fontsize=10, fontweight="bold")
    ax.set_xticks(df_cohort["week_no"].tolist())
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", framealpha=0.9, fontsize=10)

    out_path = FIG_DIR / "br7_cohort_benchmark.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    print(f"✅ Đã lưu biểu đồ BR7: {out_path}")


if __name__ == "__main__":
    main()
