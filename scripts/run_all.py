"""Việc 1.13: chạy toàn bộ pipeline bằng một lệnh, đo thời gian từng bước, ghi docs/etl_timing.md.

Thứ tự: staging -> dims -> facts -> student-week -> load-bq -> load-pg -> test (mỗi bước là một mục Makefile).
Dừng ngay ở bước đầu tiên bị lỗi.

Chạy trong container:
    python scripts/run_all.py                # cũng chính là: make all
    python scripts/run_all.py --skip-bq      # máy chưa có khóa Google Cloud
    python scripts/run_all.py --stream       # chạy thêm phần stream (1.9) ở cuối
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data" / "staging"
WAREHOUSE = ROOT / "data" / "warehouse"
DOC = ROOT / "docs" / "etl_timing.md"

STEPS = [  # (việc, mục Makefile, mô tả)
    ("1.3", "staging", "7 CSV -> staging Parquet"),
    ("1.4", "dims", "làm sạch, 5 dimension + fact_enrollment"),
    ("1.5", "facts", "fact_vle_daily + fact_submission"),
    ("1.8", "student-week", "fact_student_week"),
    ("1.6", "load-bq", "nạp kho lên BigQuery"),
    ("1.7", "load-pg", "nạp kho vào PostgreSQL"),
    ("1.10", "test", "pytest"),
    ("1.9", "stream", "phát lại click qua Spark Streaming, so với batch"),
]

# bảng kho -> (mô tả đầu vào, bảng staging/kho cho số dòng vào)
INPUTS = {
    "dim_presentation": ("courses", "stg_courses"),
    "dim_student": ("studentInfo (distinct SV)", "stg_student_info"),
    "dim_assessment": ("assessments", "stg_assessments"),
    "dim_vle_site": ("vle", "stg_vle"),
    "dim_week": ("sinh từ tuần −4..38", None),
    "fact_enrollment": ("studentInfo ⨝ studentRegistration", "stg_student_info"),
    "fact_vle_daily": ("studentVle (gộp click trùng)", "stg_student_vle"),
    "fact_submission": ("studentAssessment", "stg_student_assessment"),
    "fact_student_week": ("fact_enrollment × tuần", "fact_enrollment"),
}


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def machine_info():
    mem_gb = "?"
    try:
        kb = int(next(line for line in open("/proc/meminfo") if line.startswith("MemTotal")).split()[1])
        mem_gb = f"{kb / 1024 / 1024:.0f}"
    except (OSError, StopIteration):
        pass
    try:
        import pyspark
        spark = pyspark.__version__
    except ImportError:
        spark = "?"
    return (f"{os.cpu_count()} CPU, {mem_gb} GB RAM (nhìn từ container), "
            f"Spark {spark}, driver memory {os.getenv('SPARK_DRIVER_MEMORY', '3g')}")


def write_doc(timings):
    stg = read_json(STAGING / "_row_counts.json")
    wh = {**read_json(WAREHOUSE / "_report_02_clean_dims.json"),
          **read_json(WAREHOUSE / "_report_03_facts.json"),
          **read_json(WAREHOUSE / "_report_06_student_week.json")}
    bq = read_json(WAREHOUSE / "_report_04_load_bq.json")
    pg = read_json(WAREHOUSE / "_report_05_load_pg.json")

    def sec(d, k):
        return f"{d[k]['seconds']}" if k in d else "–"

    lines = [
        "# Thời gian ETL (việc 1.13)",
        "",
        f"Đo lúc {datetime.datetime.now():%d/%m/%Y %H:%M} bằng `make all`. Máy: {machine_info()}.",
        "File này do `scripts/run_all.py` tự sinh; chạy lại `make all` để cập nhật.",
        "",
        "## Từng bước",
        "",
        "Thời gian thực của cả bước, gồm cả khởi động Spark.",
        "",
        "| Việc | Lệnh | Nội dung | Thời gian (s) | Kết quả |",
        "|---|---|---|---:|---|",
    ]
    for (task, target, desc), (seconds, ok) in timings.items():
        lines.append(f"| {task} | `make {target}` | {desc} | {seconds:.1f} | {'OK' if ok else 'LỖI'} |")
    total = sum(s for s, _ in timings.values())
    lines += [f"| | | **Tổng** | **{total:.1f}** | |", ""]

    lines += ["## Staging (1.3)", "",
              "| Bảng | File nguồn | Số dòng | Ghi Parquet (s) |", "|---|---|---:|---:|"]
    for name, r in stg.items():
        lines.append(f"| `{name}` | {r['source']} | {r['rows']:,} | {r['seconds']} |")

    lines += ["", "## Kho (1.4, 1.5, 1.8) và nạp kho (1.6, 1.7)", "",
              "Thời gian ghi Parquet tính từ lúc bắt đầu ghi đến lúc đếm lại xong, không gồm khởi động Spark.",
              "",
              "| Bảng | Đầu vào | Số dòng vào | Số dòng ra | Ghi Parquet (s) | Lên BigQuery (s) | Vào PostgreSQL (s) |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for name, r in wh.items():
        label, src = INPUTS.get(name, ("?", None))
        n_in = stg.get(src, wh.get(src, {})).get("rows") if src else None
        lines.append(f"| `{name}` | {label} | {f'{n_in:,}' if n_in else '–'} | {r['rows']:,} | "
                     f"{r['seconds']} | {sec(bq, name)} | {sec(pg, name)} |")

    DOC.parent.mkdir(exist_ok=True)
    DOC.write_text("\n".join(lines) + "\n")


def give_back_to_owner():
    """Container chạy bằng root: trả quyền file vừa sinh về cho chủ thư mục repo,
    để trên máy thật xóa hay sửa data/ và docs/ không cần sudo."""
    owner = ROOT.stat()
    if os.geteuid() != 0 or owner.st_uid == 0:
        return
    for top in [ROOT / "data", DOC]:
        if not top.exists():
            continue
        paths = [top] + (list(top.rglob("*")) if top.is_dir() else [])
        for p in paths:
            try:
                os.chown(p, owner.st_uid, owner.st_gid, follow_symlinks=False)
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-bq", action="store_true", help="bỏ bước nạp BigQuery (máy chưa có khóa)")
    ap.add_argument("--stream", action="store_true", help="chạy thêm phần stream ở cuối")
    args = ap.parse_args()

    steps = [s for s in STEPS
             if not (args.skip_bq and s[1] == "load-bq") and (args.stream or s[1] != "stream")]
    timings = {}
    for task, target, desc in steps:
        print(f"\n===== [{task}] make {target}: {desc} =====", flush=True)
        t0 = time.time()
        ok = subprocess.run(["make", "-s", target], cwd=ROOT).returncode == 0
        timings[(task, target, desc)] = (time.time() - t0, ok)
        if not ok:
            break

    write_doc(timings)
    give_back_to_owner()
    print("\n===== Tóm tắt =====")
    for (task, target, _), (seconds, ok) in timings.items():
        print(f"{'OK ' if ok else 'LỖI'} [{task:4s}] make {target:13s} {seconds:7.1f}s")
    print(f"Tổng {sum(s for s, _ in timings.values()):.1f}s. Chi tiết: {DOC.relative_to(ROOT)}")
    if not all(ok for _, ok in timings.values()):
        sys.exit("Pipeline dừng ở bước bị lỗi, xem log phía trên.")


if __name__ == "__main__":
    main()
