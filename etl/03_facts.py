"""Việc 1.5: fact_vle_daily + fact_submission ra Parquet.

Tên bảng, tên cột, định nghĩa cờ theo đúng docs/contract.md.
- fact_vle_daily: gộp các dòng click trùng (SV, đợt, học liệu, ngày) bằng cách cộng sum_click.
  10.655.280 dòng gốc -> 8.459.320 dòng, tổng click giữ nguyên.
- fact_submission: is_late chỉ tính TMA và không tính bài chuyển điểm; days_late NULL nếu chuyển điểm.
Ghi đè mỗi lần chạy, nên chạy lại không bị nhân đôi.

Cần chạy 02_clean_dims.py trước (dùng deadline đã điền của dim_assessment).

Chạy trong container:
    cd etl && spark-submit --driver-memory 3g 03_facts.py
"""
import sys

from pyspark.sql import functions as F

from common import (get_spark, read_staging, read_wh, save_report, week_of,
                    write_table)

VLE_KEYS = ["id_student", "code_module", "code_presentation", "id_site", "date"]


def build_fact_vle_daily(svle):
    return (svle.groupBy(*VLE_KEYS)
            .agg(F.sum("sum_click").cast("int").alias("sum_click"),
                 F.count("*").cast("int").alias("n_records"))
            .select(*VLE_KEYS[:4], "date", week_of("date").alias("week_no"),
                    "sum_click", "n_records", (F.col("date") < 0).alias("is_pre_start")))


def build_fact_submission(sa, dim_assessment, dim_presentation):
    asm = (dim_assessment.select("id_assessment", "code_module", "code_presentation",
                                 "assessment_type", "deadline")
           .join(dim_presentation.select("code_module", "code_presentation", "length_days"),
                 ["code_module", "code_presentation"]))
    banked = F.col("is_banked") == 1
    late = (F.col("assessment_type") == "TMA") & ~banked & (F.col("date_submitted") > F.col("deadline"))
    return (sa.join(asm, "id_assessment")
            .select(
                "id_student", "id_assessment", "code_module", "code_presentation",
                "date_submitted", week_of("date_submitted").alias("week_no"),
                F.col("score").cast("int").alias("score"),  # mọi điểm đều là số nguyên (đã kiểm)
                F.when(~banked, F.col("date_submitted") - F.col("deadline")).alias("days_late"),
                banked.alias("is_banked"),
                F.coalesce(late, F.lit(False)).alias("is_late"),
                F.col("score").isNull().alias("score_missing"),
                (F.col("date_submitted") > F.col("length_days")).alias("is_beyond_course"),
                (F.col("score") >= 40).alias("is_pass_score"),  # NULL khi thiếu điểm
            ))


def main():
    spark = get_spark("oulad-03-facts")
    spark.sparkContext.setLogLevel("WARN")

    svle = read_staging(spark, "stg_student_vle")
    sa = read_staging(spark, "stg_student_assessment")
    dim_assessment = read_wh(spark, "dim_assessment")
    dim_presentation = read_wh(spark, "dim_presentation")

    report = {
        "fact_vle_daily": write_table(spark, build_fact_vle_daily(svle), "fact_vle_daily", 8459320),
        "fact_submission": write_table(spark, build_fact_submission(sa, dim_assessment, dim_presentation),
                                       "fact_submission", 173912),
    }
    ok = save_report(report, "03_facts")
    spark.stop()
    if not ok:
        sys.exit("Có bảng lệch số dòng, xem log phía trên.")
    print("Xong 1.5: fact_vle_daily + fact_submission khớp số dòng. Kiểm cờ: pytest -q tests/test_warehouse.py")


if __name__ == "__main__":
    main()
