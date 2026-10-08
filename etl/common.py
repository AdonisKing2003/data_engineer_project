"""Hàm dùng chung cho các bước ETL."""
import json
import os
import time
from pathlib import Path

from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"          # 7 file CSV gốc của OULAD
STAGING_DIR = ROOT / "data" / "staging"  # Parquet sau bước 1.3
WAREHOUSE_DIR = ROOT / "data" / "warehouse"  # dim/fact sau bước 1.4, 1.5


def get_spark(app_name: str) -> SparkSession:
    mem = os.getenv("SPARK_DRIVER_MEMORY", "3g")
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", mem)
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def read_staging(spark: SparkSession, name: str) -> DataFrame:
    return spark.read.parquet(str(STAGING_DIR / name))


def read_wh(spark: SparkSession, name: str) -> DataFrame:
    return spark.read.parquet(str(WAREHOUSE_DIR / name))


def week_of(day: str) -> Column:
    """Tuần của một cột ngày: floor(date / 7). Không dùng chia nguyên vì ngày −1 phải là tuần −1."""
    return F.floor(F.col(day) / 7).cast("int")


def mark_exists(df: DataFrame, other: DataFrame, keys: list, name: str) -> DataFrame:
    """Thêm cờ `name` = TRUE nếu khóa `keys` của df có xuất hiện trong other."""
    marks = other.select(*keys).distinct().withColumn(name, F.lit(True))
    return (df.join(marks, keys, "left")
            .withColumn(name, F.coalesce(F.col(name), F.lit(False))))


def write_table(spark: SparkSession, df: DataFrame, name: str, expected: int = None) -> dict:
    """Ghi đè một bảng kho ra data/warehouse/<name>, đếm lại số dòng và in log.
    Ghi đè nên chạy lại không bị nhân đôi."""
    t0 = time.time()
    out = WAREHOUSE_DIR / name
    df.write.mode("overwrite").parquet(str(out))
    n = spark.read.parquet(str(out)).count()
    ok = expected is None or n == expected
    seconds = round(time.time() - t0, 1)
    want = f"(chuẩn {expected:,})" if expected is not None else ""
    print(f"{'OK ' if ok else 'SAI'} {name:22s} {n:>12,} dòng {want}  {seconds}s")
    return {"rows": n, "expected": expected, "ok": ok, "seconds": seconds}


def save_report(report: dict, step: str) -> bool:
    """Ghi log số dòng và thời gian của một bước ra data/warehouse/_report_<step>.json.
    Gộp vào báo cáo cũ, nên chạy lại riêng một bảng không làm mất số của các bảng khác."""
    path = WAREHOUSE_DIR / f"_report_{step}.json"
    merged = json.loads(path.read_text()) if path.exists() else {}
    merged.update(report)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    return all(r["ok"] for r in report.values())
