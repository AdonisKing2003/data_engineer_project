"""Báo lỗi khi một task của DAG thất bại hẳn (đã hết lượt chạy lại).

- Luôn ghi một dòng JSON vào data/airflow_alerts.jsonl: thời điểm, DAG, task, lần chạy, lỗi, đường dẫn log.
- Nếu .env có ALERT_WEBHOOK_URL thì gửi thêm tin nhắn tới webhook đó: Discord nhận {"content": ...},
  Slack và các dịch vụ cùng kiểu nhận {"text": ...}.
- Gửi webhook lỗi thì chỉ in ra log, không làm hỏng thêm lần chạy.

File này không import airflow, nên test được ở máy không cài Airflow (tests/test_alerts.py).
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ALERT_LOG = Path(os.getenv("ALERT_LOG", "/work/data/airflow_alerts.jsonl"))


def build_alert(context: dict) -> dict:
    ti = context["task_instance"]
    error = context.get("exception")
    return {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dag_id": ti.dag_id,
        "task_id": ti.task_id,
        "run_id": context.get("run_id"),
        "try_number": ti.try_number,
        "error": f"{type(error).__name__}: {error}"[:500] if error else None,
        "log_url": ti.log_url,
    }


def format_message(alert: dict) -> str:
    return (f"Airflow: task {alert['task_id']} của DAG {alert['dag_id']} lỗi "
            f"(lần chạy {alert['run_id']}, lần thử {alert['try_number']}).\n"
            f"Lỗi: {alert['error']}\nLog: {alert['log_url']}")


def webhook_payload(url: str, message: str) -> dict:
    if "discord.com" in url or "discordapp.com" in url:
        return {"content": message[:2000]}  # Discord giới hạn 2000 ký tự
    return {"text": message}


def send_webhook(url: str, message: str) -> None:
    body = json.dumps(webhook_payload(url, message)).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except Exception as error:  # noqa: BLE001 - báo lỗi không được làm hỏng lần chạy
        print(f"[alert] gửi webhook lỗi: {error}")


def notify_failure(context: dict) -> None:
    """on_failure_callback của Airflow: ghi log báo lỗi và gửi webhook nếu có."""
    alert = build_alert(context)
    message = format_message(alert)
    print(f"[alert] {message}")
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")
    url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if url:
        send_webhook(url, message)
