"""Manually refresh the two allow-listed BigQuery TV3 dashboard marts.

By default this command runs dry-run SELECTs and reports estimated source bytes.
Pass ``--apply`` to replace only ``tv3_br2_weekly_mart`` and
``tv3_br3_student_mart`` in the configured ``BQ_DATASET``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SAFE_PROJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
SAFE_DATASET = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class Mart:
    table: str
    source_sql: Path
    grain: tuple[str, ...]
    required_columns: tuple[str, ...]


MARTS = (
    Mart(
        table="tv3_br2_weekly_mart",
        source_sql=ROOT / "sql" / "bigquery" / "br2_vle_weekly.sql",
        grain=("code_module", "code_presentation", "week_no", "activity_type"),
        required_columns=(
            "code_module",
            "code_presentation",
            "week_no",
            "week_start_day",
            "week_end_day",
            "activity_type",
            "enrolled_students",
            "offering_week_total_clicks",
            "avg_clicks_per_enrolled_student",
            "activity_type_total_clicks",
            "activity_type_avg_clicks_per_enrolled_student",
            "activity_type_click_share",
            "avg_clicks_rank",
            "total_clicks_rank",
            "mart_created_at",
        ),
    ),
    Mart(
        table="tv3_br3_student_mart",
        source_sql=ROOT / "sql" / "bigquery" / "br3_spearman.sql",
        grain=("code_module", "code_presentation", "id_student"),
        required_columns=(
            "code_module",
            "code_presentation",
            "id_student",
            "clicks_before_deadline",
            "score",
            "n",
            "rho",
            "mart_created_at",
        ),
    ),
)


def _load_dotenv() -> None:
    """Load local settings when available; container-injected settings win."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env", override=False)


def _project_and_dataset() -> tuple[str, str, str]:
    project = os.getenv("GCP_PROJECT_ID", "").strip()
    dataset = os.getenv("BQ_DATASET", "oulad").strip()
    location = os.getenv("BQ_LOCATION", "US").strip() or "US"
    if not project or project.lower() in {"dien-project-id-vao-day", "your-project-id"}:
        raise RuntimeError("Set GCP_PROJECT_ID to a valid Google Cloud project ID")
    if not SAFE_PROJECT.fullmatch(project):
        raise RuntimeError("GCP_PROJECT_ID contains unsupported characters")
    if not SAFE_DATASET.fullmatch(dataset):
        raise RuntimeError("BQ_DATASET must contain only letters, digits, and underscores")
    return project, dataset, location


def _read_select(mart: Mart) -> str:
    if not mart.source_sql.is_file():
        raise FileNotFoundError(f"BigQuery source query is missing: {mart.source_sql}")
    raw_sql = mart.source_sql.read_text(encoding="utf-8").strip().rstrip(";").strip()
    if not raw_sql:
        raise RuntimeError(f"BigQuery source query is empty: {mart.source_sql}")
    # The BR3 raw result includes id_student while keeping its existing score,
    # zero-click, rank, n, and rho calculations. The BR2 query is used as-is.
    return (
        "SELECT CURRENT_TIMESTAMP() AS mart_created_at, source.*\n"
        "FROM (\n"
        f"{raw_sql}\n"
        ") AS source"
    )


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "not reported"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:,.1f} {unit}"
        size /= 1024
    return f"{value:,} B"


def _job_config(bigquery: Any, project: str, dataset: str, *, dry_run: bool):
    return bigquery.QueryJobConfig(
        default_dataset=f"{project}.{dataset}",
        dry_run=dry_run,
        use_query_cache=False,
    )


def _estimate(client: Any, bigquery: Any, project: str, dataset: str, location: str,
              mart: Mart, select_sql: str) -> int:
    job = client.query(
        select_sql,
        job_config=_job_config(bigquery, project, dataset, dry_run=True),
        location=location,
    )
    if job.total_bytes_processed is None:
        raise RuntimeError(f"BigQuery returned no dry-run estimate for {dataset}.{mart.table}")
    return int(job.total_bytes_processed)


def _validate_mart(client: Any, bigquery: Any, project: str, dataset: str,
                   location: str, mart: Mart) -> None:
    table_id = f"{project}.{dataset}.{mart.table}"
    table = client.get_table(table_id)
    fields = {field.name for field in table.schema}
    missing = sorted(set(mart.required_columns) - fields)
    if missing:
        raise RuntimeError(f"{dataset}.{mart.table} is missing required columns: {missing}")

    grain_fields = ", ".join(f"{column} AS {column}" for column in mart.grain)
    sql = (
        "SELECT COUNT(*) AS row_count, "
        f"COUNT(DISTINCT STRUCT({grain_fields})) AS grain_count, "
        "MIN(mart_created_at) AS mart_created_at "
        f"FROM `{table_id}`"
    )
    validation_started = time.perf_counter()
    job = client.query(
        sql,
        job_config=_job_config(bigquery, project, dataset, dry_run=False),
        location=location,
    )
    row = next(iter(job.result()))
    validation_elapsed = time.perf_counter() - validation_started
    row_count = int(row["row_count"])
    grain_count = int(row["grain_count"])
    metadata_count = int(table.num_rows or 0)
    created = table.created
    created_text = created.astimezone(timezone.utc).isoformat() if created else "unknown"
    mart_created = row["mart_created_at"]
    mart_created_text = (
        mart_created.astimezone(timezone.utc).isoformat() if mart_created else "unknown"
    )
    ok = row_count == grain_count and row_count == metadata_count
    print(
        f"{'OK' if ok else 'FAIL'} {dataset}.{mart.table}: "
        f"rows={row_count:,}, unique_grain={grain_count:,}, "
        f"metadata_rows={metadata_count:,}, mart_created_at={mart_created_text}, "
        f"table_created_at={created_text}, validation_elapsed={validation_elapsed:.2f}s, "
        f"validation_bytes={_format_bytes(job.total_bytes_processed)}"
    )
    if not ok:
        raise RuntimeError(f"Row-count or grain validation failed for {dataset}.{mart.table}")


def refresh(*, apply: bool) -> None:
    from google.cloud import bigquery

    project, dataset, configured_location = _project_and_dataset()
    client = bigquery.Client(project=project, location=configured_location)
    dataset_object = client.get_dataset(f"{project}.{dataset}")
    location = dataset_object.location or configured_location
    selects = {mart.table: _read_select(mart) for mart in MARTS}

    estimates: dict[str, int] = {}
    for mart in MARTS:
        estimate = _estimate(
            client, bigquery, project, dataset, location, mart, selects[mart.table]
        )
        estimates[mart.table] = estimate
    print(f"BigQuery dry-run estimates for {project}.{dataset} ({location}):")
    for mart in MARTS:
        print(f"  {mart.table}: {_format_bytes(estimates[mart.table])}")
    print(f"  Total: {_format_bytes(sum(estimates.values()))}")

    if not apply:
        print("Dry run only; no BigQuery tables were changed. Pass --apply to refresh the marts.")
        return

    for mart in MARTS:
        target = f"`{project}.{dataset}.{mart.table}`"
        sql = f"CREATE OR REPLACE TABLE {target} AS\n{selects[mart.table]}"
        started = time.perf_counter()
        started_text = datetime.now(timezone.utc).isoformat()
        job = client.query(
            sql,
            job_config=_job_config(bigquery, project, dataset, dry_run=False),
            location=location,
        )
        job.result()
        elapsed = time.perf_counter() - started
        job_created = job.created.astimezone(timezone.utc).isoformat() if job.created else "unknown"
        finished_text = datetime.now(timezone.utc).isoformat()
        print(
            f"Refreshed {dataset}.{mart.table}: started_at={started_text}, "
            f"job_created={job_created}, finished_at={finished_text}, "
            f"elapsed={elapsed:.2f}s, bytes_processed={_format_bytes(job.total_bytes_processed)}, "
            f"bytes_billed={_format_bytes(job.total_bytes_billed)}"
        )
        _validate_mart(client, bigquery, project, dataset, location, mart)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="estimate query bytes only (the default; no table changes)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="create or replace the two allow-listed dashboard marts",
    )
    args = parser.parse_args()
    _load_dotenv()
    try:
        refresh(apply=args.apply)
    except Exception as exc:
        print(f"TV3 mart refresh failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
