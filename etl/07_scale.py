"""Việc 1.12: sinh kho nhân bản N× (mặc định 5×) cho benchmark (việc 3.9 của TV3).

- Mỗi SV được chép thành N bản: bản i có id_student = id_student + i × 10.000.000, kéo theo toàn bộ
  lượt đăng ký, click, bài nộp và các tuần của SV đó. Bản 0 giữ nguyên mã gốc, nên kho 1× nằm trong kho N×.
- Bảng không gắn với SV (dim_presentation, dim_assessment, dim_vle_site, dim_week) giữ nguyên:
  thêm SV nhưng vẫn từng ấy môn, bài, học liệu.
- Chép nguyên vẹn nên phân bố click giữ đúng; mọi tỷ lệ trên kho N× bằng kho 1×.
- Đọc từ data/warehouse (kho 1×), ghi ra data/warehouse_<N>x. Ghi đè, chạy lại không nhân đôi.

Kho 1× chính là kho hiện có (BigQuery dataset oulad, PostgreSQL schema public), không cần sinh lại.

Chạy trong container (sau make all):
    cd etl && spark-submit --driver-memory 3g 07_scale.py            # 5×
    cd etl && spark-submit --driver-memory 3g 07_scale.py --factor 2
Rồi nạp: python 04_load_bq.py --scale 5 ; python 05_load_pg.py --scale 5
"""
import argparse
import sys

from pyspark.sql import functions as F

from common import (ROOT, get_spark, give_back_to_owner, read_wh, save_report,
                    scaled_dir, write_table)

OFFSET = 10_000_000  # lớn hơn id_student lớn nhất (2.716.795); bản thứ 214 mới chạm giới hạn int32
STUDENT_TABLES = ["dim_student", "fact_enrollment", "fact_vle_daily", "fact_submission", "fact_student_week"]
STATIC_TABLES = ["dim_presentation", "dim_assessment", "dim_vle_site", "dim_week"]


def replicate(spark, df, factor):
    copies = spark.range(factor).select(F.col("id").cast("int").alias("copy_no"))
    cols = [(F.col("id_student") + F.col("copy_no") * OFFSET).cast("int").alias("id_student")
            if c == "id_student" else F.col(c) for c in df.columns]
    return df.crossJoin(F.broadcast(copies)).select(*cols)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor", type=int, default=5)
    factor = ap.parse_args().factor
    if not 2 <= factor <= 200:
        sys.exit("--factor phải từ 2 đến 200")
    out_dir = scaled_dir(factor)
    out_dir.mkdir(parents=True, exist_ok=True)

    spark = get_spark(f"oulad-07-scale-{factor}x")
    spark.sparkContext.setLogLevel("WARN")
    report = {}
    for name in STATIC_TABLES + STUDENT_TABLES:
        src = read_wh(spark, name)
        n_src = src.count()
        if name in STUDENT_TABLES:
            report[name] = write_table(spark, replicate(spark, src, factor), name, n_src * factor, out_dir)
        else:
            report[name] = write_table(spark, src, name, n_src, out_dir)
    ok = save_report(report, "07_scale", out_dir)
    spark.stop()
    give_back_to_owner(out_dir)
    if not ok:
        sys.exit(f"Kho {factor}× lệch số dòng, xem log phía trên.")
    print(f"Xong 1.12: kho {factor}× ở {out_dir.relative_to(ROOT)}, bảng có SV gấp đúng {factor} lần.")


if __name__ == "__main__":
    main()
