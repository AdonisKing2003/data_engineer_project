"""Shared, allow-listed query access for the Streamlit application."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass
QUERY_FILES = {
    "overview_offerings": {
        "duckdb": PROJECT_ROOT / "sql" / "overview_offerings.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "overview_offerings.sql",
    },
    "br2_offerings": {
        "duckdb": PROJECT_ROOT / "sql" / "br2_offerings.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br2_offerings.sql",
    },
    "br2_dashboard": {
        "duckdb": PROJECT_ROOT / "sql" / "br2_dashboard.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br2_dashboard.sql",
    },
    "br2_school_totals": {
        "duckdb": PROJECT_ROOT / "sql" / "br2_school_totals.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br2_school_totals.sql",
    },
    "br2_tma_deadlines": {
        "duckdb": PROJECT_ROOT / "sql" / "br2_tma_deadlines.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br2_tma_deadlines.sql",
    },
    "br2_vle_weekly": {
        "duckdb": PROJECT_ROOT / "sql" / "br2_vle_weekly.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br2_vle_weekly.sql",
    },
    "br3_dashboard": {
        "duckdb": PROJECT_ROOT / "sql" / "br3_dashboard.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br3_dashboard.sql",
    },
    "br3_summary": {
        "duckdb": PROJECT_ROOT / "sql" / "br3_summary.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br3_summary.sql",
    },
    "br3_spearman": {
        "duckdb": PROJECT_ROOT / "sql" / "br3_spearman.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br3_spearman.sql",
    },
    "br6_imd_gap": {
        "duckdb": PROJECT_ROOT / "sql" / "br6_imd_gap.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br6_imd_gap.sql",
    },
    "br8_forum_week5": {
        "duckdb": PROJECT_ROOT / "sql" / "br8_forum_week5.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br8_forum_week5.sql",
    },
    "presentations": {
        "duckdb": PROJECT_ROOT / "sql" / "presentations.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "presentations.sql",
    },
    "overall_stats": {
        "duckdb": PROJECT_ROOT / "sql" / "overall_stats.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "overall_stats.sql",
    },
    "br1_school_summary": {
        "duckdb": PROJECT_ROOT / "sql" / "br1_school_summary.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br1_school_summary.sql",
    },
    "br1_assessment_stats": {
        "duckdb": PROJECT_ROOT / "sql" / "br1_assessment_stats.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br1_assessment_stats.sql",
    },
    "br1_assessment_scores": {
        "duckdb": PROJECT_ROOT / "sql" / "br1_assessment_scores.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br1_assessment_scores.sql",
    },
    "br4_school_summary": {
        "duckdb": PROJECT_ROOT / "sql" / "br4_school_summary.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br4_school_summary.sql",
    },
    "br4_at_risk_all": {
        "duckdb": PROJECT_ROOT / "sql" / "br4_at_risk_all.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br4_at_risk_all.sql",
    },
    "br4_at_risk_list": {
        "duckdb": PROJECT_ROOT / "sql" / "br4_at_risk_list.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br4_at_risk_list.sql",
    },
    "br5_withdrawal_summary": {
        "duckdb": PROJECT_ROOT / "sql" / "br5_withdrawal_summary.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br5_withdrawal_summary.sql",
    },
    "br5_school_summary": {
        "duckdb": PROJECT_ROOT / "sql" / "br5_school_summary.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br5_school_summary.sql",
    },
    "br5_retention_curve": {
        "duckdb": PROJECT_ROOT / "sql" / "br5_retention_curve.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br5_retention_curve.sql",
    },
    "br7_students_in_presentation": {
        "duckdb": PROJECT_ROOT / "sql" / "br7_students_in_presentation.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br7_students_in_presentation.sql",
    },
    "br7_cohort_benchmark": {
        "duckdb": PROJECT_ROOT / "sql" / "br7_cohort_benchmark.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br7_cohort_benchmark.sql",
    },
    "br7_student_progress": {
        "duckdb": PROJECT_ROOT / "sql" / "br7_student_progress.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "br7_student_progress.sql",
    },
    "stream_live_weekly": {
        "duckdb": PROJECT_ROOT / "sql" / "stream_live_weekly.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "stream_live_weekly.sql",
    },
    "stream_batch_weekly": {
        "duckdb": PROJECT_ROOT / "sql" / "stream_batch_weekly.sql",
        "bigquery": PROJECT_ROOT / "sql" / "bigquery" / "stream_batch_weekly.sql",
    },
}

# The order is the binding contract for DuckDB's positional ``?`` markers.
# BigQuery uses the same names as named query parameters.
QUERY_PARAMETER_ORDER = {
    "overview_offerings": (),
    "br2_offerings": (),
    "br2_dashboard": ("code_module", "code_presentation"),
    "br2_school_totals": (),
    "br2_tma_deadlines": ("code_module", "code_presentation"),
    "br2_vle_weekly": (),
    "br3_dashboard": ("code_module", "code_presentation"),
    "br3_summary": (),
    "br3_spearman": (),
    "br6_imd_gap": (),
    "br8_forum_week5": (),
    "presentations": (),
    "overall_stats": (),
    "br1_school_summary": (),
    "br1_assessment_stats": ("code_module", "code_presentation"),
    "br1_assessment_scores": ("code_module", "code_presentation"),
    "br4_school_summary": (),
    "br4_at_risk_all": ("week_no",),
    "br4_at_risk_list": ("week_no", "code_module", "code_presentation"),
    "br5_withdrawal_summary": (),
    "br5_school_summary": (),
    "br5_retention_curve": (),
    "br7_students_in_presentation": ("code_module", "code_presentation"),
    "br7_cohort_benchmark": ("code_module", "code_presentation"),
    "br7_student_progress": ("id_student", "code_module", "code_presentation"),
    "stream_live_weekly": (),
    "stream_batch_weekly": (),
}


def _query_path(query_id: str, backend: str) -> Path:
    by_backend = QUERY_FILES.get(query_id)
    if by_backend is None:
        raise ValueError(f"Unknown query id: {query_id!r}")
    query_path = by_backend.get(backend)
    if query_path is None:
        raise ValueError(f"Query {query_id!r} is not available for {backend!r}")
    if not query_path.is_file():
        raise FileNotFoundError(f"Query file is missing: {query_path}")
    return query_path


def _run_duckdb(query: str, parameters: Sequence[Any] | None) -> pd.DataFrame:
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("DuckDB backend selected but package 'duckdb' is not installed") from error

    # Register the warehouse location explicitly so the SQL works regardless of
    # the directory from which Streamlit was started.
    with duckdb.connect(
        database=":memory:", config={"file_search_path": str(PROJECT_ROOT)}
    ) as connection:
        warehouse = PROJECT_ROOT / "data" / "warehouse"
        if warehouse.is_dir():
            for entry in warehouse.iterdir():
                if entry.is_dir() and any(entry.glob("*.parquet")):
                    connection.execute(
                        f"CREATE OR REPLACE VIEW {entry.name} AS SELECT * FROM read_parquet('{entry.as_posix()}/*.parquet')"
                    )
        return connection.execute(query, list(parameters or ())).fetchdf()


def _bq_parameter_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    if isinstance(value, str):
        return "STRING"
    raise TypeError(f"Unsupported BigQuery query parameter value: {type(value).__name__}")


def _validate_parameter_names(parameters: Mapping[str, Any]) -> None:
    if any(not isinstance(name, str) or not name for name in parameters):
        raise TypeError("Named query parameter keys must be non-empty strings")


def _ordered_named_parameters(
    query_id: str, parameters: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_parameter_names(parameters)
    expected = QUERY_PARAMETER_ORDER[query_id]
    expected_names = set(expected)
    supplied_names = set(parameters)
    missing = [name for name in expected if name not in supplied_names]
    extra = sorted(supplied_names - expected_names)
    if missing or extra:
        issues = []
        if missing:
            issues.append(f"missing: {', '.join(missing)}")
        if extra:
            issues.append(f"unsupported: {', '.join(extra)}")
        expected_text = ", ".join(expected) if expected else "none"
        raise ValueError(
            f"Invalid parameters for query {query_id!r} ({'; '.join(issues)}). "
            f"Expected: {expected_text}."
        )
    return {name: parameters[name] for name in expected}


def _duckdb_parameters(
    query_id: str, parameters: Sequence[Any] | Mapping[str, Any] | None
) -> tuple[Any, ...]:
    expected = QUERY_PARAMETER_ORDER[query_id]
    if parameters is None:
        ordered = ()
    elif isinstance(parameters, Mapping):
        ordered = tuple(_ordered_named_parameters(query_id, parameters).values())
    elif isinstance(parameters, (str, bytes)) or not isinstance(parameters, Sequence):
        raise TypeError(
            "DuckDB app queries use a sequence or named parameter mapping"
        )
    else:
        ordered = tuple(parameters)

    if len(ordered) != len(expected):
        if len(ordered) < len(expected):
            issue = f"missing {len(expected) - len(ordered)} parameter(s)"
        else:
            issue = f"received {len(ordered) - len(expected)} unsupported parameter(s)"
        expected_text = ", ".join(expected) if expected else "none"
        raise ValueError(
            f"Invalid parameters for query {query_id!r}: {issue}. "
            f"Expected {len(expected)} in this order: {expected_text}."
        )
    return ordered


@lru_cache(maxsize=4)
def _bigquery_client(project: str, location: str):
    from google.cloud import bigquery

    return bigquery.Client(
        project=project,
        location=location,
        default_job_creation_mode="JOB_CREATION_OPTIONAL",
    )


def _run_bigquery(query: str, parameters: Mapping[str, Any] | None) -> pd.DataFrame:
    project = os.getenv("GCP_PROJECT_ID", "").strip()
    if not project or project.lower() in {"dien-project-id-vao-day", "your-project-id"}:
        raise RuntimeError(
            "BigQuery backend requires GCP_PROJECT_ID. Set it in .env and provide valid "
            "Google Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS."
        )
    dataset = os.getenv("BQ_DATASET", "oulad").strip()
    if not dataset:
        raise RuntimeError("BigQuery backend requires a non-empty BQ_DATASET")

    try:
        from google.cloud import bigquery
    except ImportError as error:
        raise RuntimeError(
            "BigQuery backend selected but google-cloud-bigquery is not installed"
        ) from error

    try:
        client = _bigquery_client(project, os.getenv("BQ_LOCATION", "US"))
        job_config = bigquery.QueryJobConfig(
            default_dataset=f"{project}.{dataset}",
            query_parameters=[
                bigquery.ScalarQueryParameter(name, _bq_parameter_type(value), value)
                for name, value in (parameters or {}).items()
            ],
        )
        # query_and_wait returns small results inline; with job creation optional
        # BigQuery skips creating a job, cutting ~2 s per dashboard query to ~0.5 s.
        rows = client.query_and_wait(query, job_config=job_config)
        return rows.to_dataframe(create_bqstorage_client=False)
    except Exception as error:
        # Surface the original exception as a cause; never switch to another
        # backend silently because that could display stale/local data.
        raise RuntimeError(
            f"BigQuery query failed for project {project!r}, dataset {dataset!r}: {error}"
        ) from error


def run_query(
    query_id: str,
    parameters: Sequence[Any] | Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Run a known query using ``DATA_BACKEND`` and return a DataFrame.

    The dashboard defaults to BigQuery. Set ``DATA_BACKEND=duckdb`` explicitly
    for local Parquet execution. Backend and connection errors are propagated
    with actionable context and never trigger an implicit fallback.
    """
    backend = os.getenv("DATA_BACKEND", "bigquery").strip().lower()
    if backend not in {"bigquery", "duckdb"}:
        raise ValueError(
            f"Unsupported DATA_BACKEND={backend!r}; choose 'bigquery' or 'duckdb'."
        )
    query_path = _query_path(query_id, backend)
    query = query_path.read_text(encoding="utf-8")

    if backend == "duckdb":
        # Reorder named inputs from the query contract rather than relying on
        # the caller's mapping insertion order.
        duckdb_parameters = _duckdb_parameters(query_id, parameters)
        return _run_duckdb(query, duckdb_parameters)
    if parameters is None:
        if QUERY_PARAMETER_ORDER[query_id]:
            # Validate missing named inputs before constructing a BigQuery job.
            _ordered_named_parameters(query_id, {})
        named_parameters = None
    else:
        if not isinstance(parameters, Mapping):
            raise TypeError(
                "BigQuery app queries use named parameters, for example {'week_no': 5}"
            )
        named_parameters = _ordered_named_parameters(query_id, parameters)
        for value in named_parameters.values():
            _bq_parameter_type(value)
    return _run_bigquery(query, named_parameters)
