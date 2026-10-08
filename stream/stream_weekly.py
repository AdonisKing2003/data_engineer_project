"""Việc 1.9, bước 3: Spark Structured Streaming cộng dồn click theo SV × đợt × tuần.

- Nguồn: thư mục data/stream/input/ (file source, readStream), mỗi file là click của một ngày.
  Mỗi micro-batch đọc tối đa 7 file (khoảng một tuần dữ liệu).
- Trạng thái: tổng clicks_week của từng (SV, đợt, tuần), giữ trong state store của Spark.
- Đích: outputMode "update". Mỗi micro-batch chỉ ghi các dòng vừa thay đổi kèm batch_id vào
  data/stream/out/updates (Parquet). Giá trị mới nhất của một dòng = dòng có batch_id lớn nhất.
  clicks_cum được cộng dồn từ clicks_week ở bước so sánh (compare.py).
- Mỗi lần chạy xóa input/, checkpoint/, out/ để bắt đầu lại từ đầu.

Chạy trong container, chọn một trong hai cách:
    spark-submit stream/stream_weekly.py --replay        # tự phát lại trong cùng tiến trình
    spark-submit stream/stream_weekly.py                 # terminal 1: chạy trước
    python stream/replay.py --delay 1                    # terminal 2: phát lại để xem từng batch
Sau đó: python stream/compare.py
"""
import argparse
import json
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
sys.path.insert(0, str(ROOT / "stream"))

from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import IntegerType, StringType, StructField, StructType  # noqa: E402

from common import get_spark, week_of  # noqa: E402
from replay import DONE, INPUT_DIR, replay  # noqa: E402

STREAM_DIR = ROOT / "data" / "stream"
CHECKPOINT = STREAM_DIR / "checkpoint"
UPDATES = STREAM_DIR / "out" / "updates"
KEY = ["id_student", "code_module", "code_presentation", "week_no"]

SCHEMA = StructType([
    StructField("code_module", StringType()), StructField("code_presentation", StringType()),
    StructField("id_student", IntegerType()), StructField("id_site", IntegerType()),
    StructField("date", IntegerType()), StructField("sum_click", IntegerType()),
])


def save_batch(batch_df, batch_id):
    batch_df.persist()
    stats = batch_df.agg(F.count("*").alias("n"), F.max("week_no").alias("w")).first()
    if stats.n:
        batch_df.withColumn("batch_id", F.lit(batch_id)).write.mode("append").parquet(str(UPDATES))
    print(f"[stream] batch {batch_id:3d}: cập nhật {stats.n:>8,} dòng SV-tuần, tuần mới nhất {stats.w}")
    batch_df.unpersist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", action="store_true", help="tự chạy replay.py trong cùng tiến trình")
    ap.add_argument("--delay", type=float, default=0.2, help="số giây giữa hai ngày khi --replay")
    args = ap.parse_args()

    for d in [INPUT_DIR, CHECKPOINT, STREAM_DIR / "out"]:
        shutil.rmtree(d, ignore_errors=True)
    INPUT_DIR.mkdir(parents=True)

    spark = get_spark("oulad-stream-weekly")
    spark.sparkContext.setLogLevel("WARN")
    t0 = time.time()

    clicks = (spark.readStream.schema(SCHEMA).option("header", True)
              .option("maxFilesPerTrigger", 7).csv(str(INPUT_DIR)))
    weekly = (clicks.withColumn("week_no", week_of("date"))
              .groupBy(*KEY).agg(F.sum("sum_click").cast("long").alias("clicks_week")))
    query = (weekly.writeStream.outputMode("update").foreachBatch(save_batch)
             .option("checkpointLocation", str(CHECKPOINT))
             .trigger(processingTime="2 seconds").start())

    if args.replay:
        threading.Thread(target=replay, args=(args.delay,), daemon=True).start()
    else:
        print(f"[stream] đang chờ file trong {INPUT_DIR}. Mở terminal khác chạy: python stream/replay.py")

    while not DONE.exists():
        if query.exception():
            raise query.exception()
        time.sleep(1)
    query.processAllAvailable()  # đợi xử lý hết các file đã thả rồi mới dừng
    n_batches = len(query.recentProgress)
    query.stop()
    spark.stop()

    run = {"seconds": round(time.time() - t0, 1), "micro_batches": n_batches,
           "files": len(list(INPUT_DIR.glob("day_*.csv")))}
    (STREAM_DIR / "_run.json").write_text(json.dumps(run, indent=2))
    print(f"[stream] xong: {run['files']} file ngày, {n_batches} micro-batch, {run['seconds']}s. "
          f"So với batch: python stream/compare.py")


if __name__ == "__main__":
    main()
