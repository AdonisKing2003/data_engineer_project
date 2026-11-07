"""Trực quan hóa BR1: Tỷ lệ nộp bài, tỷ lệ nộp trễ và phân phối điểm số từng bài kiểm tra.

Vẽ biểu đồ cột tỷ lệ nộp và trễ hạn (TMA) của đợt học BBB 2014J.
Chạy:
    python scripts/run_br1.py
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
    for t in ["dim_assessment", "fact_enrollment", "fact_submission"]:
        p = WH / t
        con.sql(f'CREATE VIEW "{t}" AS SELECT * FROM read_parquet(\'{p.as_posix()}/*.parquet\')')

    mod, pres = "BBB", "2014J"

    df = con.sql(f"""
    WITH assessment_cohort AS (
        SELECT
            a.id_assessment,
            a.assessment_type,
            a.assessment_order,
            a.deadline,
            COUNT(DISTINCT e.id_student) AS active_students
        FROM dim_assessment a
        JOIN fact_enrollment e
          ON e.code_module = a.code_module
         AND e.code_presentation = a.code_presentation
         AND (e.date_unregistration IS NULL OR e.date_unregistration > a.deadline)
        WHERE a.code_module = '{mod}' AND a.code_presentation = '{pres}'
        GROUP BY a.id_assessment, a.assessment_type, a.assessment_order, a.deadline
    ),
    sub_stats AS (
        SELECT
            s.id_assessment,
            COUNT(DISTINCT CASE WHEN NOT s.is_banked THEN s.id_student END) AS submitted_regular,
            COUNTIF(s.is_late) AS late_submissions,
            ROUND(MEDIAN(s.score), 1) AS median_score
        FROM fact_submission s
        JOIN dim_assessment a USING (id_assessment)
        WHERE a.code_module = '{mod}' AND a.code_presentation = '{pres}'
        GROUP BY s.id_assessment
    )
    SELECT
        c.assessment_type || ' #' || c.assessment_order || ' (Hạn ' || c.deadline || ')' AS assessment_label,
        c.assessment_type,
        c.active_students,
        s.submitted_regular,
        ROUND(100.0 * s.submitted_regular / c.active_students, 1) AS submission_rate_pct,
        ROUND(100.0 * s.late_submissions / NULLIF(s.submitted_regular, 0), 1) AS late_rate_pct,
        s.median_score
    FROM assessment_cohort c
    LEFT JOIN sub_stats s USING (id_assessment)
    ORDER BY c.assessment_type DESC, c.assessment_order ASC;
    """).df()

    print("=" * 80)
    print(f"THỐNG KÊ NỘP BÀI VÀ TRỄ HẠN ĐỢT {mod} {pres} (BR1)")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)

    x = range(len(df))
    width = 0.38

    bars1 = ax.bar([i - width/2 for i in x], df["submission_rate_pct"], width=width, color="#2563EB", label="Tỷ lệ nộp bài (%)")
    bars2 = ax.bar([i + width/2 for i in x], df["late_rate_pct"].fillna(0), width=width, color="#EF4444", label="Tỷ lệ trễ hạn TMA (%)")

    # Hiển thị số trên đỉnh cột
    for bar in bars1:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 1, f"{yval:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1E3A8A")
    for bar in bars2:
        yval = bar.get_height()
        if yval > 0:
            ax.text(bar.get_x() + bar.get_width()/2, yval + 1, f"{yval:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#B91C1C")

    ax.set_title(f"Tiến độ Nộp bài & Tỷ lệ Nộp trễ theo từng Bài kiểm tra — {mod} {pres} (BR1)", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Tỷ lệ (%)", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 115)
    ax.set_xticks(x)
    ax.set_xticklabels(df["assessment_label"], rotation=15, ha="right", fontsize=9.5)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.legend(loc="upper right", framealpha=0.9)

    out_path = FIG_DIR / "br1_submission_rates.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    print(f"✅ Đã lưu biểu đồ BR1: {out_path}")


if __name__ == "__main__":
    main()
