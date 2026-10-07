"""Việc 1.3: Spark đọc 7 CSV của OULAD vào staging (Parquet).

- Kiểu dữ liệu đặt tay, không để Spark tự đoán.
- Cột ngày (date, date_submitted, date_registration...) là SỐ NGUYÊN: số ngày tính từ ngày khai giảng.
- Ô trống hoặc "?" -> NULL.
- Ghi đè mỗi lần chạy, nên chạy lại không bị nhân đôi.
- Ghi log số dòng ra data/staging/_row_counts.json và so với số chuẩn.

Chạy trong container:
    spark-submit --driver-memory 3g etl/01_staging.py
"""
import json
import sys
import time

from pyspark.sql import functions as F
from pyspark.sql.types import (IntegerType, StringType, StructField,
                               StructType, DoubleType)

from common import RAW_DIR, STAGING_DIR, get_spark

S, I, D = StringType(), IntegerType(), DoubleType()


def schema(*cols):
    return StructType([StructField(n, t, True) for n, t in cols])


# tên file -> (tên bảng staging, schema, số dòng chuẩn)
TABLES = {
    "courses.csv": ("stg_courses", schema(
        ("code_module", S), ("code_presentation", S), ("module_presentation_length", I)), 22),
    "assessments.csv": ("stg_assessments", schema(
        ("code_module", S), ("code_presentation", S), ("id_assessment", I),
        ("assessment_type", S), ("date", I), ("weight", D)), 206),
    "vle.csv": ("stg_vle", schema(
        ("id_site", I), ("code_module", S), ("code_presentation", S),
        ("activity_type", S), ("week_from", I), ("week_to", I)), 6364),
    "studentInfo.csv": ("stg_student_info", schema(
        ("code_module", S), ("code_presentation", S), ("id_student", I),
        ("gender", S), ("region", S), ("highest_education", S), ("imd_band", S),
        ("age_band", S), ("num_of_prev_attempts", I), ("studied_credits", I),
        ("disability", S), ("final_result", S)), 32593),
    "studentRegistration.csv": ("stg_student_registration", schema(
        ("code_module", S), ("code_presentation", S), ("id_student", I),
        ("date_registration", I), ("date_unregistration", I)), 32593),
    "studentAssessment.csv": ("stg_student_assessment", schema(
        ("id_assessment", I), ("id_student", I), ("date_submitted", I),
        ("is_banked", I), ("score", D)), 173912),
    "studentVle.csv": ("stg_student_vle", schema(
        ("code_module", S), ("code_presentation", S), ("id_student", I),
        ("id_site", I), ("date", I), ("sum_click", I)), 10655280),
}


def read_csv(spark, path, sch):
    """Đọc mọi cột thành chữ, đổi ""/"?" thành NULL, rồi mới ép kiểu.
    OULAD dùng lẫn cả ô rỗng và "?" cho giá trị thiếu, nên không dựa vào option nullValue."""
    raw_sch = StructType([StructField(f.name, StringType(), True) for f in sch.fields])
    raw = (spark.read.option("header", True).option("mode", "FAILFAST")
           .schema(raw_sch).csv(str(path)))
    cleaned = []
    for f in sch.fields:
        c = F.trim(F.col(f.name))
        c = F.when(c.isNull() | (c == "") | (c == "?"), None).otherwise(c)
        cleaned.append(c.alias(f.name))
    df = raw.select(cleaned).cache()

    # Ép kiểu số. Giá trị có nhưng ép hỏng (vd "12a") thì dừng, không để lặng lẽ thành NULL.
    typed = [F.col(f.name).cast(f.dataType).alias(f.name) for f in sch.fields]
    bad_checks = [F.sum((F.col(f.name).isNotNull() & F.col(f.name).cast(f.dataType).isNull())
                        .cast("int")).alias(f.name)
                  for f in sch.fields if not isinstance(f.dataType, StringType)]
    if bad_checks:
        bad = {k: v for k, v in df.select(bad_checks).first().asDict().items() if v}
        if bad:
            raise ValueError(f"{path.name}: có giá trị không ép được sang số: {bad}")
    return df.select(typed)


def main():
    spark = get_spark("oulad-01-staging")
    spark.sparkContext.setLogLevel("WARN")
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    missing = [f for f in TABLES if not (RAW_DIR / f).exists()]
    if missing:
        sys.exit(f"Thiếu file trong {RAW_DIR}: {missing}")

    report, all_ok = {}, True
    for fname, (tname, sch, expected) in TABLES.items():
        t0 = time.time()
        df = read_csv(spark, RAW_DIR / fname, sch)
        out = STAGING_DIR / tname
        df.write.mode("overwrite").parquet(str(out))
        n = spark.read.parquet(str(out)).count()
        ok = n == expected
        all_ok &= ok
        nulls = (spark.read.parquet(str(out))
                 .select([F.sum(F.col(c).isNull().cast("int")).alias(c) for c in df.columns])
                 .first().asDict())
        report[tname] = {"source": fname, "rows": n, "expected": expected, "ok": ok,
                         "seconds": round(time.time() - t0, 1),
                         "nulls": {k: v for k, v in nulls.items() if v}}
        print(f"{'OK ' if ok else 'SAI'} {tname:28s} {n:>12,} dòng (chuẩn {expected:,})  "
              f"{report[tname]['seconds']}s  null={report[tname]['nulls']}")

    (STAGING_DIR / "_row_counts.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    spark.stop()
    if not all_ok:
        sys.exit("Có bảng lệch số dòng, xem log phía trên.")
    print("Xong 1.3: cả 7 bảng khớp số dòng.")


if __name__ == "__main__":
    main()
