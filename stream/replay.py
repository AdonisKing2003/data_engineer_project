"""Việc 1.9, bước 2: phát lại click theo từng ngày vào data/stream/input/ (thay cho Kafka).

Mỗi file ngày được chép vào một tên tạm bắt đầu bằng "." (Spark bỏ qua file ẩn), rồi đổi tên một lần.
Nhờ vậy Spark không bao giờ đọc phải file đang chép dở. Thả xong thì tạo file _DONE.
Đây là phát lại có kiểm soát dữ liệu lịch sử, không phải luồng thật; báo cáo cần ghi rõ điều này.

Chạy trong container, song song với stream_weekly.py ở một terminal khác:
    python stream/replay.py                  # mỗi ngày cách nhau 0,2 giây
    python stream/replay.py --delay 1        # chậm hơn, dễ quan sát khi demo
"""
import argparse
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAYS_DIR = ROOT / "data" / "stream" / "days"
INPUT_DIR = ROOT / "data" / "stream" / "input"
DONE = INPUT_DIR / "_DONE"


def replay(delay: float = 0.2, log=print):
    files = sorted(DAYS_DIR.glob("day_*.csv"))
    if not files:
        raise SystemExit(f"Không có file trong {DAYS_DIR}. Chạy python stream/split_days.py trước.")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    DONE.unlink(missing_ok=True)
    for i, f in enumerate(files, 1):
        tmp = INPUT_DIR / f".{f.name}.tmp"
        shutil.copyfile(f, tmp)
        os.replace(tmp, INPUT_DIR / f.name)
        if i % 30 == 0 or i == len(files):
            log(f"[replay] đã thả {i}/{len(files)} file, mới nhất {f.name}")
        time.sleep(delay)
    DONE.touch()
    log("[replay] xong, đã tạo _DONE")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.2, help="số giây giữa hai ngày")
    replay(ap.parse_args().delay)
