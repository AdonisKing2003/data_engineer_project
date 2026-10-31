"""Test hàm báo lỗi của DAG Airflow (dags/alerts.py). Không cần cài Airflow: context được giả lập."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dags"))

import alerts  # noqa: E402


@pytest.fixture
def context():
    ti = SimpleNamespace(dag_id="oulad_batch", task_id="load_bq", try_number=2,
                         log_url="http://localhost:8080/log?task_id=load_bq")
    return {"task_instance": ti, "run_id": "manual__2026-11-01", "exception": RuntimeError("BigQuery 403")}


@pytest.fixture
def alert_log(tmp_path, monkeypatch):
    path = tmp_path / "airflow_alerts.jsonl"
    monkeypatch.setattr(alerts, "ALERT_LOG", path)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    return path


def test_failure_is_written_to_alert_log(context, alert_log):
    alerts.notify_failure(context)
    alerts.notify_failure(context)
    lines = alert_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # ghi thêm, không ghi đè
    alert = json.loads(lines[0])
    assert (alert["dag_id"], alert["task_id"], alert["run_id"], alert["try_number"]) == (
        "oulad_batch", "load_bq", "manual__2026-11-01", 2)
    assert alert["error"] == "RuntimeError: BigQuery 403"
    assert alert["log_url"].startswith("http://localhost:8080/")


def test_no_webhook_call_without_url(context, alert_log, monkeypatch):
    monkeypatch.setattr(alerts.urllib.request, "urlopen", lambda *a, **k: pytest.fail("không được gọi webhook"))
    alerts.notify_failure(context)


@pytest.mark.parametrize("url, key", [
    ("https://discord.com/api/webhooks/1/abc", "content"),
    ("https://hooks.slack.com/services/T/B/x", "text"),
])
def test_webhook_payload_matches_service(context, alert_log, monkeypatch, url, key):
    sent = []

    def fake_urlopen(request, timeout):
        sent.append(json.loads(request.data))
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setenv("ALERT_WEBHOOK_URL", url)
    monkeypatch.setattr(alerts.urllib.request, "urlopen", fake_urlopen)
    alerts.notify_failure(context)
    assert list(sent[0]) == [key]
    assert "load_bq" in sent[0][key] and "BigQuery 403" in sent[0][key]


def test_webhook_error_does_not_raise(context, alert_log, monkeypatch, capsys):
    def broken_urlopen(request, timeout):
        raise OSError("mạng lỗi")

    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
    monkeypatch.setattr(alerts.urllib.request, "urlopen", broken_urlopen)
    alerts.notify_failure(context)  # không được ném lỗi
    assert "gửi webhook lỗi" in capsys.readouterr().out
    assert alert_log.exists()  # vẫn ghi log dù webhook lỗi
