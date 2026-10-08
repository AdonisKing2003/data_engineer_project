"""Việc 1.8: fact_student_week — ảnh chụp SV × đợt × tuần, theo đúng docs/contract.md.

- Grain: mỗi lượt đăng ký có đủ các tuần từ −4 đến n_weeks − 1, kể cả sau khi rút
  (1.342.949 dòng). Lọc người còn học bằng is_enrolled.
- As-of: cột của tuần w chỉ dùng dữ liệu có ngày <= 7w + 6 (ngày cuối tuần w).
- Không có final_result: nhãn chỉ dùng để chấm BR4, nằm ở fact_enrollment.

Cần chạy 02_clean_dims.py và 03_facts.py trước.

Chạy trong container:
    cd etl && spark-submit --driver-memory 3g 06_student_week.py
"""
import sys

from pyspark.sql import Window
from pyspark.sql import functions as F

from common import get_spark, read_wh, save_report, week_of, write_table

PRES = ["code_module", "code_presentation"]
ENROL = ["id_student"] + PRES
KEY = ENROL + ["week_no"]
WEEK_MIN = -4


def build_fact_student_week(enrollment, presentation, vle_daily, submission, assessment):
    end_of_week = F.col("week_no") * 7 + 6

    # Khung: mọi lượt đăng ký × mọi tuần của đợt
    grid = (enrollment.select(*ENROL, "date_unregistration")
            .join(presentation.select(*PRES, "n_weeks"), PRES)
            .withColumn("week_no", F.explode(F.sequence(F.lit(WEEK_MIN), F.col("n_weeks") - 1)))
            .drop("n_weeks"))

    clicks = vle_daily.groupBy(*KEY).agg(
        F.sum("sum_click").alias("clicks_week"),
        F.countDistinct("date").alias("active_days_week"),
        F.countDistinct("id_site").alias("sites_week"))

    # Bài nộp theo tuần nộp; cộng dồn ở dưới. date_submitted <= 7w + 6  <=>  tuần nộp <= w
    subs = submission.groupBy(*KEY).agg(
        F.count("*").alias("n_sub"),
        F.sum(F.col("is_late").cast("int")).alias("n_late"),
        F.sum("score").alias("score_sum"),
        F.count("score").alias("score_n"))

    # TMA có trọng số bị bỏ ở tuần w: hạn <= 7w + 6 và chưa nộp đến 7w + 6 (bài chuyển điểm tính là đã nộp).
    # Tức là w nằm trong [tuần của hạn, tuần nộp − 1], hoặc từ tuần của hạn trở đi nếu không nộp.
    tma = (assessment.filter((F.col("assessment_type") == "TMA") & (F.col("weight") > 0))
           .select("id_assessment", *PRES, week_of("deadline").alias("due_week")))
    pairs = (enrollment.select(*ENROL).join(tma, PRES)
             .join(submission.select("id_student", "id_assessment", F.col("week_no").alias("sub_week")),
                   ["id_student", "id_assessment"], "left"))
    missed = (grid.select(*KEY).join(pairs, ENROL)
              .filter((F.col("week_no") >= F.col("due_week"))
                      & (F.col("sub_week").isNull() | (F.col("week_no") < F.col("sub_week"))))
              .groupBy(*KEY).agg(F.count("*").alias("n_tma_missed_cum")))

    zero = ["clicks_week", "active_days_week", "sites_week", "n_sub", "n_late",
            "score_sum", "score_n", "n_tma_missed_cum"]
    df = (grid.join(clicks, KEY, "left").join(subs, KEY, "left").join(missed, KEY, "left")
          .fillna(0, subset=zero))

    upto = Window.partitionBy(*ENROL).orderBy("week_no").rowsBetween(Window.unboundedPreceding, 0)
    score_n_cum = F.sum("score_n").over(upto)
    unreg = F.col("date_unregistration")
    return df.select(
        *KEY,
        "clicks_week",
        F.sum("clicks_week").over(upto).alias("clicks_cum"),
        "active_days_week", "sites_week",
        F.sum("n_sub").over(upto).alias("n_submitted_cum"),
        F.sum("n_late").over(upto).alias("n_late_cum"),
        F.when(score_n_cum > 0, F.sum("score_sum").over(upto) / score_n_cum).alias("avg_score_cum"),
        "n_tma_missed_cum",
        (F.col("week_no") < 0).alias("is_pre_start"),
        (F.col("clicks_week") == 0).alias("is_week_inactive"),
        (unreg.isNull() | (unreg > end_of_week)).alias("is_enrolled"),
    )


def main():
    spark = get_spark("oulad-06-student-week")
    spark.sparkContext.setLogLevel("WARN")

    df = build_fact_student_week(
        read_wh(spark, "fact_enrollment"), read_wh(spark, "dim_presentation"),
        read_wh(spark, "fact_vle_daily"), read_wh(spark, "fact_submission"),
        read_wh(spark, "dim_assessment"))
    report = {"fact_student_week": write_table(spark, df, "fact_student_week", 1342949)}
    ok = save_report(report, "06_student_week")
    spark.stop()
    if not ok:
        sys.exit("fact_student_week lệch số dòng, xem log phía trên.")
    print("Xong 1.8: fact_student_week khớp số dòng. Kiểm: pytest -q tests/test_student_week.py")


if __name__ == "__main__":
    main()
