"""Việc 1.6: nạp mọi bảng trong data/warehouse lên BigQuery, rồi so số dòng.

- Mỗi bảng gộp các file part của Spark thành MỘT file Parquet và nạp bằng MỘT job WRITE_TRUNCATE:
  job thành công thì thay hẳn bảng cũ, thất bại thì bảng cũ giữ nguyên. Chạy lại không bị nhân đôi.
- Kiểu cột lấy theo Parquet: int -> INT64, double -> FLOAT64, string -> STRING, bool -> BOOL.
- Nạp file (load job) không tốn phí; số dòng đọc từ metadata của bảng nên cũng không tốn phí truy vấn.
- --scale N (việc 1.12): nạp kho nhân bản data/warehouse_<N>x vào dataset <BQ_DATASET>_<N>x.
- Kho 1× được nạp thẳng vào bảng đã tối ưu (việc 1.11, số đo ở docs/optimization.md):
  fact_student_week phân vùng theo week_no, fact_vle_daily gom cụm theo code_module, code_presentation.
  Kho 5× và --no-tuning nạp bảng thường, để benchmark star / 3NF / bảng rộng so cùng điều kiện.
  Load job WRITE_TRUNCATE không đổi được cách phân vùng của bảng đã có, nên khi cách phân vùng hoặc
  gom cụm khác bảng cũ, bảng cũ bị xóa trước khi nạp (chỉ lúc đổi qua lại, không phải mỗi lần nạp).

Cần: .env có GCP_PROJECT_ID, BQ_DATASET, BQ_LOCATION; khóa ở secrets/gcp-key.json.
Chạy trong container (không cần Spark):
    cd etl && python 04_load_bq.py              # nạp mọi bảng
    cd etl && python 04_load_bq.py dim_week     # chỉ nạp một vài bảng
    cd etl && python 04_load_bq.py --scale 5    # kho 5× vào dataset oulad_5x
    cd etl && python 04_load_bq.py --no-tuning  # bảng thường, không phân vùng / gom cụm (trước make bench)
"""
import argparse
import io
import os
import sys
import time

import pyarrow.parquet as pq
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from common import give_back_to_owner, save_report, scaled_dir

# Cách lưu vật lý của kho 1× trên BigQuery (việc 1.11). Bảng không có trong đây nạp như bảng thường.
TUNING = {
    # Trang Cảnh báo luôn hỏi một tuần: mỗi tuần một phân vùng, tuần -4 đến 38 (đầu mút 39 không tính).
    "fact_student_week": {"range": ("week_no", -4, 39, 1)},
    # Trang Học phần lọc theo một đợt: các khối của cùng một đợt nằm cạnh nhau.
    "fact_vle_daily": {"cluster": ["code_module", "code_presentation"]},
}
PLAIN = {"range": None, "cluster": None}


def warehouse_tables(src):
    return sorted(p.name for p in src.iterdir()
                  if p.is_dir() and p.name.startswith(("dim_", "fact_")))


def layout_of(table):
    """Cách phân vùng và gom cụm của một bảng BigQuery, cùng dạng với TUNING."""
    rp = table.range_partitioning
    return {
        "range": (rp.field, rp.range_.start, rp.range_.end, rp.range_.interval) if rp else None,
        "cluster": list(table.clustering_fields) if table.clustering_fields else None,
    }


def describe(layout):
    parts = []
    if layout["range"]:
        field, start, end, step = layout["range"]
        parts.append(f"phân vùng {field} [{start}, {end}) bước {step}")
    if layout["cluster"]:
        parts.append("gom cụm " + ", ".join(layout["cluster"]))
    return "; ".join(parts) or "bảng thường"


def load_table(client, dataset, src, name, tuned=True):
    t0 = time.time()
    table = pq.read_table(str(src / name))  # bỏ qua _SUCCESS và .crc
    buf = io.BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)
    want = {**PLAIN, **TUNING.get(name, {})} if tuned else dict(PLAIN)
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    if want["range"]:
        field, start, end, step = want["range"]
        job_config.range_partitioning = bigquery.RangePartitioning(
            field=field, range_=bigquery.PartitionRange(start=start, end=end, interval=step))
    if want["cluster"]:
        job_config.clustering_fields = want["cluster"]
    table_id = f"{dataset}.{name}"
    try:
        old = layout_of(client.get_table(table_id))
    except NotFound:
        old = None
    if old is not None and old != want:
        # WRITE_TRUNCATE báo lỗi khi cách phân vùng khác bảng đã có: xóa rồi nạp lại từ đầu.
        print(f"    {name}: đổi từ {describe(old)} sang {describe(want)}, xóa bảng cũ trước khi nạp")
        client.delete_table(table_id)
    client.load_table_from_file(buf, table_id, job_config=job_config).result()
    loaded = client.get_table(table_id)
    n_bq = loaded.num_rows
    layout = layout_of(loaded)
    ok = n_bq == table.num_rows and layout == want
    seconds = round(time.time() - t0, 1)
    print(f"{'OK ' if ok else 'SAI'} {name:22s} {n_bq:>12,} dòng trên BigQuery "
          f"(Parquet {table.num_rows:,})  {seconds}s  [{describe(layout)}]")
    return {"rows": n_bq, "expected": table.num_rows, "ok": ok, "seconds": seconds,
            "layout": describe(layout)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="*", help="chỉ nạp các bảng này (mặc định: mọi bảng)")
    ap.add_argument("--scale", type=int, default=1, help="nạp kho nhân bản N× (việc 1.12)")
    ap.add_argument("--no-tuning", action="store_true",
                    help="nạp bảng thường, không phân vùng / gom cụm (kho 5× luôn là bảng thường)")
    args = ap.parse_args()

    project = os.environ["GCP_PROJECT_ID"]
    base = os.getenv("BQ_DATASET", "oulad")
    dataset = f"{project}.{base}" if args.scale == 1 else f"{project}.{base}_{args.scale}x"
    location = os.getenv("BQ_LOCATION", "US")
    src = scaled_dir(args.scale)

    names = args.tables or (warehouse_tables(src) if src.is_dir() else [])
    missing = [n for n in names if not (src / n).is_dir()]
    if missing or not names:
        sys.exit(f"Không thấy bảng trong {src}: {missing or 'trống'}. "
                 f"Chạy {'make dims, make facts' if args.scale == 1 else 'make scale'} trước.")

    client = bigquery.Client(project=project, location=location)
    ds = bigquery.Dataset(dataset)
    ds.location = location
    client.create_dataset(ds, exists_ok=True)

    tuned = args.scale == 1 and not args.no_tuning
    report = {name: load_table(client, dataset, src, name, tuned) for name in names}
    ok = save_report(report, "04_load_bq", src)
    give_back_to_owner(src)
    if not ok:
        sys.exit("Có bảng lệch số dòng giữa BigQuery và Parquet, xem log phía trên.")
    print(f"Xong 1.6: {len(names)} bảng đã lên {dataset}, số dòng khớp Parquet. Báo nhóm!")


if __name__ == "__main__":
    main()
