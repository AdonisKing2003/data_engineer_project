"""Việc 1.4: làm sạch + 5 dimension + fact_enrollment.

Tên bảng, tên cột, định nghĩa cờ theo đúng docs/contract.md. Các bước làm sạch theo sheet Task1:
- Không xóa dòng, không sửa giá trị gốc; chỗ có vấn đề thì thêm cờ.
- imd_band: '10-20' -> '10-20%', NULL -> 'Unknown' (cờ imd_unknown).
- 11 bài Exam thiếu ngày: deadline = ngày cuối đợt (cờ deadline_imputed), giữ cột gốc ở deadline_raw.
- Tuần = floor(date / 7).

Các số tổng hợp (total_clicks, n_submissions, never_clicked...) tính thẳng từ staging,
nên bước này không phụ thuộc 03_facts.py.

Chạy trong container:
    cd etl && spark-submit --driver-memory 3g 02_clean_dims.py
"""
import sys

from pyspark.sql import Window
from pyspark.sql import functions as F

from common import (WAREHOUSE_DIR, get_spark, mark_exists, read_staging,
                    save_report, write_table)

PRES = ["code_module", "code_presentation"]
ENROL = ["id_student"] + PRES
WEEK_MIN, WEEK_MAX = -4, 38  # click sớm nhất ngày −25 (tuần −4); đợt dài nhất 269 ngày (tuần 38)


def build_dim_presentation(courses, asm, sa):
    exam_rows = sa.join(asm.filter(F.col("assessment_type") == "Exam"), "id_assessment")
    weighted_tma = asm.filter((F.col("assessment_type") == "TMA") & (F.col("weight") > 0))
    df = courses.select(
        *PRES,
        F.substring("code_presentation", 1, 4).cast("int").alias("year"),
        F.substring("code_presentation", 5, 1).alias("semester"),
        F.col("module_presentation_length").alias("length_days"),
        (F.floor((F.col("module_presentation_length") - 1) / 7) + 1).cast("int").alias("n_weeks"),
    )
    df = mark_exists(df, exam_rows, PRES, "has_exam_result")
    return mark_exists(df, weighted_tma, PRES, "has_weighted_tma")


def build_dim_student(info):
    # gender, region, highest_education, disability, imd_band không đổi giữa các đợt (đã kiểm),
    # nên distinct ra đúng một dòng mỗi SV. age_band thì có đổi, nên để ở fact_enrollment.
    imd = F.col("imd_band")
    return (info.select(
        "id_student", "gender", "region", "highest_education",
        F.when(imd.isNull(), "Unknown").when(imd == "10-20", "10-20%").otherwise(imd).alias("imd_band"),
        "disability",
        imd.isNull().alias("imd_unknown"),
    ).distinct())


def build_dim_assessment(asm, courses, sa):
    by_deadline = Window.partitionBy(*PRES).orderBy("deadline", "id_assessment")
    df = (asm.join(courses, PRES)
          .withColumn("deadline", F.coalesce("date", "module_presentation_length"))
          .select(
              "id_assessment", *PRES, "assessment_type",
              F.col("date").alias("deadline_raw"),
              "deadline", "weight",
              F.row_number().over(by_deadline).alias("assessment_order"),
              F.col("date").isNull().alias("deadline_imputed"),
              (F.col("weight") == 0).alias("zero_weight"),
          ))
    # TMA đầu tiên có trọng số: lọc weight > 0 TRƯỚC rồi mới lấy hạn sớm nhất (BBB 2014J -> 15021)
    first_tma = (df.filter((F.col("assessment_type") == "TMA") & (F.col("weight") > 0))
                 .withColumn("rn", F.row_number().over(by_deadline))
                 .filter(F.col("rn") == 1))
    df = mark_exists(df, first_tma, ["id_assessment"], "is_first_weighted_tma")
    return mark_exists(df, sa, ["id_assessment"], "has_submissions")


def build_dim_vle_site(vle, svle):
    df = vle.withColumn("has_planned_week", F.col("week_from").isNotNull())
    df = mark_exists(df, svle, ["id_site"], "clicked")
    return df.withColumn("never_clicked", ~F.col("clicked")).drop("clicked")


def build_dim_week(spark):
    return (spark.range(WEEK_MIN, WEEK_MAX + 1)
            .select(F.col("id").cast("int").alias("week_no"))
            .select("week_no",
                    (F.col("week_no") * 7).alias("day_from"),
                    (F.col("week_no") * 7 + 6).alias("day_to"),
                    (F.col("week_no") < 0).alias("is_pre_start")))


def build_fact_enrollment(info, reg, svle, sa, asm):
    clicks = svle.groupBy(*ENROL).agg(
        F.sum("sum_click").alias("total_clicks"),
        F.countDistinct("date").alias("active_days"))
    subs = (sa.join(asm.select("id_assessment", *PRES), "id_assessment")
            .groupBy(*ENROL).agg(F.count("*").alias("n_submissions")))
    unreg = F.col("date_unregistration")
    df = (info.select(*ENROL, "final_result", "age_band", "studied_credits", "num_of_prev_attempts")
          .join(reg, ENROL)
          .join(clicks.withColumn("has_vle", F.lit(True)), ENROL, "left")
          .join(subs, ENROL, "left"))
    return df.select(
        *ENROL, "final_result", "age_band", "studied_credits", "num_of_prev_attempts",
        "date_registration", "date_unregistration",
        F.coalesce("total_clicks", F.lit(0)).alias("total_clicks"),
        F.coalesce("active_days", F.lit(0)).alias("active_days"),
        F.coalesce("n_submissions", F.lit(0)).alias("n_submissions"),
        (F.col("final_result") == "Withdrawn").alias("is_withdrawn"),
        F.coalesce(unreg <= 0, F.lit(False)).alias("withdrawn_before_start"),
        F.col("has_vle").isNull().alias("no_vle_activity"),
        F.col("date_registration").isNull().alias("reg_date_missing"),
        ((F.col("final_result") == "Withdrawn") != unreg.isNotNull()).alias("result_inconsistent"),
        (F.col("num_of_prev_attempts") > 0).alias("is_repeat"),
    )


def main():
    spark = get_spark("oulad-02-clean-dims")
    spark.sparkContext.setLogLevel("WARN")
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)

    courses = read_staging(spark, "stg_courses")
    asm = read_staging(spark, "stg_assessments")
    vle = read_staging(spark, "stg_vle")
    info = read_staging(spark, "stg_student_info")
    reg = read_staging(spark, "stg_student_registration")
    sa = read_staging(spark, "stg_student_assessment")
    svle = read_staging(spark, "stg_student_vle")

    report = {
        "dim_presentation": write_table(spark, build_dim_presentation(courses, asm, sa), "dim_presentation", 22),
        "dim_student": write_table(spark, build_dim_student(info), "dim_student", 28785),
        "dim_assessment": write_table(spark, build_dim_assessment(asm, courses, sa), "dim_assessment", 206),
        "dim_vle_site": write_table(spark, build_dim_vle_site(vle, svle), "dim_vle_site", 6364),
        "dim_week": write_table(spark, build_dim_week(spark), "dim_week", WEEK_MAX - WEEK_MIN + 1),
        "fact_enrollment": write_table(spark, build_fact_enrollment(info, reg, svle, sa, asm),
                                       "fact_enrollment", 32593),
    }
    ok = save_report(report, "02_clean_dims")
    spark.stop()
    if not ok:
        sys.exit("Có bảng lệch số dòng, xem log phía trên.")
    print("Xong 1.4: 5 dimension + fact_enrollment khớp số dòng. Kiểm cờ: pytest -q tests/test_warehouse.py")


if __name__ == "__main__":
    main()
