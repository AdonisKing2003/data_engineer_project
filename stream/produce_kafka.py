"""Phát lại click theo từng ngày lên Kafka (bản Kafka của replay.py).

- Mỗi dòng click là một message JSON. Key = id_student, nên click của một SV luôn vào cùng partition
  và giữ đúng thứ tự trong SV đó.
- enable.idempotence: producer gửi lại khi lỗi mạng cũng không tạo message trùng.
- --late p: giữ lại tỷ lệ p số click, gửi sau cùng, để thử watermark bỏ dữ liệu đến trễ.
  Chạy so với batch thì để --late 0.

Chạy (sau khi stream_kafka.py đã tạo topic và đang chờ):
    python stream/produce_kafka.py --delay 1
"""
import argparse
import csv
import json
import os
import random
import time
from pathlib import Path

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

ROOT = Path(__file__).resolve().parents[1]
DAYS_DIR = ROOT / "data" / "stream" / "days"
DONE = ROOT / "data" / "stream" / "_kafka_DONE"
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "oulad.clicks")


def recreate_topic(partitions: int = 4) -> None:
    """Xóa topic cũ (nếu có) rồi tạo lại, để mỗi lần chạy bắt đầu từ topic rỗng."""
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
    if TOPIC in admin.list_topics(timeout=10).topics:
        admin.delete_topics([TOPIC])[TOPIC].result()
        while TOPIC in admin.list_topics(timeout=10).topics:  # Kafka xóa chạy nền
            time.sleep(0.5)
    admin.create_topics([NewTopic(TOPIC, num_partitions=partitions, replication_factor=1)])[TOPIC].result()
    print(f"[kafka] đã tạo topic {TOPIC} ({partitions} partition)")


def _send(producer: Producer, msg: dict) -> None:
    while True:
        try:
            producer.produce(TOPIC, key=str(msg["id_student"]), value=json.dumps(msg))
            producer.poll(0)
            return
        except BufferError:  # hàng đợi nội bộ đầy: chờ gửi bớt rồi thử lại
            producer.poll(0.5)


def produce(delay: float = 0.2, late: float = 0.0, log=print) -> None:
    files = sorted(DAYS_DIR.glob("day_*.csv"))
    if not files:
        raise SystemExit(f"Không có file trong {DAYS_DIR}. Chạy python stream/split_days.py trước.")
    DONE.unlink(missing_ok=True)
    producer = Producer({"bootstrap.servers": BOOTSTRAP, "linger.ms": 50,
                         "compression.type": "lz4", "enable.idempotence": True})
    rng, held, sent = random.Random(42), [], 0
    for i, f in enumerate(files, 1):
        with f.open(newline="") as fh:
            for r in csv.DictReader(fh):
                msg = {"code_module": r["code_module"], "code_presentation": r["code_presentation"],
                       "id_student": int(r["id_student"]), "id_site": int(r["id_site"]),
                       "date": int(r["date"]), "sum_click": int(r["sum_click"])}
                if late and rng.random() < late:
                    held.append(msg)
                    continue
                _send(producer, msg)
                sent += 1
        producer.flush()  # hết một ngày mới sang ngày sau
        if i % 30 == 0 or i == len(files):
            log(f"[kafka] đã gửi {i}/{len(files)} ngày, {sent:,} message")
        time.sleep(delay)
    for msg in held:
        _send(producer, msg)
    producer.flush()
    DONE.touch()
    log(f"[kafka] xong: {sent + len(held):,} message, trong đó {len(held):,} gửi trễ")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.2, help="số giây giữa hai ngày")
    ap.add_argument("--late", type=float, default=0.0, help="tỷ lệ click gửi trễ (thử watermark)")
    a = ap.parse_args()
    produce(a.delay, a.late)
