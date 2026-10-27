"""Benchmark BR1/BR2/BR4/BR6 on a selected BigQuery/PostgreSQL matrix.

Safe commands list the 48 planned cells or estimate the selected 44. The
measurement command requires ``--confirm-m3`` and all twenty question files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import traceback
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from numbers import Integral, Real
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

ENGINES = ("bq", "pg")
SCALES = (1, 5)
LAYOUTS = ("star", "3nf", "wide")
LAYOUT_LABELS = {
    "star": "star",
    "3nf": "partial normalization",
    "wide": "wide",
}
WORKLOADS = ("br1_q07", "br2_q09", "br4_q14", "br6_q18")
RUNS_DEFAULT = 5
RANDOM_SEED = 39
QUESTIONS_DIR = ROOT / "sql" / "questions"
QUESTION_BY_WORKLOAD = {"br1_q07": 7, "br2_q09": 9, "br4_q14": 14, "br6_q18": 18}

PLANNED_MATRIX = tuple(
    (engine, scale, layout, workload)
    for engine in ENGINES
    for scale in SCALES
    for layout in LAYOUTS
    for workload in WORKLOADS
)
EXCLUDED_MATRIX = tuple(row for row in PLANNED_MATRIX if row[:3] == ("bq", 5, "wide"))
MATRIX = tuple(row for row in PLANNED_MATRIX if row not in EXCLUDED_MATRIX)
BQ_MATRIX = tuple(row for row in MATRIX if row[0] == "bq")

REFERENCE_1X = {
    "br1_q07": {
        "tma_nonbanked_submissions": 97088,
        "late_submissions": 16320,
        "late_rate_pct": 16.8,
    },
    "br2_q09": {
        "activity_type": "oucontent",
        "activity_type_total_clicks": 11206803,
        "global_total_clicks": 39605099,
        "global_activity_type_click_share_pct": 28.3,
    },
    "br4_q14": {
        "n_enrolled": 27250,
        "n_listed": 3958,
        "n_true_positives": 3189,
        "precision_pct": 80.6,
        "recall_pct": 26.9,
        "baseline_bad_rate_pct": 43.5,
    },
    "br6_q18": {
        "n_students_0_10": 615,
        "n_enrollments_0_10": 615,
        "n_students_0_10_label": "615",
        "rate_0_10_pct": 41.1,
        "n_students_90_100": 436,
        "n_enrollments_90_100": 436,
        "n_students_90_100_label": "436",
        "rate_90_100_pct": 63.3,
        "gap_pp": 22.2,
    },
}
COUNT_COLUMNS = {
    "br1_q07": ("tma_nonbanked_submissions", "late_submissions"),
    "br2_q09": ("activity_type_total_clicks", "global_total_clicks"),
    "br4_q14": ("n_enrolled", "n_listed", "n_true_positives"),
    "br6_q18": (
        "n_students_0_10", "n_enrollments_0_10",
        "n_students_90_100", "n_enrollments_90_100",
    ),
}
DERIVED_COUNT_LABELS = {
    "br6_q18": {
        "n_students_0_10_label": "n_students_0_10",
        "n_students_90_100_label": "n_students_90_100",
    },
}
REFERENCE_SOURCES = {
    "br1_q07": ("tests/test_postgres.py", "tests/test_warehouse.py"),
    "br2_q09": ("tests/test_postgres.py", "sql/questions/q09.sql"),
    "br4_q14": ("tests/test_student_week.py", "tests/test_tv2_sql.py"),
    "br6_q18": ("sql/questions/q18.sql", "docs/br6_validation.md"),
}
REQUIRED_RELATIONS_BY_LAYOUT = {
    "star": (
        "fact_submission", "dim_assessment", "fact_vle_daily", "dim_vle_site",
        "fact_student_week", "fact_enrollment", "dim_student",
    ),
    "3nf": (
        "fact_submission", "dim_assessment", "fact_vle_daily", "dim_vle_site",
        "fact_student_week", "fact_enrollment", "dim_student",
    ),
    "wide": ("wide_submission", "wide_vle_daily", "wide_student_week", "wide_enrollment"),
}

RAW_FIELDS = (
    "engine",
    "scale",
    "layout",
    "workload",
    "phase",
    "repeat",
    "round_order",
    "order_index",
    "client_elapsed_seconds",
    "server_elapsed_seconds",
    "elapsed_seconds",
    "bytes_scanned",
    "bytes_billed",
    "job_id",
    "row_count",
    "result_hash",
    "cache_hit",
    "target",
    "sql_file",
    "status",
    "error_type",
    "error_message",
)
SUMMARY_FIELDS = (
    "query",
    "engine",
    "scale",
    "layout",
    "workload",
    "runs",
    "measured_runs",
    "median_s",
    "min_elapsed_seconds",
    "median_elapsed_seconds",
    "max_elapsed_seconds",
    "iqr_elapsed_seconds",
    "median_server_elapsed_seconds",
    "min_server_elapsed_seconds",
    "max_server_elapsed_seconds",
    "iqr_server_elapsed_seconds",
    "median_bytes_scanned",
    "min_bytes_scanned",
    "max_bytes_scanned",
    "iqr_bytes_scanned",
    "median_bytes_billed",
    "min_bytes_billed",
    "max_bytes_billed",
    "iqr_bytes_billed",
    "row_count",
    "result_hash",
    "oracle_hash_match",
    "repetition_hashes_match",
    "matrix_hashes_match_at_scale",
    "target",
    "sql_file",
)


def sql_file(engine: str, layout: str, workload: str) -> Path:
    return ROOT / "sql" / "bench" / engine / layout / f"{workload}.sql"


def missing_sql_files(rows=MATRIX) -> list[Path]:
    missing = []
    seen = set()
    for engine, _, layout, workload in rows:
        path = sql_file(engine, layout, workload)
        if not path.is_file() and path not in seen:
            missing.append(path)
            seen.add(path)
    return missing


def missing_question_files() -> list[Path]:
    return [QUESTIONS_DIR / f"q{number:02d}.sql" for number in range(1, 21)
            if not (QUESTIONS_DIR / f"q{number:02d}.sql").is_file()]


def target_for(engine: str, scale: int, layout: str) -> str:
    if scale < 1:
        raise ValueError("scale must be a positive integer")
    if layout not in LAYOUTS:
        raise ValueError(f"Unsupported layout: {layout}")
    if engine == "pg":
        if layout == "star":
            return "public" if scale == 1 else f"x{scale}"
        if layout == "3nf":
            return "three_nf" if scale == 1 else f"three_nf_x{scale}"
        return "wide" if scale == 1 else f"wide_x{scale}"

    base = os.getenv("BQ_DATASET", "oulad").strip()
    if not base:
        raise RuntimeError("BQ_DATASET must not be empty")
    if layout == "star":
        dataset = base if scale == 1 else f"{base}_{scale}x"
    elif layout == "3nf":
        dataset = f"{base}_3nf" if scale == 1 else f"{base}_3nf_{scale}x"
    else:
        dataset = f"{base}_wide" if scale == 1 else f"{base}_wide_{scale}x"
    project = os.getenv("GCP_PROJECT_ID", "<GCP_PROJECT_ID>").strip()
    return f"{project}.{dataset}"


def display_layout(layout: str) -> str:
    """Use a clear label while retaining the technical layout ID in files."""
    if layout not in LAYOUT_LABELS:
        raise ValueError(f"Unsupported layout: {layout}")
    if layout == "3nf":
        return f"{LAYOUT_LABELS[layout]} [ID: 3nf]"
    return LAYOUT_LABELS[layout]


def list_matrix() -> None:
    headings = ("engine", "scale", "layout", "workload", "target", "SQL file", "selection")
    rows = []
    for engine, scale, layout, workload in PLANNED_MATRIX:
        path = sql_file(engine, layout, workload)
        key = (engine, scale, layout, workload)
        rows.append((
            engine,
            f"{scale}x",
            display_layout(layout),
            workload,
            target_for(engine, scale, layout),
            path.relative_to(ROOT).as_posix(),
            ("excluded: 5x wide" if key in EXCLUDED_MATRIX
             else "selected" if path.is_file() else "selected SQL missing"),
        ))

    widths = [max(len(headings[i]), *(len(str(row[i])) for row in rows)) for i in range(len(headings))]
    print(" | ".join(headings[i].ljust(widths[i]) for i in range(len(headings))))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headings))))
    print(
        f"\n{len(PLANNED_MATRIX)} planned combinations; {len(MATRIX)} selected; "
        f"{len(MATRIX) * (RUNS_DEFAULT + 1)} matrix executions "
        f"(one warm-up plus {RUNS_DEFAULT} measured runs)."
    )


def _bigquery_project() -> str:
    project = os.getenv("GCP_PROJECT_ID", "").strip()
    if not project or project.lower() in {"dien-project-id-vao-day", "your-project-id"}:
        raise RuntimeError("GCP_PROJECT_ID is missing or still has the example value")
    return project


def _new_bigquery_client():
    from google.cloud import bigquery

    project = _bigquery_project()
    return bigquery, bigquery.Client(project=project, location=os.getenv("BQ_LOCATION", "US"))


def estimate_bq(runs: int = RUNS_DEFAULT, client=None,
                bigquery_module=None) -> list[dict[str, Any]]:
    """Dry-run each selected BigQuery variant; no result rows are read."""
    if runs < 1:
        raise ValueError("runs must be a positive integer")
    missing = missing_sql_files(BQ_MATRIX)
    if missing:
        paths = "\n".join(f"  - {path.relative_to(ROOT)}" for path in missing)
        raise RuntimeError(f"BigQuery SQL variants are missing:\n{paths}")

    owns_client = client is None
    if bigquery_module is None:
        if owns_client:
            bigquery, client = _new_bigquery_client()
        else:
            from google.cloud import bigquery
    else:
        bigquery = bigquery_module

    estimates = []
    for engine, scale, layout, workload in BQ_MATRIX:
        path = sql_file(engine, layout, workload)
        config = bigquery.QueryJobConfig(
            default_dataset=target_for(engine, scale, layout),
            dry_run=True,
            use_query_cache=False,
            use_legacy_sql=False,
        )
        try:
            job = client.query(path.read_text(encoding="utf-8"), job_config=config)
        except Exception as exc:
            raise RuntimeError(
                f"BigQuery dry run failed for {scale}x/{layout}/{workload}: {exc}"
            ) from exc
        if job.total_bytes_processed is None:
            raise RuntimeError(
                f"BigQuery dry run returned no byte estimate for {scale}x/{layout}/{workload}"
            )
        estimates.append({
            "engine": engine,
            "scale": scale,
            "layout": layout,
            "workload": workload,
            "bytes_per_execution": int(job.total_bytes_processed),
            "planned_executions": runs + 1,
            "planned_bytes": int(job.total_bytes_processed) * (runs + 1),
            "target": target_for(engine, scale, layout),
            "sql_file": path.relative_to(ROOT).as_posix(),
        })
    if owns_client:
        close = getattr(client, "close", None)
        if close is not None:
            close()
    return estimates


def print_estimates(estimates: list[dict[str, Any]], runs: int = RUNS_DEFAULT) -> None:
    print("BigQuery dry-run estimate (bytes processed per execution)")
    for row in estimates:
        mib = row["bytes_per_execution"] / (1024 * 1024)
        print(
            f"{row['scale']}x {display_layout(row['layout']):<36} {row['workload']:<9} "
            f"{row['bytes_per_execution']:>14,} bytes ({mib:,.2f} MiB)"
        )
    one_pass = sum(row["bytes_per_execution"] for row in estimates)
    full_run = one_pass * (runs + 1)
    print(f"\nOne execution of all BigQuery variants: {one_pass:,} bytes processed.")
    print(
        f"Warm-up plus {runs} measured executions: {full_run:,} estimated bytes processed "
        f"({full_run / (1024 * 1024):,.2f} MiB)."
    )
    print("Dry-run estimates are not measured results or a billing quote.")


def _number_text(value: Any) -> str:
    number = Decimal(str(value)).quantize(Decimal("0.000000001"))
    if number == 0:
        return "0"
    return format(number.normalize(), "f")


def _canonical_cell(value: Any) -> str:
    if value is None:
        return "null"
    try:
        import pandas as pd

        if bool(pd.isna(value)):
            return "null"
    except ImportError:
        try:
            if math.isnan(value):
                return "null"
        except (TypeError, ValueError):
            pass
    except (TypeError, ValueError):
        pass

    if isinstance(value, bool):
        return f"bool:{str(value).lower()}"
    if isinstance(value, Decimal):
        return f"number:{_number_text(value)}"
    if isinstance(value, Integral):
        return f"number:{int(value)}"
    if isinstance(value, Real):
        return f"number:{_number_text(value)}"
    if isinstance(value, (datetime, date)):
        return f"datetime:{value.isoformat()}"
    if isinstance(value, (bytes, bytearray)):
        return f"bytes:{bytes(value).hex()}"
    return f"string:{value}"


def result_hash(frame: Any) -> str:
    """Hash normalized, order-independent rows while retaining duplicate rows."""
    columns = [str(column) for column in frame.columns]
    rows = [[_canonical_cell(value) for value in row]
            for row in frame.itertuples(index=False, name=None)]
    rows.sort(key=lambda row: json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    payload = json.dumps(
        {"columns": columns, "rows": rows},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _plain_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        import pandas as pd

        if bool(pd.isna(value)):
            return None
    except (ImportError, TypeError, ValueError):
        pass
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return float(value)
    return str(value)


def _frame_rows(frame: Any) -> list[dict[str, Any]]:
    columns = [str(column) for column in frame.columns]
    return [dict(zip(columns, row)) for row in frame.itertuples(index=False, name=None)]


def _values_match(actual: list[dict[str, Any]] | None,
                  expected: dict[str, Any] | None) -> bool:
    if actual is None or expected is None or len(actual) != 1:
        return False
    row = actual[0]
    if tuple(row) != tuple(expected):
        return False
    return all(_canonical_cell(row[key]) == _canonical_cell(value)
               for key, value in expected.items())


def _scaled_reference(values: list[dict[str, Any]], workload: str, factor: int) -> dict[str, Any] | None:
    if len(values) != 1:
        return None
    scaled = dict(values[0])
    for column in COUNT_COLUMNS[workload]:
        value = scaled.get(column)
        if value is None:
            continue
        scaled[column] = int(value) * factor
    for label_column, count_column in DERIVED_COUNT_LABELS.get(workload, {}).items():
        count = scaled.get(count_column)
        scaled[label_column] = "n < 30" if count is None or count < 30 else str(int(count))
    return scaled


def _group_variants(scale: int, workload: str) -> set[tuple[str, int, str, str]]:
    return {row for row in MATRIX if row[1] == scale and row[3] == workload}


def warmup_correctness_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Check warm-ups against the 1x reference answer and each scale baseline."""
    warmups = [record for record in records if record["phase"] == "warmup"]
    groups = []
    for workload in WORKLOADS:
        baseline_1x_records = [record for record in warmups if (
            record["engine"], record["scale"], record["layout"], record["workload"]
        ) == ("pg", 1, "star", workload)]
        baseline_5x_records = [record for record in warmups if (
            record["engine"], record["scale"], record["layout"], record["workload"]
        ) == ("pg", 5, "star", workload)]
        baseline_1x = baseline_1x_records[0] if len(baseline_1x_records) == 1 else None
        baseline_5x = baseline_5x_records[0] if len(baseline_5x_records) == 1 else None
        reference_1x_match = bool(
            baseline_1x and _values_match(baseline_1x.get("result_values"), REFERENCE_1X[workload])
        )
        expected_5x = (
            _scaled_reference(baseline_1x["result_values"], workload, 5)
            if baseline_1x else None
        )
        reference_5x_match = bool(
            baseline_5x and _values_match(baseline_5x.get("result_values"), expected_5x)
        )

        for scale, baseline, semantic_match in (
            (1, baseline_1x, reference_1x_match),
            (5, baseline_5x, reference_5x_match),
        ):
            group_rows = [record for record in warmups
                          if record["scale"] == scale and record["workload"] == workload]
            expected = _group_variants(scale, workload)
            variant_map: dict[tuple[str, int, str, str], list[dict[str, Any]]] = {}
            for record in group_rows:
                key = (record["engine"], record["scale"], record["layout"], record["workload"])
                variant_map.setdefault(key, []).append(record)
            missing = sorted(expected - set(variant_map))
            duplicates = sorted(key for key, rows in variant_map.items() if len(rows) != 1)
            variants = []
            for key in sorted(expected & set(variant_map)):
                rows = variant_map[key]
                same_as_baseline = bool(
                    len(rows) == 1 and baseline
                    and rows[0]["result_hash"] == baseline["result_hash"]
                    and rows[0]["row_count"] == baseline["row_count"]
                )
                variants.append({
                    "engine": key[0],
                    "layout": key[2],
                    "warmup_count": len(rows),
                    "status": "passed" if same_as_baseline else "failed",
                    "matches_scale_baseline": same_as_baseline,
                    "row_count": rows[0]["row_count"] if rows else None,
                    "result_hash": rows[0]["result_hash"] if rows else None,
                })
            passed = (
                baseline is not None
                and semantic_match
                and not missing
                and not duplicates
                and len(group_rows) == len(expected)
                and all(item["status"] == "passed" for item in variants)
            )
            groups.append({
                "scale": scale,
                "workload": workload,
                "status": "passed" if passed else "failed",
                "baseline": {"engine": "pg", "layout": "star"},
                "semantic_reference_status": "passed" if semantic_match else "failed",
                "semantic_reference": (
                    REFERENCE_1X[workload] if scale == 1 else expected_5x
                ),
                "scale_replication": ({
                    "factor": 5,
                    "count_columns_scaled": list(COUNT_COLUMNS[workload]),
                    "derived_count_labels": DERIVED_COUNT_LABELS.get(workload, {}),
                    "other_columns_unchanged": True,
                } if scale == 5 else None),
                "reference_source": list(REFERENCE_SOURCES[workload]),
                "expected_variants": len(expected),
                "actual_warmup_records": len(group_rows),
                "missing_variants": [list(key) for key in missing],
                "duplicate_variants": [list(key) for key in duplicates],
                "variants": variants,
            })
    passed = all(group["status"] == "passed" for group in groups)
    return {
        "status": "passed" if passed else "failed",
        "check": "one warm-up per selected variant; 1x PostgreSQL star matches the checked-in reference answer; 5x PostgreSQL star follows explicit count/rate replication rules; every same-scale engine/layout matches its baseline",
        "matrix_executions": len(MATRIX),
        "groups": groups,
    }


def measured_correctness_report(
    records: list[dict[str, Any]], runs: int,
    warmup_report: dict[str, Any],
) -> dict[str, Any]:
    """Require every measured execution to match its checked warm-up baseline."""
    measured = [record for record in records if record["phase"] == "measured"]
    groups = []
    expected_repeats = set(range(1, runs + 1))
    for scale in SCALES:
        for workload in WORKLOADS:
            baseline_rows = [record for record in records if (
                record["phase"], record["engine"], record["scale"],
                record["layout"], record["workload"]
            ) == ("warmup", "pg", scale, "star", workload)]
            baseline = baseline_rows[0] if len(baseline_rows) == 1 else None
            expected = _group_variants(scale, workload)
            group_rows = [record for record in measured
                          if record["scale"] == scale and record["workload"] == workload]
            variant_map: dict[tuple[str, int, str, str], list[dict[str, Any]]] = {}
            for record in group_rows:
                key = (record["engine"], record["scale"], record["layout"], record["workload"])
                variant_map.setdefault(key, []).append(record)
            missing = sorted(expected - set(variant_map))
            variant_checks = []
            for key in sorted(expected & set(variant_map)):
                rows = variant_map[key]
                repeats = {record["repeat"] for record in rows}
                hashes_match = len({record["result_hash"] for record in rows}) == 1
                counts_match = len({record["row_count"] for record in rows}) == 1
                baseline_match = bool(baseline and all(
                    record["result_hash"] == baseline["result_hash"]
                    and record["row_count"] == baseline["row_count"]
                    for record in rows
                ))
                exact_runs = len(rows) == runs and repeats == expected_repeats
                passed = exact_runs and hashes_match and counts_match and baseline_match
                variant_checks.append({
                    "engine": key[0],
                    "layout": key[2],
                    "status": "passed" if passed else "failed",
                    "runs": len(rows),
                    "repeats": sorted(repeats),
                    "hashes_match_within_variant": hashes_match,
                    "row_counts_match_within_variant": counts_match,
                    "every_run_matches_warmup_baseline": baseline_match,
                })
            group_hashes = {record["result_hash"] for record in group_rows}
            group_counts = {record["row_count"] for record in group_rows}
            passed = (
                baseline is not None
                and not missing
                and len(group_rows) == len(expected) * runs
                and all(item["status"] == "passed" for item in variant_checks)
                and len(group_hashes) == 1
                and len(group_counts) == 1
            )
            groups.append({
                "scale": scale,
                "workload": workload,
                "status": "passed" if passed else "failed",
                "expected_runs_per_variant": runs,
                "expected_repeats": sorted(expected_repeats),
                "missing_variants": [list(key) for key in missing],
                "variant_checks": variant_checks,
                "matrix_hashes_match_at_scale": len(group_hashes) == 1,
                "distinct_row_counts": sorted(group_counts),
            })
    passed = warmup_report["status"] == "passed" and all(
        group["status"] == "passed" for group in groups
    )
    return {
        "status": "passed" if passed else "failed",
        "check": "exactly the configured runs per selected variant; every measured row count and result hash matches its warm-up baseline and all variants at the same scale",
        "groups": groups,
    }


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def _stats(values: list[Any]) -> dict[str, float | int | None]:
    present = [float(value) for value in values if value is not None]
    if not present:
        return {"median": None, "min": None, "max": None, "iqr": None}
    return {
        "median": median(present),
        "min": min(present),
        "max": max(present),
        "iqr": (_quantile(present, 0.75) or 0) - (_quantile(present, 0.25) or 0),
    }


def summarize(
    records: list[dict[str, Any]], runs: int,
    warmup_report: dict[str, Any],
) -> list[dict[str, Any]]:
    measured = [record for record in records if record["phase"] == "measured"]
    matrix_hashes: dict[tuple[str, int], set[str]] = {}
    for record in measured:
        matrix_hashes.setdefault((record["workload"], record["scale"]), set()).add(record["result_hash"])
    warmup_status = {
        (group["scale"], group["workload"]): group["status"] == "passed"
        for group in warmup_report["groups"]
    }

    summary = []
    for engine, scale, layout, workload in MATRIX:
        group = [record for record in measured if (
            record["engine"], record["scale"], record["layout"], record["workload"]
        ) == (engine, scale, layout, workload)]
        if not group:
            continue
        client_stats = _stats([row["client_elapsed_seconds"] for row in group])
        server_stats = _stats([row["server_elapsed_seconds"] for row in group])
        scanned_stats = _stats([row["bytes_scanned"] for row in group])
        billed_stats = _stats([row["bytes_billed"] for row in group])
        hashes = {record["result_hash"] for record in group}
        summary.append({
            "query": workload,
            "engine": engine,
            "scale": scale,
            "layout": layout,
            "workload": workload,
            "runs": len(group),
            "measured_runs": len(group),
            "median_s": client_stats["median"],
            "min_elapsed_seconds": client_stats["min"],
            "median_elapsed_seconds": client_stats["median"],
            "max_elapsed_seconds": client_stats["max"],
            "iqr_elapsed_seconds": client_stats["iqr"],
            "median_server_elapsed_seconds": server_stats["median"],
            "min_server_elapsed_seconds": server_stats["min"],
            "max_server_elapsed_seconds": server_stats["max"],
            "iqr_server_elapsed_seconds": server_stats["iqr"],
            "median_bytes_scanned": scanned_stats["median"],
            "min_bytes_scanned": scanned_stats["min"],
            "max_bytes_scanned": scanned_stats["max"],
            "iqr_bytes_scanned": scanned_stats["iqr"],
            "median_bytes_billed": billed_stats["median"],
            "min_bytes_billed": billed_stats["min"],
            "max_bytes_billed": billed_stats["max"],
            "iqr_bytes_billed": billed_stats["iqr"],
            "row_count": group[0]["row_count"],
            "result_hash": group[0]["result_hash"],
            "oracle_hash_match": warmup_status[(scale, workload)],
            "repetition_hashes_match": len(hashes) == 1 and len(group) == runs,
            "matrix_hashes_match_at_scale": len(matrix_hashes[(workload, scale)]) == 1,
            "target": group[0]["target"],
            "sql_file": group[0]["sql_file"],
        })
    return summary


def write_chart_html(summary: list[dict[str, Any]], path: Path, run_id: str) -> None:
    """Write a dependency-free HTML report with inline SVG charts and a data table."""
    panels = []
    colors = {1: "#4c78a8", 5: "#f58518"}
    for workload in WORKLOADS:
        rows = [row for row in summary if row["workload"] == workload]
        if not rows:
            continue
        maximum = max(max(float(row["median_s"]) for row in rows), 1e-12)
        chart_height = 230
        baseline_y = 255
        usable_height = 190
        group_labels = [(engine, layout) for engine in ENGINES for layout in LAYOUTS]
        svg = [
            '<svg viewBox="0 0 960 330" role="img" '
            f'aria-label="Median client elapsed seconds for {html.escape(workload)}">',
            '<line x1="48" y1="255" x2="940" y2="255" stroke="#444" />',
        ]
        for tick in range(1, 5):
            y = baseline_y - (usable_height * tick / 4)
            value = maximum * tick / 4
            svg.append(
                f'<line x1="48" y1="{y:.1f}" x2="940" y2="{y:.1f}" stroke="#e1e5ea" />'
                f'<text x="4" y="{y + 5:.1f}" class="tick">{value:.3g}s</text>'
            )
        for group_index, (engine, layout) in enumerate(group_labels):
            center = 95 + group_index * 140
            match = next((row for row in rows if (
                row["engine"], row["layout"], row["scale"]
            ) == (engine, layout, 1)), None)
            match5 = next((row for row in rows if (
                row["engine"], row["layout"], row["scale"]
            ) == (engine, layout, 5)), None)
            for offset, item, scale in ((-18, match, 1), (18, match5, 5)):
                if item is None:
                    continue
                value = float(item["median_s"])
                height = min(usable_height, value / maximum * usable_height)
                x, y = center + offset - 13, baseline_y - height
                title = html.escape(
                    f"{engine.upper()} {layout} {scale}x: median {value:.6g}s, "
                    f"IQR {item['iqr_elapsed_seconds']:.6g}s, n={item['runs']}"
                )
                svg.append(
                    f'<rect x="{x}" y="{y:.1f}" width="26" height="{height:.1f}" '
                    f'fill="{colors[scale]}"><title>{title}</title></rect>'
                )
            label = html.escape(f"{engine.upper()} / {display_layout(layout)}")
            svg.append(
                f'<text x="{center}" y="275" text-anchor="middle" class="label">{label}</text>'
            )
        svg.append('</svg>')
        panels.append(
            f'<section><h2>{html.escape(workload.upper().replace("_", " "))}</h2>'
            + "\n".join(svg)
            + '</section>'
        )

    table_rows = []
    for row in summary:
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(row['query'])}</td>"
            f"<td>{row['engine'].upper()}</td>"
            f"<td>{row['scale']}x</td>"
            f"<td>{html.escape(display_layout(row['layout']))}</td>"
            f"<td>{row['median_s']:.6g}</td>"
            f"<td>{row['min_elapsed_seconds']:.6g}</td>"
            f"<td>{row['max_elapsed_seconds']:.6g}</td>"
            f"<td>{row['iqr_elapsed_seconds']:.6g}</td>"
            f"<td>{row['runs']}</td>"
            "</tr>"
        )
    run_scope_html = (
        f"<p>Run ID: <code>{html.escape(run_id)}</code>. Coverage: 44 selected of 48 planned cells.</p>"
        "<p>Excluded: the four BigQuery 5x wide workload cells because adding the 5x wide "
        "datasets to existing data would exceed the BigQuery Sandbox 10 GB project storage quota.</p>"
    )
    document = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OULAD layout benchmark</title>
<style>
body{font:15px system-ui,sans-serif;color:#20252b;margin:2rem;max-width:1200px}
h1,h2{color:#172b4d}section{margin:2rem 0;padding:1rem;border:1px solid #dfe3e8;border-radius:8px}
svg{width:100%;height:auto}.tick{font:12px system-ui;fill:#59636e}.label{font:11px system-ui;fill:#20252b}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:.45rem .55rem;border-bottom:1px solid #dfe3e8;text-align:right}
th:first-child,td:first-child,th:nth-child(4),td:nth-child(4){text-align:left}
th{background:#f4f6f8;position:sticky;top:0}.legend span{display:inline-block;margin-right:1.25rem}
.swatch{display:inline-block;width:.8rem;height:.8rem;margin-right:.35rem}
</style>
</head>
<body>
<h1>OULAD layout benchmark</h1>
""" + run_scope_html + """
<p>Bars show median client elapsed time from the prepared client call through full result fetch. Server/job time and billing metrics are in the CSV output.</p>
<p class="legend"><span><i class="swatch" style="background:#4c78a8"></i>1x</span>
<span><i class="swatch" style="background:#f58518"></i>5x</span></p>
""" + "\n".join(panels) + """
<section><h2>Run statistics</h2>
<table><thead><tr><th>Query</th><th>Engine</th><th>Scale</th><th>Layout</th>
<th>Median seconds</th><th>Min</th><th>Max</th><th>IQR</th><th>Runs</th></tr></thead>
<tbody>""" + "\n".join(table_rows) + """</tbody></table></section>
</body></html>
"""
    path.write_text(document, encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_write(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=_plain_value) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _cell_label(key: tuple[str, int, str, str]) -> dict[str, Any]:
    engine, scale, layout, workload = key
    return {"engine": engine, "scale": scale, "layout": layout, "workload": workload}


def _execution_plan(runs: int) -> dict[str, Any]:
    randomizer = random.Random(RANDOM_SEED)
    baseline_order = [
        ("pg", scale, "star", workload)
        for workload in WORKLOADS
        for scale in SCALES
    ]
    baseline_set = set(baseline_order)
    remaining = [key for key in MATRIX if key not in baseline_set]
    randomizer.shuffle(remaining)
    warmup_order = baseline_order + remaining
    measured_rounds = []
    for repeat in range(1, runs + 1):
        order = list(MATRIX)
        randomizer.shuffle(order)
        measured_rounds.append({
            "repeat": repeat,
            "order": [_cell_label(key) for key in order],
        })
    return {
        "random_seed": RANDOM_SEED,
        "warmup_order": [_cell_label(key) for key in warmup_order],
        "measured_rounds": measured_rounds,
    }


def _git_snapshot() -> dict[str, Any]:
    result = {}
    for key, args in (
        ("branch", ["git", "branch", "--show-current"]),
        ("commit", ["git", "rev-parse", "HEAD"]),
        ("working_tree", ["git", "status", "--short"]),
    ):
        try:
            completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                       timeout=5, check=False)
            result[key] = completed.stdout.strip() if completed.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            result[key] = None
    return result


def _configuration_snapshot(runs: int) -> dict[str, Any]:
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "git": _git_snapshot(),
        "script_sha256": script_hash,
        "environment": {
            "gcp_project_id": os.getenv("GCP_PROJECT_ID"),
            "bq_dataset": os.getenv("BQ_DATASET", "oulad"),
            "bq_location": os.getenv("BQ_LOCATION", "US"),
            "postgres_host": os.getenv("POSTGRES_HOST", "postgres"),
            "postgres_port": os.getenv("POSTGRES_PORT", "5432"),
            "postgres_database": os.getenv("POSTGRES_DB", "oulad"),
            "postgres_user": os.getenv("POSTGRES_USER", "oulad"),
        },
        "protocol": {
            "runs": runs,
            "warmups_per_variant": 1,
            "selected_matrix_executions": len(MATRIX) * (runs + 1),
            "random_seed": RANDOM_SEED,
            "bigquery_use_query_cache": False,
            "bigquery_cache_hit_expected": False,
            "postgres_index_policy": "primary-key indexes only; read-only check, no index changes",
            "client_elapsed_boundary": "prepared client call through complete result fetch",
        },
    }


def _postgres_preflight(connection) -> dict[str, Any]:
    server = connection.execute(
        "SELECT current_database(), current_user, current_setting('server_version'), "
        "current_setting('server_encoding'), current_setting('shared_buffers'), "
        "current_setting('work_mem')"
    ).fetchone()
    schema_layouts = {
        target_for("pg", scale, layout): (scale, layout)
        for engine, scale, layout, _ in MATRIX if engine == "pg"
    }
    schemas = []
    analyze_started_at = _utc_now()
    for schema, (scale, layout) in sorted(schema_layouts.items()):
        relations = connection.execute(
            "SELECT c.relname, c.relkind FROM pg_class AS c "
            "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'v', 'm', 'f') "
            "ORDER BY c.relname",
            (schema,),
        ).fetchall()
        tables = [(name,) for name, kind in relations if kind in {"r", "p"}]
        actual_relations = {name for name, _ in relations}
        missing_required = sorted(
            set(REQUIRED_RELATIONS_BY_LAYOUT[layout]) - actual_relations
        )
        for (table,) in tables:
            quoted_schema = schema.replace('"', '""')
            quoted_table = table.replace('"', '""')
            connection.execute(f'ANALYZE "{quoted_schema}"."{quoted_table}"')
        index_rows = connection.execute(
            "SELECT table_class.relname, index_class.relname, index_meta.indisprimary, "
            "index_meta.indisvalid, pg_get_indexdef(index_meta.indexrelid) "
            "FROM pg_index AS index_meta "
            "JOIN pg_class AS table_class ON table_class.oid = index_meta.indrelid "
            "JOIN pg_namespace AS schema_meta ON schema_meta.oid = table_class.relnamespace "
            "JOIN pg_class AS index_class ON index_class.oid = index_meta.indexrelid "
            "WHERE schema_meta.nspname = %s ORDER BY table_class.relname, index_class.relname",
            (schema,),
        ).fetchall()
        table_stats = connection.execute(
            "SELECT relname, n_live_tup, n_dead_tup, last_analyze, last_autoanalyze, "
            "pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) "
            "FROM pg_stat_user_tables WHERE schemaname = %s ORDER BY relname",
            (schema,),
        ).fetchall()
        primary_tables = {row[0] for row in index_rows if row[2]}
        non_primary = [
            {"table": row[0], "index": row[1], "definition": row[4], "valid": row[3]}
            for row in index_rows if not row[2]
        ]
        invalid_indexes = [
            {"table": row[0], "index": row[1], "definition": row[4]}
            for row in index_rows if not row[3]
        ]
        missing_primary = sorted(table[0] for table in tables if table[0] not in primary_tables)
        estimated_live_rows = sum(int(row[1] or 0) for row in table_stats)
        total_relation_bytes = sum(int(row[5] or 0) for row in table_stats)
        schema_passed = (
            bool(tables) and not missing_required and not non_primary
            and not invalid_indexes and not missing_primary
        )
        schemas.append({
            "schema": schema,
            "scale": scale,
            "layout": layout,
            "status": "passed" if schema_passed else "failed",
            "required_relations": list(REQUIRED_RELATIONS_BY_LAYOUT[layout]),
            "missing_required_relations": missing_required,
            "table_count": len(tables),
            "tables_without_primary_key": missing_primary,
            "index_count": len(index_rows),
            "primary_key_index_count": sum(1 for row in index_rows if row[2]),
            "indexes": [
                {
                    "table": row[0],
                    "name": row[1],
                    "is_primary": row[2],
                    "is_valid": row[3],
                    "definition": row[4],
                }
                for row in index_rows
            ],
            "non_primary_indexes": non_primary,
            "invalid_indexes": invalid_indexes,
            "stats_kind": "estimates from pg_stat_user_tables after ANALYZE",
            "estimated_live_rows": estimated_live_rows,
            "estimated_total_relation_bytes": total_relation_bytes,
            "table_stats": [
                {
                    "table": row[0], "estimated_live_rows": row[1],
                    "estimated_dead_rows": row[2], "last_analyze": row[3],
                    "last_autoanalyze": row[4], "total_bytes": row[5],
                }
                for row in table_stats
            ],
        })
    return {
        "status": "passed" if all(row["status"] == "passed" for row in schemas) else "failed",
        "captured_at_utc": _utc_now(),
        "analyze_started_at_utc": analyze_started_at,
        "analyze_completed_at_utc": _utc_now(),
        "analyze_performed": True,
        "server": {
            "database": server[0], "user": server[1],
            "version": server[2], "encoding": server[3],
            "shared_buffers": server[4], "work_mem": server[5],
        },
        "schemas": schemas,
    }


def _bigquery_snapshot(client) -> dict[str, Any]:
    targets = sorted({target_for("bq", scale, layout) for engine, scale, layout, _ in MATRIX
                      if engine == "bq"})
    target_snapshots = []
    for target in targets:
        dataset = client.get_dataset(target)
        objects = []
        for table_reference in client.list_tables(target):
            table = client.get_table(table_reference)
            objects.append({
                "table": table.table_id,
                "type": table.table_type,
                "metadata_row_count": getattr(table, "num_rows", None),
                "metadata_bytes": getattr(table, "num_bytes", None),
                "created_at": getattr(table, "created", None),
                "modified_at": getattr(table, "modified", None),
            })
        row_values = [item["metadata_row_count"] for item in objects
                      if item["metadata_row_count"] is not None]
        byte_values = [item["metadata_bytes"] for item in objects
                       if item["metadata_bytes"] is not None]
        target_snapshots.append({
            "target": target,
            "location": getattr(dataset, "location", None),
            "created_at": getattr(dataset, "created", None),
            "modified_at": getattr(dataset, "modified", None),
            "object_count": len(objects),
            "metadata_row_count_total": sum(row_values),
            "metadata_bytes_total": sum(byte_values),
            "stats_kind": "BigQuery table metadata; view values may be unset or zero",
            "objects": objects,
        })
    return {
        "status": "passed",
        "captured_at_utc": _utc_now(),
        "targets": target_snapshots,
    }


def _engine_versions(executor, postgres_server_version: str | None = None) -> dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version

    package_versions = {}
    for package in ("google-cloud-bigquery", "google-api-core", "pandas", "psycopg"):
        try:
            package_versions[package] = version(package)
        except PackageNotFoundError:
            package_versions[package] = None
    try:
        import psycopg

        libpq_version = psycopg.pq.version()
    except (ImportError, AttributeError):
        libpq_version = None
    return {
        "python": platform.python_version(),
        "postgresql_server": postgres_server_version,
        "bigquery_client_module": getattr(executor.bigquery_module, "__name__", None),
        "libraries": package_versions,
        "libpq_version_number": libpq_version,
    }


def _artifact_manifest(run_id: str, runs: int) -> dict[str, Any]:
    return {
        "status": "incomplete",
        "run_id": run_id,
        "started_at_utc": _utc_now(),
        "coverage": {
            "planned": len(PLANNED_MATRIX),
            "selected": len(MATRIX),
            "excluded": [
                {
                    **_cell_label(key),
                    "reason": (
                        "BigQuery Sandbox project storage quota is 10 GB; adding the 5x wide "
                        "datasets to existing data would exceed the limit"
                    ),
                }
                for key in EXCLUDED_MATRIX
            ],
        },
        "configuration": _configuration_snapshot(runs),
        "preflight": {"status": "incomplete"},
        "execution_plan": _execution_plan(runs),
        "progress": {"completed_executions": 0, "planned_executions": len(MATRIX) * (runs + 1)},
        "artifacts": {
            "raw_csv": "raw.csv",
            "medians_csv": "medians.csv",
            "correctness_json": "correctness.json",
            "chart_html": "chart.html",
        },
    }


def _raw_row(record: dict[str, Any]) -> dict[str, Any]:
    return {field: _plain_value(record.get(field)) for field in RAW_FIELDS}


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def run_benchmark(output_dir: Path, runs: int = RUNS_DEFAULT) -> tuple[Path, Path, Path, Path]:
    if runs < 1:
        raise ValueError("--runs must be a positive integer")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    run_dir = output_dir / run_id
    run_dir.mkdir()
    manifest_path = run_dir / "manifest.json"
    raw_path = run_dir / "raw.csv"
    medians_path = run_dir / "medians.csv"
    chart_path = run_dir / "chart.html"
    correctness_path = run_dir / "correctness.json"
    diagnostics_path = run_dir / "diagnostics.txt"
    manifest = _artifact_manifest(run_id, runs)
    _json_write(manifest_path, manifest)
    _json_write(correctness_path, {"status": "incomplete", "stage": "preflight"})

    records: list[dict[str, Any]] = []
    executor = None
    close_errors = []
    try:
        with raw_path.open("x", newline="", encoding="utf-8-sig") as raw_file:
            writer = csv.DictWriter(raw_file, fieldnames=RAW_FIELDS)
            writer.writeheader()
            raw_file.flush()

            missing_sql = missing_sql_files()
            missing_questions = missing_question_files()
            missing_oracles = [
                QUESTIONS_DIR / f"q{QUESTION_BY_WORKLOAD[workload]:02d}.sql"
                for workload in WORKLOADS
                if not (QUESTIONS_DIR / f"q{QUESTION_BY_WORKLOAD[workload]:02d}.sql").is_file()
            ]
            manifest["preflight"] = {
                "status": "failed" if missing_sql or missing_questions or missing_oracles else "passed",
                "captured_at_utc": _utc_now(),
                "m3_question_files_missing": [path.relative_to(ROOT).as_posix() for path in missing_questions],
                "canonical_oracle_files_missing": [path.relative_to(ROOT).as_posix() for path in missing_oracles],
                "selected_sql_files_missing": [path.relative_to(ROOT).as_posix() for path in missing_sql],
            }
            _json_write(manifest_path, manifest)
            if missing_sql or missing_questions or missing_oracles:
                details = []
                if missing_questions:
                    details.append("M3 question-file gate is incomplete: " + ", ".join(
                        path.relative_to(ROOT).as_posix() for path in missing_questions
                    ))
                if missing_oracles:
                    details.append("canonical oracle files are missing: " + ", ".join(
                        path.relative_to(ROOT).as_posix() for path in missing_oracles
                    ))
                if missing_sql:
                    details.append("selected benchmark SQL files are missing: " + ", ".join(
                        path.relative_to(ROOT).as_posix() for path in missing_sql
                    ))
                raise RuntimeError("Refusing to measure; " + "; ".join(details))

            sql_text = {
                key: sql_file(key[0], key[2], key[3]).read_text(encoding="utf-8")
                for key in MATRIX
            }
            selected_sql_paths = sorted({
                sql_file(engine, layout, workload)
                for engine, _, layout, workload in MATRIX
            }, key=lambda path: path.as_posix())
            manifest["configuration"]["selected_sql_sha256"] = {
                path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in selected_sql_paths
            }
            manifest["configuration"]["question_sql_sha256"] = {
                (QUESTIONS_DIR / f"q{number:02d}.sql").relative_to(ROOT).as_posix():
                hashlib.sha256((QUESTIONS_DIR / f"q{number:02d}.sql").read_bytes()).hexdigest()
                for number in range(1, 21)
            }
            from run_sql import BenchmarkExecutor

            executor = BenchmarkExecutor()
            pg_snapshot = _postgres_preflight(executor.postgres_connection)
            manifest["preflight"]["postgres"] = pg_snapshot
            manifest["engine_versions"] = _engine_versions(
                executor, postgres_server_version=pg_snapshot["server"]["version"]
            )
            if pg_snapshot["status"] != "passed":
                manifest["preflight"]["status"] = "failed"
                _json_write(manifest_path, manifest)
                failed_targets = [
                    {
                        "target": row["schema"],
                        "missing_required_relations": row["missing_required_relations"],
                        "tables_without_primary_key": row["tables_without_primary_key"],
                        "non_primary_indexes": row["non_primary_indexes"],
                        "invalid_indexes": row["invalid_indexes"],
                    }
                    for row in pg_snapshot["schemas"] if row["status"] != "passed"
                ]
                raise RuntimeError(
                    "PostgreSQL target/index preflight failed; benchmark targets must contain "
                    "all required relations and only primary-key indexes. No indexes were altered. "
                    + json.dumps(failed_targets, ensure_ascii=False, default=_plain_value)
                )

            print("Running selected BigQuery dry-run preflight...")
            estimates = estimate_bq(
                runs=runs,
                client=executor.bigquery_client,
                bigquery_module=executor.bigquery_module,
            )
            print_estimates(estimates, runs=runs)
            manifest["preflight"]["bigquery"] = {
                "status": "incomplete",
                "captured_at_utc": _utc_now(),
                "query_cache_disabled": True,
                "estimates": estimates,
                "one_execution_bytes": sum(row["bytes_per_execution"] for row in estimates),
                "planned_bytes_with_warmups_and_measured_runs": sum(
                    row["planned_bytes"] for row in estimates
                ),
            }
            bq_snapshot = _bigquery_snapshot(executor.bigquery_client)
            manifest["preflight"]["bigquery"]["status"] = "passed"
            manifest["preflight"]["bigquery"]["target_snapshots"] = bq_snapshot
            bq_target_scale_layouts = {
                target_for("bq", scale, layout): (scale, layout)
                for engine, scale, layout, _ in MATRIX if engine == "bq"
            }
            manifest["source_snapshot"] = {
                "snapshot_id": f"{run_id}-preflight-metadata",
                "snapshot_kind": "preflight metadata capture; source tables are not transactionally frozen",
                "captured_at_utc": _utc_now(),
                "targets": [
                    {
                        "engine": "pg",
                        "target": target["schema"],
                        "scale": target["scale"],
                        "layout": target["layout"],
                        "row_count": target["estimated_live_rows"],
                        "bytes": target["estimated_total_relation_bytes"],
                        "stats_kind": target["stats_kind"],
                    }
                    for target in pg_snapshot["schemas"]
                ] + [
                    {
                        "engine": "bq",
                        "target": target["target"],
                        "scale": bq_target_scale_layouts[target["target"]][0],
                        "layout": bq_target_scale_layouts[target["target"]][1],
                        "row_count": target["metadata_row_count_total"],
                        "bytes": target["metadata_bytes_total"],
                        "stats_kind": target["stats_kind"],
                    }
                    for target in bq_snapshot["targets"]
                ],
            }
            manifest["preflight"]["measurement_ready"] = True
            _json_write(manifest_path, manifest)

            plan = manifest["execution_plan"]

            def execute_variant(key: tuple[str, int, str, str], phase: str,
                                repeat: int, round_order: int, order_index: int) -> dict[str, Any]:
                engine, scale, layout, workload = key
                query = sql_text[key]
                path = sql_file(engine, layout, workload)
                target = target_for(engine, scale, layout)
                started = time.perf_counter()
                frame = None
                metrics = {}
                try:
                    frame, target, metrics = executor.execute(
                        query,
                        engine=engine,
                        scale=scale,
                        layout=layout,
                        use_query_cache=False,
                    )
                    client_elapsed = metrics.get("client_elapsed_seconds")
                    if client_elapsed is None:
                        raise RuntimeError("Prepared executor did not report client_elapsed_seconds")
                    server_elapsed = metrics.get("server_elapsed_seconds")
                    cache_hit = metrics.get("cache_hit")
                    bytes_scanned = metrics.get("bytes_processed")
                    bytes_billed = metrics.get("bytes_billed")
                    job_id = metrics.get("job_id")
                    if engine == "bq" and cache_hit is not False:
                        raise RuntimeError(
                            f"BigQuery cache status was not false (cache_hit={cache_hit!r}) "
                            f"for {scale}x/{layout}/{workload}"
                        )
                except Exception as exc:
                    client_elapsed = metrics.get("client_elapsed_seconds")
                    if client_elapsed is None:
                        client_elapsed = time.perf_counter() - started
                    record = {
                        "engine": engine, "scale": scale, "layout": layout,
                        "workload": workload, "phase": phase, "repeat": repeat,
                        "round_order": round_order, "order_index": order_index,
                        "client_elapsed_seconds": client_elapsed,
                        "server_elapsed_seconds": metrics.get("server_elapsed_seconds"),
                        "elapsed_seconds": client_elapsed,
                        "bytes_scanned": metrics.get("bytes_processed"),
                        "bytes_billed": metrics.get("bytes_billed"),
                        "job_id": metrics.get("job_id"),
                        "row_count": len(frame) if frame is not None else None,
                        "result_hash": result_hash(frame) if frame is not None else None,
                        "cache_hit": metrics.get("cache_hit"),
                        "target": target, "sql_file": path.relative_to(ROOT).as_posix(),
                        "status": "failed", "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                    records.append(record)
                    writer.writerow(_raw_row(record))
                    raw_file.flush()
                    raise

                record = {
                    "engine": engine, "scale": scale, "layout": layout,
                    "workload": workload, "phase": phase, "repeat": repeat,
                    "round_order": round_order, "order_index": order_index,
                    "client_elapsed_seconds": float(client_elapsed),
                    "server_elapsed_seconds": server_elapsed,
                    "elapsed_seconds": float(client_elapsed),
                    "bytes_scanned": bytes_scanned, "bytes_billed": bytes_billed,
                    "job_id": job_id, "row_count": len(frame),
                    "result_hash": result_hash(frame), "cache_hit": cache_hit,
                    "target": target, "sql_file": path.relative_to(ROOT).as_posix(),
                    "status": "success", "error_type": None, "error_message": None,
                    "result_values": _frame_rows(frame),
                }
                records.append(record)
                writer.writerow(_raw_row(record))
                raw_file.flush()
                manifest["progress"]["completed_executions"] += 1
                _json_write(manifest_path, manifest)
                print(
                    f"{engine} {scale}x {display_layout(layout):<38} {workload:<9} "
                    f"{phase:<8} client {record['client_elapsed_seconds']:.3f}s, "
                    f"{record['row_count']} rows"
                )
                return record

            warmup_order = [
                (entry["engine"], entry["scale"], entry["layout"], entry["workload"])
                for entry in plan["warmup_order"]
            ]
            for index, key in enumerate(warmup_order):
                execute_variant(key, "warmup", 0, 0, index)

            warmup_report = warmup_correctness_report(records)
            correctness = {
                "status": "incomplete" if warmup_report["status"] == "passed" else "failed",
                "warmup": warmup_report,
                "measured": {"status": "incomplete", "check": "measured rounds have not completed"},
            }
            _json_write(correctness_path, correctness)
            if warmup_report["status"] != "passed":
                failed = [f"{row['scale']}x/{row['workload']}" for row in warmup_report["groups"]
                          if row["status"] != "passed"]
                raise RuntimeError("Warm-up correctness gate failed for " + ", ".join(failed))

            for round_info in plan["measured_rounds"]:
                repeat = round_info["repeat"]
                for index, item in enumerate(round_info["order"]):
                    key = (item["engine"], item["scale"], item["layout"], item["workload"])
                    execute_variant(key, "measured", repeat, repeat, index)

            measured_report = measured_correctness_report(records, runs, warmup_report)
            correctness = {
                "status": measured_report["status"],
                "warmup": warmup_report,
                "measured": measured_report,
            }
            _json_write(correctness_path, correctness)
            if measured_report["status"] != "passed":
                failed = [f"{row['scale']}x/{row['workload']}" for row in measured_report["groups"]
                          if row["status"] != "passed"]
                raise RuntimeError("Measured correctness gate failed for " + ", ".join(failed))

            summary = summarize(records, runs, warmup_report)
            _write_csv(medians_path, summary, SUMMARY_FIELDS)
            temporary_chart = chart_path.with_name(chart_path.name + ".tmp")
            write_chart_html(summary, temporary_chart, run_id)
            temporary_chart.replace(chart_path)

        executor.close()
        executor = None

        completed_at = _utc_now()
        manifest["status"] = "success"
        manifest["completed_at_utc"] = completed_at
        manifest["preflight"]["status"] = "passed"
        manifest["artifacts"] = {
            "raw_csv": "raw.csv",
            "medians_csv": "medians.csv",
            "correctness_json": "correctness.json",
            "chart_html": "chart.html",
        }
        manifest["correctness"] = "passed"
        _json_write(manifest_path, manifest)
        _json_write(output_dir / "latest_success.json", {
            "run_id": run_id,
            "completed_at_utc": completed_at,
            "manifest": f"{run_id}/manifest.json",
        })
        return raw_path, medians_path, chart_path, correctness_path
    except BaseException as exc:
        is_interrupt = isinstance(exc, KeyboardInterrupt)
        diagnostics_path.write_text(traceback.format_exc(), encoding="utf-8")
        failure = {
            "type": type(exc).__name__,
            "message": str(exc),
            "diagnostics": "diagnostics.txt",
            "at_utc": _utc_now(),
        }
        if not manifest.get("preflight", {}).get("measurement_ready", False):
            manifest.setdefault("preflight", {})["status"] = "failed"
        manifest["status"] = "incomplete" if is_interrupt else "failed"
        manifest["failure"] = failure
        manifest["completed_at_utc"] = None if is_interrupt else _utc_now()
        manifest["artifacts"] = {
            key: name for key, name, path in (
                ("raw_csv", "raw.csv", raw_path),
                ("correctness_json", "correctness.json", correctness_path),
                ("diagnostics", "diagnostics.txt", diagnostics_path),
            ) if path.is_file()
        }
        _json_write(manifest_path, manifest)
        try:
            correctness = json.loads(correctness_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            correctness = {}
        correctness["status"] = "incomplete" if is_interrupt else "failed"
        correctness["failure"] = failure
        _json_write(correctness_path, correctness)
        for artifact in (medians_path, chart_path,
                         medians_path.with_name(medians_path.name + ".tmp"),
                         chart_path.with_name(chart_path.name + ".tmp")):
            try:
                artifact.unlink(missing_ok=True)
            except OSError:
                pass
        if executor is not None:
            try:
                executor.close()
            except Exception as close_exc:
                close_errors.append(str(close_exc))
        if close_errors:
            failure["close_errors"] = close_errors
            _json_write(manifest_path, manifest)
        if is_interrupt:
            raise
        raise RuntimeError(
            f"Benchmark failed; raw and correctness diagnostics are in {run_dir}. {exc}"
        ) from exc


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("matrix", help="list the planned and selected query/layout combinations")
    estimate_parser = commands.add_parser(
        "estimate-bq", help="dry-run selected BigQuery variants and estimate bytes processed"
    )
    estimate_parser.add_argument("--runs", type=_positive_int, default=RUNS_DEFAULT,
                                 help=f"measured runs per query (default: {RUNS_DEFAULT})")

    run_parser = commands.add_parser("run", help="run the selected layout benchmark")
    run_parser.add_argument(
        "--confirm-m3",
        action="store_true",
        required=True,
        help="assert the checklist M3 gate is met; all q01.sql through q20.sql must also exist",
    )
    run_parser.add_argument(
        "--output-dir",
        default="bench/results",
        help="parent directory for run folders (default: bench/results)",
    )
    run_parser.add_argument(
        "--runs", type=_positive_int, default=RUNS_DEFAULT,
        help=f"measured runs per selected query (default: {RUNS_DEFAULT})",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "matrix":
            list_matrix()
            return 0
        if args.command == "estimate-bq":
            print_estimates(estimate_bq(runs=args.runs), runs=args.runs)
            return 0
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = ROOT / output_dir
        raw_path, medians_path, chart_path, correctness_path = run_benchmark(
            output_dir, runs=args.runs
        )
    except (RuntimeError, FileNotFoundError) as exc:
        parser.exit(2, f"error: {exc}\n")

    print(f"Raw measurements: {raw_path}")
    print(f"Median summary:   {medians_path}")
    print(f"Chart:            {chart_path}")
    print(f"Correctness check: {correctness_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
