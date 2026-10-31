"""DAG dựng lại kho OULAD từ 7 file CSV.

    chờ đủ CSV -> staging -> dims -> facts -> student_week -> quality_gate -> (load_bq || load_pg) -> test_all
                                                                                          -> give_back_files

Mỗi task gọi đúng một mục Makefile, giống make all, nên logic ETL không đổi. Airflow lo phần điều phối:
lập lịch, thứ tự, chạy song song bước không phụ thuộc nhau, chạy lại khi lỗi, log và thời gian từng bước.
Mọi bước đều ghi đè, chạy lại không nhân đôi dữ liệu, nên bật retries là an toàn.

Khác make all ở hai chỗ:
- quality_gate kiểm kho trên Parquet TRƯỚC khi nạp, lỗi thì dừng, không đẩy dữ liệu sai lên BigQuery;
- wait_raw_csv chờ đủ 7 file nguồn thay vì báo lỗi ngay khi thiếu.
"""
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.python import PythonSensor
from airflow.utils.trigger_rule import TriggerRule

REPO = "/work"
RAW = Path(REPO) / "data" / "raw"
RAW_FILES = ["courses.csv", "assessments.csv", "vle.csv", "studentInfo.csv",
             "studentRegistration.csv", "studentAssessment.csv", "studentVle.csv"]
# Venv của Airflow đứng đầu PATH trong container; task phải dùng python, spark-submit, pytest của image app.
TASK_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}


def raw_ready() -> bool:
    return all((RAW / f).is_file() and (RAW / f).stat().st_size > 0 for f in RAW_FILES)


def bash(task_id: str, command: str, **kwargs) -> BashOperator:
    return BashOperator(task_id=task_id, bash_command=command, cwd=REPO,
                        env=TASK_ENV, append_env=True, **kwargs)


with DAG(
    dag_id="oulad_batch",
    description="Dựng lại kho OULAD từ 7 file CSV, kiểm chất lượng, nạp BigQuery và PostgreSQL",
    start_date=datetime(2026, 10, 1),
    schedule="0 2 * * *",          # 2 giờ sáng mỗi ngày (giờ UTC)
    catchup=False,                 # không chạy bù các ngày đã qua
    max_active_runs=1,             # hai lần chạy cùng ghi data/ sẽ đè nhau
    default_args={
        "owner": "tv1",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=20),
    },
    tags=["oulad", "batch"],
) as dag:
    wait_raw = PythonSensor(
        task_id="wait_raw_csv",
        python_callable=raw_ready,
        poke_interval=60,          # kiểm tra mỗi phút
        timeout=60 * 60,           # chờ tối đa 1 giờ rồi báo lỗi
        mode="reschedule",         # nhả chỗ chạy giữa hai lần kiểm tra
    )
    staging = bash("staging", "make -s staging")
    dims = bash("dims", "make -s dims")
    facts = bash("facts", "make -s facts")
    student_week = bash("student_week", "make -s student-week")
    quality_gate = bash(
        "quality_gate",
        "pytest -q tests/test_staging.py tests/test_warehouse.py tests/test_student_week.py",
    )
    load_bq = bash("load_bq", "make -s load-bq")
    load_pg = bash("load_pg", "make -s load-pg")
    test_all = bash("test_all", "make -s test")
    # Container chạy bằng root: trả quyền file trong data/ cho chủ repo, kể cả khi bước trước lỗi.
    give_back_files = bash(
        "give_back_files",
        "python -c \"import sys; sys.path.insert(0, 'etl'); from pathlib import Path; "
        "from common import give_back_to_owner; give_back_to_owner(Path('data'))\"",
        retries=0,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    wait_raw >> staging >> dims >> facts >> student_week >> quality_gate >> [load_bq, load_pg] >> test_all
    test_all >> give_back_files
