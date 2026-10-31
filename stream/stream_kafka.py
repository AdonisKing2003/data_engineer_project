"""Spark Structured Streaming đọc click từ Kafka, cộng theo cửa sổ tuần có watermark.

- Nguồn: Kafka topic (readStream.format("kafka")), tối đa --max-offsets message mỗi micro-batch.
- Thời điểm sự kiện: 2000-01-06 + date ngày. Ngày gốc cách 1970-01-01 đúng 1566 tuần,
  nên cửa sổ 7 ngày của Spark trùng tuần OULAD: week_no = floor(date / 7).
- Watermark: tuần được coi là đóng khi đã thấy sự kiện muộn hơn cuối tuần đó --watermark.
  Spark dọn trạng thái của tuần đã đóng; click đến sau đó bị bỏ và được đếm.
- Đích: outputMode "update" qua foreachBatch. Mỗi micro-batch ghi vào một thư mục riêng
  (ghi đè), nên chạy lại một batch không tạo dòng trùng. --to-bq: nạp thêm lên BigQuery.

Chạy trong container (cần docker compose --profile stream up -d):
    make stream-kafka
"""
import argparse
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
sys.path.insert(0, str(ROOT / "stream"))

from google.cloud import bigquery  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import IntegerType, StringType, StructField, StructType  # noqa: E402

from common import get_spark  # noqa: E402
from produce_kafka import BOOTSTRAP, DONE, TOPIC, produce, recreate_topic  # noqa: E402

STREAM_DIR = ROOT / "data" / "stream"
OUT = STREAM_DIR / "out_kafka"
UPDATES = OUT / "updates"
CHECKPOINT = STREAM_DIR / "checkpoint_kafka"
BASE_EPOCH = 947_116_800  # 2000-01-06 00:00 UTC
WEEK = 7 * 86_400

SCHEMA = StructType([
    StructField("code_module", StringType()), StructField("code_presentation", StringType()),
    StructField("id_student", IntegerType()), StructField("id_site", IntegerType()),
    StructField("date", IntegerType()), StructField("sum_click", IntegerType()),
])
BQ_SCHEMA = [bigquery.SchemaField(n, t) for n, t in [
    ("id_student", "INT64"), ("code_module", "STRING"), ("code_presentation", "STRING"),
    ("week_no", "INT64"), ("clicks_week", "INT64"), ("batch_id", "INT64"),
    ("processed_at", "TIMESTAMP")]]
BQ = None  # (client, table_id) khi chạy với --to-bq


def setup_bq():
    """Tạo lại bảng log cập nhật và view lấy giá trị mới nhất trên BigQuery."""
    project, dataset = os.environ["GCP_PROJECT_ID"], os.getenv("BQ_DATASET", "oulad")
    client = bigquery.Client(project=project, location=os.getenv("BQ_LOCATION", "US"))
    table_id = f"{project}.{dataset}.stream_student_week_updates"
    client.delete_table(table_id, not_found_ok=True)
    client.create_table(bigquery.Table(table_id, schema=BQ_SCHEMA))
    client.query_and_wait(f"""
        CREATE OR REPLACE VIEW `{project}.{dataset}.stream_student_week_latest` AS
        SELECT * EXCEPT (rn) FROM (
          SELECT *, ROW_NUMBER() OVER (
                   PARTITION BY id_student, code_module, code_presentation, week_no
                   ORDER BY batch_id DESC) AS rn
          FROM `{table_id}`)
        WHERE rn = 1""")
    return client, table_id


def save_batch(batch_df, batch_id):
    df = (batch_df.withColumn("batch_id", F.lit(batch_id))
          .withColumn("processed_at", F.current_timestamp()))
    df.persist()
    n = df.count()
    if n:
        df.write.mode("overwrite").parquet(str(UPDATES / f"batch_{batch_id:05d}"))
        if BQ:
            client, table_id = BQ
            client.load_table_from_dataframe(
                df.toPandas(), table_id,
                job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND", schema=BQ_SCHEMA),
            ).result()
    print(f"[stream-kafka] batch {batch_id:3d}: cập nhật {n:>8,} dòng SV-tuần")
    df.unpersist()


def main():
    global BQ
    ap = argparse.ArgumentParser()
    ap.add_argument("--produce", action="store_true", help="chạy producer trong cùng tiến trình")
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--late", type=float, default=0.0)
    ap.add_argument("--watermark", default="7 days")
    ap.add_argument("--max-offsets", type=int, default=250_000, help="khoảng một tuần click mỗi batch")
    ap.add_argument("--to-bq", action="store_true", help="nạp từng micro-batch lên BigQuery")
    args = ap.parse_args()

    for d in [OUT, CHECKPOINT]:
        shutil.rmtree(d, ignore_errors=True)
    DONE.unlink(missing_ok=True)
    recreate_topic()  # tạo topic TRƯỚC khi Spark đăng ký đọc
    if args.to_bq:
        BQ = setup_bq()

    spark = get_spark("oulad-stream-kafka")
    spark.sparkContext.setLogLevel("WARN")
    spark.conf.set("spark.sql.streaming.numRecentProgressUpdates", "1000")
    t0 = time.time()

    raw = (spark.readStream.format("kafka")
           .option("kafka.bootstrap.servers", BOOTSTRAP)
           .option("subscribe", TOPIC)
           .option("startingOffsets", "earliest")
           .option("maxOffsetsPerTrigger", args.max_offsets)
           .load())
    clicks = (raw.select(F.from_json(F.col("value").cast("string"), SCHEMA).alias("c")).select("c.*")
              .withColumn("event_time", F.timestamp_seconds(F.lit(BASE_EPOCH) + F.col("date") * 86_400)))
    weekly = (clicks.withWatermark("event_time", args.watermark)
              .groupBy(F.window("event_time", "7 days"), "id_student", "code_module", "code_presentation")
              .agg(F.sum("sum_click").cast("long").alias("clicks_week"))
              .select("id_student", "code_module", "code_presentation",
                      ((F.unix_timestamp("window.start") - BASE_EPOCH) / WEEK).cast("int").alias("week_no"),
                      "clicks_week"))
    query = (weekly.writeStream.outputMode("update").foreachBatch(save_batch)
             .option("checkpointLocation", str(CHECKPOINT))
             .trigger(processingTime="2 seconds").start())

    producer = None
    if args.produce:
        producer = threading.Thread(target=produce, args=(args.delay, args.late), daemon=True)
        producer.start()
    else:
        print("[stream-kafka] đang chờ. Mở terminal khác chạy: python stream/produce_kafka.py")

    while not DONE.exists():
        if query.exception():
            raise query.exception()
        if producer and not producer.is_alive():
            sys.exit("Producer dừng giữa chừng, xem log phía trên.")
        time.sleep(1)
    query.processAllAvailable()
    progress = query.recentProgress
    query.stop()
    spark.stop()

    ops = [op for p in progress for op in p.get("stateOperators", [])]
    run = {
        "seconds": round(time.time() - t0, 1),
        "micro_batches": len({p["batchId"] for p in progress if p["numInputRows"]}),
        "input_rows": sum(p["numInputRows"] for p in progress),
        "rows_dropped_by_watermark": sum(op.get("numRowsDroppedByWatermark", 0) for op in ops),
        "state_rows_max": max((op["numRowsTotal"] for op in ops), default=0),
        "state_rows_end": ops[-1]["numRowsTotal"] if ops else 0,
        "watermark": args.watermark, "late_ratio": args.late, "to_bigquery": args.to_bq,
    }
    (STREAM_DIR / "_run_kafka.json").write_text(json.dumps(run, indent=2))
    print(json.dumps(run, indent=2))


if __name__ == "__main__":
    main()
