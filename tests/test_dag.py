"""DAG Airflow nạp được, đúng thứ tự, mọi task có báo lỗi.

Cần cài Airflow nên chạy trong container airflow: docker compose exec airflow make test-dag.
Trong container app (make test) tự bỏ qua.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DAGS = ROOT / "dags"
os.environ.setdefault("AIRFLOW__CORE__DAGS_FOLDER", str(DAGS))
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
sys.path.insert(0, str(DAGS))

pytest.importorskip("airflow", reason="chưa cài Airflow: chạy docker compose exec airflow make test-dag")
from airflow.models import DagBag  # noqa: E402

ORDER = ["wait_raw_csv", "staging", "dims", "facts", "student_week", "quality_gate"]


@pytest.fixture(scope="module")
def dag():
    bag = DagBag(dag_folder=str(DAGS), include_examples=False)
    assert not bag.import_errors, bag.import_errors
    return bag.get_dag("oulad_batch")


def test_dag_loads_with_all_tasks(dag):
    assert dag is not None
    assert set(dag.task_ids) == set(ORDER) | {"load_bq", "marts", "load_pg", "test_all", "give_back_files"}


def test_steps_run_in_order(dag):
    for before, after in zip(ORDER, ORDER[1:]):
        assert dag.get_task(before).downstream_task_ids == {after}


def test_quality_gate_before_both_loads_which_run_in_parallel(dag):
    assert dag.get_task("quality_gate").downstream_task_ids == {"load_bq", "load_pg"}
    assert dag.get_task("test_all").upstream_task_ids == {"marts", "load_pg"}


def test_marts_rebuilt_right_after_bigquery_load(dag):
    assert dag.get_task("load_bq").downstream_task_ids == {"marts"}
    assert dag.get_task("marts").downstream_task_ids == {"test_all"}


def test_files_given_back_even_after_failure(dag):
    assert dag.get_task("give_back_files").trigger_rule == "all_done"


def test_every_task_reports_failure(dag):
    from alerts import notify_failure
    for task in dag.tasks:
        callbacks = task.on_failure_callback
        callbacks = callbacks if isinstance(callbacks, list) else [callbacks]
        assert notify_failure in callbacks, task.task_id
