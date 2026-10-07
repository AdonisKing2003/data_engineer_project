"""Hàm dùng chung cho các bước ETL."""
import os
from pathlib import Path

from pyspark.sql import SparkSession

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
