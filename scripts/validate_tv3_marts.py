"""Compare TV3 dashboard marts with raw BR2/BR3 results before benchmarking.

The script is read-only. BigQuery queries disable result cache and run a dry-run
bytes preflight before reading any rows. Reports contain counts and hashes only;
student-level rows and identifiers are never written to disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import data as app_data  # noqa: E402


BR2_COLUMNS = (
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
)
BR2_KEY = ("code_module", "code_presentation", "week_no", "activity_type")
BR3_COLUMNS = (
    "code_module",
    "code_presentation",
    "id_student",
    "clicks_before_deadline",
    "score",
    "n",
    "rho",
)
BR3_KEY = ("code_module", "code_presentation", "id_student")
BR2_APP_COLUMNS = (
    "week_no",
    "activity_type",
    "activity_type_click_share",
    "activity_type_total_clicks",
)
BR3_APP_COLUMNS = (
    "code_module",
    "code_presentation",
    "clicks_before_deadline",
    "score",
    "n",
    "rho",
)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env", override=False)


def _bq_context() -> tuple[Any, str, str, str]:
    try:
        from google.cloud import bigquery
    except ImportError as error:
        raise RuntimeError("BigQuery validation requires google-cloud-bigquery") from error
    project = os.getenv("GCP_PROJECT_ID", "").strip()
    dataset = os.getenv("BQ_DATASET", "oulad").strip()
    location = os.getenv("BQ_LOCATION", "US").strip() or "US"
    if not project or project.lower() in {"dien-project-id-vao-day", "your-project-id"}:
        raise RuntimeError("Set GCP_PROJECT_ID before running BigQuery parity checks")
    if not dataset:
        raise RuntimeError("BQ_DATASET must not be empty")
    return bigquery, project, dataset, location


def _query_path(query_id: str, engine: str) -> Path:
    backend = "bigquery" if engine == "bq" else "duckdb"
    return app_data._query_path(query_id, backend)


def _parameters(query_id: str, parameters: Mapping[str, Any] | None) -> dict[str, Any]:
    return app_data._ordered_named_parameters(query_id, parameters or {})


def _run(
    engine: str,
    *,
    query_id: str | None = None,
    sql: str | None = None,
    parameters: Mapping[str, Any] | None = None,
    dry_run: bool = False,
) -> tuple[Any | None, dict[str, Any]]:
    """Run one query and return (DataFrame, timing/bytes metadata)."""
    import pandas as pd

    if (query_id is None) == (sql is None):
        raise ValueError("Supply exactly one of query_id or sql")
    if query_id is not None:
        path = _query_path(query_id, engine)
        query = path.read_text(encoding="utf-8")
        named = _parameters(query_id, parameters)
    else:
        query = str(sql)
        named = dict(parameters or {})

    if engine == "duckdb":
        if dry_run:
            return None, {"bytes_processed": None, "elapsed_seconds": 0.0, "row_count": None}
        import duckdb

        values = tuple(named.values())
        started = time.perf_counter()
        with duckdb.connect(
            database=":memory:", config={"file_search_path": str(ROOT)}
        ) as connection:
            frame = connection.execute(query, list(values)).fetchdf()
        return frame, {
            "bytes_processed": None,
            "elapsed_seconds": time.perf_counter() - started,
            "row_count": len(frame),
        }

    bigquery, project, dataset, location = _bq_context()
    client = bigquery.Client(project=project, location=location)
    query_parameters = [
        bigquery.ScalarQueryParameter(name, app_data._bq_parameter_type(value), value)
        for name, value in named.items()
    ]
    config = bigquery.QueryJobConfig(
        default_dataset=f"{project}.{dataset}",
        query_parameters=query_parameters,
        use_query_cache=False,
        dry_run=dry_run,
    )
    job = client.query(query, job_config=config, location=location)
    if dry_run:
        return None, {
            "bytes_processed": job.total_bytes_processed,
            "elapsed_seconds": 0.0,
            "row_count": None,
        }
    started = time.perf_counter()
    frame = job.result().to_dataframe(create_bqstorage_client=False)
    wall = time.perf_counter() - started
    job_elapsed = (
        (job.ended - job.started).total_seconds()
        if job.ended is not None and job.started is not None
        else None
    )
    return frame, {
        "bytes_processed": job.total_bytes_processed,
        "bytes_billed": job.total_bytes_billed,
        "elapsed_seconds": job_elapsed if job_elapsed is not None else wall,
        "wall_seconds": wall,
        "row_count": len(frame),
        "job_id": job.job_id,
    }


def _normalize(value: Any) -> Any:
    import pandas as pd

    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (float,)):
        return round(value, 8)
    if hasattr(value, "item"):
        return value.item()
    return value


def frame_hash(frame: Any, columns: Sequence[str], sort_columns: Sequence[str]) -> str:
    import pandas as pd

    view = frame.loc[:, list(columns)].copy()
    if len(view):
        view = view.sort_values(list(sort_columns), kind="mergesort", na_position="last")
    rows = [[_normalize(value) for value in row] for row in view.itertuples(index=False, name=None)]
    payload = json.dumps(
        {"columns": list(columns), "rows": rows},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_frames_equal(
    expected: Any,
    actual: Any,
    *,
    columns: Sequence[str],
    keys: Sequence[str] = (),
    unique_keys: bool = False,
    tolerance: float = 1e-8,
) -> None:
    import numpy as np
    import pandas as pd
    from pandas.api.types import is_bool_dtype, is_numeric_dtype

    for label, frame in (("expected", expected), ("actual", actual)):
        missing = set(columns) - set(frame.columns)
        if missing:
            raise AssertionError(f"{label} output is missing columns: {sorted(missing)}")
    left = expected.loc[:, list(columns)].copy()
    right = actual.loc[:, list(columns)].copy()
    if len(left) != len(right):
        raise AssertionError(f"row count differs: {len(left)} != {len(right)}")
    if keys and unique_keys:
        for label, frame in (("expected", left), ("actual", right)):
            if frame.duplicated(list(keys)).any():
                raise AssertionError(f"{label} has duplicate business keys {tuple(keys)}")
    ordering = list(keys) if unique_keys and keys else list(columns)
    if len(left):
        left = left.sort_values(ordering, kind="mergesort", na_position="last").reset_index(drop=True)
        right = right.sort_values(ordering, kind="mergesort", na_position="last").reset_index(drop=True)
    for column in columns:
        lvalues, rvalues = left[column], right[column]
        lnull, rnull = lvalues.isna().to_numpy(), rvalues.isna().to_numpy()
        if not np.array_equal(lnull, rnull):
            raise AssertionError(f"null values differ in {column}")
        present = ~lnull
        if not present.any():
            continue
        if is_numeric_dtype(lvalues.dtype) and is_numeric_dtype(rvalues.dtype) and not (
            is_bool_dtype(lvalues.dtype) or is_bool_dtype(rvalues.dtype)
        ):
            left_values = pd.to_numeric(lvalues[present]).to_numpy()
            right_values = pd.to_numeric(rvalues[present]).to_numpy()
            if np.issubdtype(left_values.dtype, np.integer) and np.issubdtype(
                right_values.dtype, np.integer
            ):
                equal = np.array_equal(left_values, right_values)
            else:
                equal = np.allclose(
                    left_values.astype(float),
                    right_values.astype(float),
                    rtol=0.0,
                    atol=tolerance,
                    equal_nan=True,
                )
            if not equal:
                raise AssertionError(f"numeric values differ in {column}")
        elif not lvalues[present].reset_index(drop=True).equals(
            rvalues[present].reset_index(drop=True)
        ):
            raise AssertionError(f"values differ in {column}")


def _mart_sql(table: str, columns: Sequence[str]) -> str:
    projection = ",\n    ".join(columns)
    order = ", ".join(columns[:3])
    return f"SELECT {projection} FROM {table} ORDER BY {order}"


def _record(records: list[dict[str, Any]], name: str, backend: str,
            frame: Any, columns: Sequence[str], keys: Sequence[str]) -> None:
    records.append(
        {
            "check": name,
            "backend": backend,
            "status": "PASS",
            "row_count": len(frame),
            "sha256": frame_hash(frame, columns, keys or columns),
        }
    )


def validate_engine(engine: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import pandas as pd

    records: list[dict[str, Any]] = []
    snapshots: dict[str, Any] = {}
    br2_raw, _ = _run(engine, query_id="br2_vle_weekly")
    br2_mart, _ = _run(
        engine,
        sql=_mart_sql("tv3_br2_weekly_mart", BR2_COLUMNS) if engine == "bq"
        else app_data._query_path("br2_vle_weekly", "duckdb").read_text(encoding="utf-8"),
    )
    assert_frames_equal(br2_raw, br2_mart, columns=BR2_COLUMNS, keys=BR2_KEY, unique_keys=True)
    _record(records, "BR2 raw versus mart", engine, br2_mart, BR2_COLUMNS, BR2_KEY)
    snapshots["br2"] = br2_raw.loc[:, list(BR2_COLUMNS)].copy()

    app_br2_rows = 0
    offerings = br2_raw[["code_module", "code_presentation"]].drop_duplicates()
    for row in offerings.sort_values(["code_module", "code_presentation"]).itertuples(index=False):
        module, presentation = str(row.code_module), str(row.code_presentation)
        expected = br2_raw.loc[
            (br2_raw["code_module"] == module)
            & (br2_raw["code_presentation"] == presentation),
            list(BR2_APP_COLUMNS),
        ]
        actual, _ = _run(
            engine,
            query_id="br2_dashboard",
            parameters={"code_module": module, "code_presentation": presentation},
        )
        assert_frames_equal(expected, actual, columns=BR2_APP_COLUMNS, keys=("week_no", "activity_type"), unique_keys=True)
        deadlines, _ = _run(
            engine,
            query_id="br2_tma_deadlines",
            parameters={"code_module": module, "code_presentation": presentation},
        )
        if list(deadlines.columns) != ["week_no"]:
            raise AssertionError(f"BR2 TMA deadlines have unexpected columns: {list(deadlines.columns)}")
        weeks = deadlines["week_no"].astype(int).tolist()
        if weeks != sorted(set(weeks)):
            raise AssertionError(f"BR2 TMA weeks are not unique and ordered for {module} {presentation}")
        app_br2_rows += len(actual)
    records.append({
        "check": "BR2 selected-offering dashboard slices",
        "backend": engine,
        "status": "PASS",
        "row_count": app_br2_rows,
        "sha256": "not emitted: per-offering hashes are intentionally omitted",
    })

    br3_raw, _ = _run(engine, query_id="br3_spearman")
    br3_mart, _ = _run(
        engine,
        sql=_mart_sql("tv3_br3_student_mart", BR3_COLUMNS) if engine == "bq"
        else app_data._query_path("br3_spearman", "duckdb").read_text(encoding="utf-8"),
    )
    assert_frames_equal(br3_raw, br3_mart, columns=BR3_COLUMNS, keys=BR3_KEY, unique_keys=True)
    _record(records, "BR3 raw versus internal student mart", engine, br3_mart, BR3_COLUMNS, BR3_KEY)
    snapshots["br3"] = br3_raw.loc[:, list(BR3_COLUMNS)].copy()

    raw_summary = (
        br3_raw.groupby(["code_module", "code_presentation"], as_index=False)
        .agg(n=("n", "first"), rho=("rho", "first"))
        .sort_values(["code_module", "code_presentation"])
        .reset_index(drop=True)
    )
    summary, _ = _run(engine, query_id="br3_summary")
    summary_columns = ("code_module", "code_presentation", "n", "rho")
    assert_frames_equal(
        raw_summary, summary, columns=summary_columns,
        keys=("code_module", "code_presentation"), unique_keys=True,
    )
    if "id_student" in summary.columns:
        raise AssertionError("BR3 summary must not expose id_student")
    _record(records, "BR3 summary", engine, summary, summary_columns,
            ("code_module", "code_presentation"))
    snapshots["br3_summary"] = raw_summary

    app_br3_rows = 0
    for row in raw_summary.itertuples(index=False):
        module, presentation = str(row.code_module), str(row.code_presentation)
        expected = br3_raw.loc[
            (br3_raw["code_module"] == module)
            & (br3_raw["code_presentation"] == presentation),
            list(BR3_APP_COLUMNS),
        ]
        actual, _ = _run(
            engine,
            query_id="br3_dashboard",
            parameters={"code_module": module, "code_presentation": presentation},
        )
        if "id_student" in actual.columns:
            raise AssertionError("BR3 dashboard slice must not expose id_student")
        assert_frames_equal(expected, actual, columns=BR3_APP_COLUMNS)
        app_br3_rows += len(actual)
    records.append({
        "check": "BR3 selected-offering dashboard slices",
        "backend": engine,
        "status": "PASS",
        "row_count": app_br3_rows,
        "sha256": "not emitted: per-offering hashes are intentionally omitted",
    })
    return records, snapshots


def _preflight_bigquery(max_bytes: int) -> None:
    required = ["br2_vle_weekly", "br3_spearman"]
    estimates: list[tuple[str, int]] = []
    for query_id in required:
        _, metrics = _run("bq", query_id=query_id, dry_run=True)
        estimate = metrics.get("bytes_processed")
        if estimate is None:
            raise RuntimeError(f"BigQuery did not return a dry-run estimate for {query_id}")
        estimates.append((query_id, int(estimate)))
    total = sum(estimate for _, estimate in estimates)
    print("BigQuery dry-run scan estimates:")
    for query_id, estimate in estimates:
        print(f"  {query_id}: {estimate:,} bytes")
    print(f"  total: {total:,} bytes (limit {max_bytes:,})")
    if total > max_bytes:
        raise RuntimeError("BigQuery preflight exceeds --max-bq-bytes; no result queries were run")


def _measure(engine: str, repetitions: int, selected: tuple[str, str]) -> list[dict[str, Any]]:
    """Measure full-query baseline versus selected dashboard slice workloads."""
    module, presentation = selected

    def run_variant(workload: str, variant: str) -> tuple[float, int | None, int]:
        if workload == "BR2" and variant == "baseline":
            _, metrics = _run(engine, query_id="br2_vle_weekly")
            return metrics["elapsed_seconds"], metrics.get("bytes_processed"), int(metrics["row_count"])
        if workload == "BR2":
            results = [
                _run(engine, query_id="br2_offerings"),
                _run(engine, query_id="br2_dashboard", parameters={"code_module": module, "code_presentation": presentation}),
                _run(engine, query_id="br2_tma_deadlines", parameters={"code_module": module, "code_presentation": presentation}),
            ]
        elif variant == "baseline":
            _, metrics = _run(engine, query_id="br3_spearman")
            return metrics["elapsed_seconds"], metrics.get("bytes_processed"), int(metrics["row_count"])
        else:
            results = [
                _run(engine, query_id="br3_summary"),
                _run(engine, query_id="br3_dashboard", parameters={"code_module": module, "code_presentation": presentation}),
            ]
        elapsed = sum(metrics["elapsed_seconds"] for _, metrics in results)
        byte_values = [metrics.get("bytes_processed") for _, metrics in results]
        total_bytes = sum(value for value in byte_values if value is not None) if any(value is not None for value in byte_values) else None
        rows = sum(int(metrics["row_count"]) for _, metrics in results)
        return elapsed, total_bytes, rows

    records = []
    for workload in ("BR2", "BR3"):
        for variant in ("baseline", "dashboard_slice"):
            # One warm-up per variant; it is deliberately not included in medians.
            run_variant(workload, variant)
            for repetition in range(1, repetitions + 1):
                elapsed, bytes_scanned, rows = run_variant(workload, variant)
                records.append({
                    "backend": engine,
                    "workload": workload,
                    "variant": variant,
                    "selected_offering": f"{module} {presentation}",
                    "repetition": repetition,
                    "elapsed_seconds": elapsed,
                    "bytes_processed": bytes_scanned,
                    "row_count": rows,
                })
    return records


def _median_records(measurements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import pandas as pd

    frame = pd.DataFrame(measurements)
    if frame.empty:
        return []
    group_columns = ["backend", "workload", "variant", "selected_offering"]
    rows = []
    for keys, group in frame.groupby(group_columns, dropna=False):
        row = dict(zip(group_columns, keys))
        row["repetitions"] = len(group)
        row["median_elapsed_seconds"] = float(group["elapsed_seconds"].median())
        row["median_bytes_processed"] = (
            float(group["bytes_processed"].median())
            if group["bytes_processed"].notna().any()
            else None
        )
        row["row_count"] = int(group["row_count"].median())
        rows.append(row)
    return rows


def validate(*, engine: str, max_bq_bytes: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if engine in {"bq", "both"}:
        _preflight_bigquery(max_bq_bytes)
    engines = ("duckdb", "bq") if engine == "both" else (engine,)
    records: list[dict[str, Any]] = []
    snapshots: dict[str, dict[str, Any]] = {}
    for backend in engines:
        print(f"Checking {backend} raw-versus-dashboard parity...")
        backend_records, backend_snapshots = validate_engine(backend)
        records.extend(backend_records)
        snapshots[backend] = backend_snapshots
    if len(engines) == 2:
        for workload, columns, keys in (
            ("br2", BR2_COLUMNS, BR2_KEY),
            ("br3", BR3_COLUMNS, BR3_KEY),
            ("br3_summary", ("code_module", "code_presentation", "n", "rho"), ("code_module", "code_presentation")),
        ):
            assert_frames_equal(
                snapshots["duckdb"][workload],
                snapshots["bq"][workload],
                columns=columns,
                keys=keys,
                unique_keys=True,
            )
            records.append({
                "check": f"Cross-backend {workload}",
                "backend": "duckdb+bq",
                "status": "PASS",
                "row_count": len(snapshots["duckdb"][workload]),
                "sha256": frame_hash(snapshots["duckdb"][workload], columns, keys),
            })
    return records, snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("duckdb", "bq", "both"), default="both")
    parser.add_argument("--max-bq-bytes", type=int, default=5_000_000_000)
    parser.add_argument("--measure", action="store_true", help="run one warm-up plus three no-cache dashboard measurements")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--report", default="data/exports/tv3_mart_parity.csv")
    parser.add_argument("--measurements", default="data/exports/tv3_mart_measurements.csv")
    parser.add_argument("--medians", default="data/exports/tv3_mart_measurement_medians.csv")
    args = parser.parse_args()
    if args.max_bq_bytes < 0 or args.repetitions < 1:
        parser.error("--max-bq-bytes must be non-negative and --repetitions must be positive")
    _load_dotenv()

    try:
        parity_records, snapshots = validate(engine=args.engine, max_bq_bytes=args.max_bq_bytes)
        measurements: list[dict[str, Any]] = []
        if args.measure:
            engines = ("duckdb", "bq") if args.engine == "both" else (args.engine,)
            for backend in engines:
                summary = snapshots[backend]["br3_summary"]
                if summary.empty:
                    raise RuntimeError(f"No BR3 offerings available for measurement on {backend}")
                first = summary.sort_values(["code_module", "code_presentation"]).iloc[0]
                selected = (str(first["code_module"]), str(first["code_presentation"]))
                measurements.extend(_measure(backend, args.repetitions, selected))
        import pandas as pd

        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(parity_records).to_csv(report_path, index=False)
        if measurements:
            measurements_path = Path(args.measurements)
            medians_path = Path(args.medians)
            if not measurements_path.is_absolute():
                measurements_path = ROOT / measurements_path
            if not medians_path.is_absolute():
                medians_path = ROOT / medians_path
            measurements_path.parent.mkdir(parents=True, exist_ok=True)
            medians_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(measurements).to_csv(measurements_path, index=False)
            pd.DataFrame(_median_records(measurements)).to_csv(medians_path, index=False)
        print(f"Parity passed: {len(parity_records)} checks. Wrote {report_path.relative_to(ROOT)}")
        return 0
    except Exception as error:
        print(f"TV3 mart parity failed; no new report was written: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
