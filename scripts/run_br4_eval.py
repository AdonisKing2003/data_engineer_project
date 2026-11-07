"""Trực quan hóa và Đánh giá Yêu cầu 2.9 (Evaluation): Hệ thống Cảnh báo Sớm BR4.

Tính toán và vẽ biểu đồ Precision, Recall, F1-Score, Base Rate qua các tuần (đặc biệt tuần 4, 8, 12).
Chạy:
    python scripts/run_br4_eval.py
    python scripts/run_br4_eval.py --plot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import duckdb
import pandas as pd
import matplotlib.pyplot as plt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Segoe UI", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
FIG_DIR = ROOT / "docs" / "figures"


def get_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for t in [
        "dim_presentation", "dim_student", "dim_assessment", "dim_vle_site", "dim_week",
        "fact_enrollment", "fact_vle_daily", "fact_submission", "fact_student_week"
    ]:
        p = WH / t
        if not p.is_dir():
            raise FileNotFoundError(f"Không tìm thấy thư mục kho dữ liệu: {p}")
        con.sql(f'CREATE VIEW "{t}" AS SELECT * FROM read_parquet(\'{p.as_posix()}/*.parquet\')')
    return con


def evaluate_weeks(con: duckdb.DuckDBPyConnection, weeks: list[int]) -> pd.DataFrame:
    rows = []
    for w in weeks:
        df = con.sql(f"""
        WITH cohort AS (
            SELECT
                w.id_student, w.code_module, w.code_presentation,
                w.clicks_cum, w.clicks_week, w.avg_score_cum, w.n_tma_missed_cum,
                p.clicks_week AS clicks_prev_week
            FROM fact_student_week w
            LEFT JOIN fact_student_week p
              ON p.id_student = w.id_student
             AND p.code_module = w.code_module
             AND p.code_presentation = w.code_presentation
             AND p.week_no = w.week_no - 1
            WHERE w.week_no = {w} AND w.is_enrolled
        ),
        p25 AS (
            SELECT code_module, code_presentation, quantile_cont(clicks_cum, 0.25) AS p25_clicks
            FROM cohort
            GROUP BY code_module, code_presentation
        ),
        scored AS (
            SELECT
                c.id_student, c.code_module, c.code_presentation,
                (CAST(c.clicks_cum < p.p25_clicks AS INT) +
                 CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT) +
                 CAST(c.n_tma_missed_cum > 0 AS INT) +
                 CAST(COALESCE(c.avg_score_cum < 40, false) AS INT)) >= 2 AS is_at_risk
            FROM cohort c
            JOIN p25 p USING (code_module, code_presentation)
        ),
        labeled AS (
            SELECT
                s.is_at_risk,
                (e.final_result IN ('Fail', 'Withdrawn')) AS actual_bad_result
            FROM scored s
            JOIN fact_enrollment e USING (id_student, code_module, code_presentation)
        )
        SELECT
            {w} AS week_no,
            COUNT(*) AS total_active,
            COUNTIF(is_at_risk) AS n_flagged,
            COUNTIF(is_at_risk AND actual_bad_result) AS n_true_positives,
            COUNTIF(actual_bad_result) AS total_actual_bad,
            ROUND(100.0 * COUNTIF(is_at_risk AND actual_bad_result) / NULLIF(COUNTIF(is_at_risk), 0), 1) AS precision_pct,
            ROUND(100.0 * COUNTIF(is_at_risk AND actual_bad_result) / NULLIF(COUNTIF(actual_bad_result), 0), 1) AS recall_pct,
            ROUND(100.0 * COUNTIF(actual_bad_result) / COUNT(*), 1) AS base_rate_pct
        FROM labeled;
        """).df()
        rows.append(df)
    result = pd.concat(rows, ignore_index=True)
    # Tính F1-score
    prec = result["precision_pct"] / 100.0
    rec = result["recall_pct"] / 100.0
    result["f1_score_pct"] = (2 * prec * rec / (prec + rec) * 100).round(1)
    return result


def plot_evaluation(df_all: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, dpi=150)
    plt.subplots_adjust(hspace=0.15)

    # Subplot 1: Precision, Recall, Base Rate
    ax1.plot(df_all["week_no"], df_all["precision_pct"], "o-", color="#2563EB", lw=2.2, label="Độ chính xác (Precision)")
    ax1.plot(df_all["week_no"], df_all["recall_pct"], "s-", color="#10B981", lw=2.2, label="Độ bao phủ (Recall / Coverage)")
    ax1.plot(df_all["week_no"], df_all["base_rate_pct"], "--", color="#9CA3AF", lw=1.8, label="Tỷ lệ nền (Base Rate Fail/Withdrawn)")

    # Đánh dấu các mốc vàng: Tuần 4, 8, 12
    for w in [4, 8, 12]:
        val = df_all.loc[df_all["week_no"] == w, "precision_pct"].values[0]
        ax1.axvline(x=w, ls=":", color="#EF4444", alpha=0.6)
        ax1.annotate(f"Tuần {w}\nP={val}%", (w, val), textcoords="offset points", xytext=(0, 10),
                     ha="center", fontsize=8.5, fontweight="bold", color="#1E3A8A")

    ax1.set_title("Đánh giá Hệ thống Cảnh báo Sớm BR4 qua các Tuần học (Yêu cầu 2.9 - Effectiveness)", fontsize=12, fontweight="bold", pad=12)
    ax1.set_ylabel("Tỷ lệ (%)", fontsize=10, fontweight="bold")
    ax1.set_ylim(0, 100)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="center right", framealpha=0.9)

    # Subplot 2: Quy mô sinh viên
    ax2.bar(df_all["week_no"] - 0.2, df_all["n_flagged"], width=0.4, color="#F59E0B", label="Số SV được cảnh báo (Flagged)")
    ax2.bar(df_all["week_no"] + 0.2, df_all["n_true_positives"], width=0.4, color="#3B82F6", label="SV cảnh báo đúng (True Positives)")
    ax2.set_xlabel("Tuần học (Week No)", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Số lượng sinh viên", fontsize=10, fontweight="bold")
    ax2.set_xticks(df_all["week_no"].tolist())
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"✅ Đã lưu biểu đồ đánh giá: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plot", action="store_true", default=True, help="Vẽ và lưu biểu đồ đánh giá (mặc định: True)")
    args = parser.parse_args()

    con = get_connection()

    # 1. Đo lường chi tiết 3 mốc chuẩn của Yêu cầu 2.9: Tuần 4, Tuần 8, Tuần 12
    key_weeks = [4, 8, 12]
    df_key = evaluate_weeks(con, key_weeks)
    print("\n" + "=" * 80)
    print("BẢNG ĐỐI SOÁT HIỆU QUẢ CẢNH BÁO SỚM BR4 (YÊU CẦU 2.9: TUẦN 4, 8, 12)")
    print("=" * 80)
    print(df_key[[
        "week_no", "total_active", "n_flagged", "n_true_positives",
        "precision_pct", "recall_pct", "base_rate_pct", "f1_score_pct"
    ]].rename(columns={
        "week_no": "Tuần",
        "total_active": "SV còn học",
        "n_flagged": "SV cảnh báo",
        "n_true_positives": "Cảnh báo đúng",
        "precision_pct": "Precision (%)",
        "recall_pct": "Recall (%)",
        "base_rate_pct": "Tỷ lệ nền (%)",
        "f1_score_pct": "F1-Score (%)"
    }).to_string(index=False))
    print("=" * 80)

    # 2. Đo chuỗi các tuần từ 2 đến 16 để vẽ đường cong liên tục
    all_weeks = list(range(2, 17))
    df_all = evaluate_weeks(con, all_weeks)

    if args.plot:
        out_fig = FIG_DIR / "br4_evaluation.png"
        plot_evaluation(df_all, out_fig)


if __name__ == "__main__":
    main()
