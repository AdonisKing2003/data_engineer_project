"""Non-cloud acceptance checks for the task 3.9 benchmark protocol."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import benchmark_layouts as benchmark
from scripts import run_sql as run_sql_module


ROOT = Path(__file__).resolve().parents[1]


class Frame:
    """Small dataframe-compatible object for pure runner tests."""

    def __init__(self, rows: list[dict]):
        self.columns = list(rows[0]) if rows else []
        self._rows = [tuple(row[column] for column in self.columns) for row in rows]

    def __len__(self):
        return len(self._rows)

    def itertuples(self, index=False, name=None):
        yield from self._rows


def _reference_values(workload: str, scale: int) -> dict:
    reference = benchmark.REFERENCE_1X[workload]
    if scale == 1:
        return dict(reference)
    return benchmark._scaled_reference([dict(reference)], workload, scale)


def _correct_warmups() -> list[dict]:
    records = []
    for engine, scale, layout, workload in benchmark.MATRIX:
        records.append({
            "engine": engine,
            "scale": scale,
            "layout": layout,
            "workload": workload,
            "phase": "warmup",
            "repeat": 0,
            "row_count": 1,
            "result_hash": f"{workload}-{scale}",
            "result_values": [_reference_values(workload, scale)],
        })
    return records


def _correct_measurements(warmups: list[dict], runs: int = 5) -> list[dict]:
    by_key = {
        (row["engine"], row["scale"], row["layout"], row["workload"]): row
        for row in warmups
    }
    measured = []
    for key, warmup in by_key.items():
        for repeat in range(1, runs + 1):
            measured.append({
                **{name: warmup[name] for name in ("engine", "scale", "layout", "workload")},
                "phase": "measured",
                "repeat": repeat,
                "row_count": warmup["row_count"],
                "result_hash": warmup["result_hash"],
            })
    return measured


def _install_fake_repo(monkeypatch, tmp_path: Path) -> Path:
    """Copy benchmark SQL to an isolated root and provide the gated question files."""
    repo_root = tmp_path / "repo"
    for engine, scale, layout, workload in benchmark.PLANNED_MATRIX:
        source = ROOT / "sql" / "bench" / engine / layout / f"{workload}.sql"
        target = repo_root / "sql" / "bench" / engine / layout / f"{workload}.sql"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(source, target)
    questions_dir = repo_root / "sql" / "questions"
    questions_dir.mkdir(parents=True)
    for number in range(1, 21):
        (questions_dir / f"q{number:02d}.sql").write_text(
            f"-- test fixture Q{number}\nSELECT {number};\n", encoding="utf-8"
        )
    monkeypatch.setattr(benchmark, "ROOT", repo_root)
    monkeypatch.setattr(benchmark, "QUESTIONS_DIR", questions_dir)
    return repo_root


def _passing_pg_snapshot() -> dict:
    schemas = []
    for engine, scale, layout, _ in benchmark.MATRIX:
        if engine != "pg":
            continue
        schema = benchmark.target_for("pg", scale, layout)
        if any(row["schema"] == schema for row in schemas):
            continue
        schemas.append({
            "schema": schema,
            "scale": scale,
            "layout": layout,
            "status": "passed",
            "missing_required_relations": [],
            "tables_without_primary_key": [],
            "non_primary_indexes": [],
            "invalid_indexes": [],
            "estimated_live_rows": 100,
            "estimated_total_relation_bytes": 1024,
            "stats_kind": "test estimate",
        })
    return {
        "status": "passed",
        "server": {"version": "16.test"},
        "schemas": schemas,
    }


def _passing_bq_snapshot() -> dict:
    targets = sorted({
        benchmark.target_for("bq", scale, layout)
        for engine, scale, layout, _ in benchmark.MATRIX if engine == "bq"
    })
    return {
        "status": "passed",
        "captured_at_utc": "2026-10-27T00:00:00Z",
        "targets": [
            {
                "target": target,
                "metadata_row_count_total": 100,
                "metadata_bytes_total": 2048,
                "stats_kind": "test metadata",
            }
            for target in targets
        ],
    }


def _estimates(*, runs: int, client, bigquery_module) -> list[dict]:
    return [
        {
            "engine": "bq",
            "scale": scale,
            "layout": layout,
            "workload": workload,
            "bytes_per_execution": 10,
            "planned_executions": runs + 1,
            "planned_bytes": 10 * (runs + 1),
        }
        for engine, scale, layout, workload in benchmark.BQ_MATRIX
    ]


class FakeExecutor:
    def __init__(self, *, bad_oracle=False, cache_hit=False, fail_measured=False):
        self.bigquery_module = SimpleNamespace(__name__="fake_bigquery")
        self.bigquery_client = object()
        self.postgres_connection = object()
        self.bad_oracle = bad_oracle
        self.cache_hit = cache_hit
        self.fail_measured = fail_measured
        self.calls = 0
        self.calls_by_key = Counter()
        self.closed = False

    def execute(self, sql, *, engine, scale, layout, use_query_cache):
        assert use_query_cache is False
        self.calls += 1
        workload = next(
            workload
            for candidate_engine, _, candidate_layout, workload in benchmark.MATRIX
            if candidate_engine == engine
            and candidate_layout == layout
            and benchmark.sql_file(engine, layout, workload).read_text(encoding="utf-8") == sql
        )
        key = (engine, scale, layout, workload)
        self.calls_by_key[key] += 1
        if self.fail_measured and self.calls_by_key[key] == 2:
            raise RuntimeError("injected measured-query failure")
        values = _reference_values(workload, scale)
        if self.bad_oracle and (engine, scale, layout, workload) == (
            "pg", 1, "star", "br1_q07"
        ):
            values["late_submissions"] += 1
        frame = Frame([values])
        return frame, benchmark.target_for(engine, scale, layout), {
            "client_elapsed_seconds": self.calls_by_key[key] * 0.001,
            "server_elapsed_seconds": 0.0005 if engine == "bq" else None,
            "bytes_processed": 100 if engine == "bq" else None,
            "bytes_billed": 100 if engine == "bq" else None,
            "cache_hit": self.cache_hit if engine == "bq" else None,
            "job_id": f"fake-{self.calls}" if engine == "bq" else None,
        }

    def close(self):
        self.closed = True


class CatalogResult:
    def __init__(self, *, rows=(), row=None):
        self.rows = list(rows)
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeCatalogConnection:
    def __init__(self, *, missing_relation=False, secondary_index=False):
        self.missing_relation = missing_relation
        self.secondary_index = secondary_index
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        normalized = sql.lower()
        if "current_database()" in normalized:
            return CatalogResult(row=("oulad", "oulad", "16.3", "UTF8", "128MB", "4MB"))
        if "from pg_class as c" in normalized:
            schema = params[0]
            scale_layout = next(
                (scale, layout)
                for engine, scale, layout, _ in benchmark.MATRIX
                if engine == "pg" and benchmark.target_for("pg", scale, layout) == schema
            )
            layout = scale_layout[1]
            required = list(benchmark.REQUIRED_RELATIONS_BY_LAYOUT[layout])
            if self.missing_relation and schema == "wide_x5":
                required.remove("wide_enrollment")
            return CatalogResult(rows=[
                (name, "v" if layout == "3nf" and name in {
                    "fact_submission", "fact_vle_daily"
                } else "r")
                for name in required
            ])
        if sql.startswith("ANALYZE "):
            return CatalogResult()
        if "from pg_index as index_meta" in normalized:
            schema = params[0]
            scale, layout = next(
                (scale, layout)
                for engine, scale, layout, _ in benchmark.MATRIX
                if engine == "pg" and benchmark.target_for("pg", scale, layout) == schema
            )
            required = list(benchmark.REQUIRED_RELATIONS_BY_LAYOUT[layout])
            physical = [
                name for name in required
                if not (layout == "3nf" and name in {"fact_submission", "fact_vle_daily"})
            ]
            indexes = [
                (name, f"{name}_pkey", True, True, f"CREATE UNIQUE INDEX {name}_pkey")
                for name in physical
            ]
            if self.secondary_index and schema == "public":
                indexes.append((physical[0], "extra_idx", False, True, "CREATE INDEX extra_idx"))
            return CatalogResult(rows=indexes)
        if "from pg_stat_user_tables" in normalized:
            schema = params[0]
            layout = next(
                layout for engine, scale, layout, _ in benchmark.MATRIX
                if engine == "pg" and benchmark.target_for("pg", scale, layout) == schema
            )
            names = benchmark.REQUIRED_RELATIONS_BY_LAYOUT[layout]
            physical = [
                name for name in names
                if not (layout == "3nf" and name in {"fact_submission", "fact_vle_daily"})
            ]
            return CatalogResult(rows=[(name, 100, 0, None, None, 1024) for name in physical])
        raise AssertionError(f"unexpected catalog query: {sql}")


def test_matrix_has_44_selected_cells_and_only_four_documented_exclusions(capsys):
    assert len(benchmark.PLANNED_MATRIX) == 48
    assert len(benchmark.MATRIX) == 44
    assert len(benchmark.EXCLUDED_MATRIX) == 4
    assert set(benchmark.MATRIX).isdisjoint(benchmark.EXCLUDED_MATRIX)
    assert set(benchmark.MATRIX) | set(benchmark.EXCLUDED_MATRIX) == set(benchmark.PLANNED_MATRIX)
    assert {row[3] for row in benchmark.EXCLUDED_MATRIX} == set(benchmark.WORKLOADS)
    assert all(row[:3] == ("bq", 5, "wide") for row in benchmark.EXCLUDED_MATRIX)

    benchmark.list_matrix()
    output = capsys.readouterr().out
    assert "48 planned combinations; 44 selected; 264 matrix executions" in output
    assert output.count("excluded: 5x wide") == 4
    manifest = benchmark._artifact_manifest("test-run", 5)
    assert all("Sandbox" in row["reason"] and "storage quota" in row["reason"]
               for row in manifest["coverage"]["excluded"])


def test_missing_selected_sql_target_is_reported(monkeypatch, tmp_path):
    missing_key = benchmark.MATRIX[0]
    missing_path = tmp_path / "missing.sql"
    original_sql_file = benchmark.sql_file

    def selected_sql_file(engine, layout, workload):
        if (engine, 1, layout, workload) == missing_key:
            return missing_path
        return original_sql_file(engine, layout, workload)

    monkeypatch.setattr(benchmark, "sql_file", selected_sql_file)
    assert benchmark.missing_sql_files() == [missing_path]


def test_seeded_plan_has_a_complete_warmup_and_five_distinct_round_orders():
    first = benchmark._execution_plan(5)
    second = benchmark._execution_plan(5)
    assert first == second
    assert first["random_seed"] == 39
    warmups = [
        (row["engine"], row["scale"], row["layout"], row["workload"])
        for row in first["warmup_order"]
    ]
    assert len(warmups) == 44
    assert len(set(warmups)) == 44
    assert set(warmups) == set(benchmark.MATRIX)
    assert len(first["measured_rounds"]) == 5
    for expected_repeat, round_info in enumerate(first["measured_rounds"], start=1):
        rows = [
            (row["engine"], row["scale"], row["layout"], row["workload"])
            for row in round_info["order"]
        ]
        assert round_info["repeat"] == expected_repeat
        assert len(rows) == 44 and len(set(rows)) == 44
        assert set(rows) == set(benchmark.MATRIX)


def test_result_hash_normalizes_numeric_types_and_order_but_keeps_duplicates():
    original = Frame([{"n": 1, "value": 1.25}, {"n": 2, "value": None}])
    reordered = Frame([{"n": 2.0, "value": float("nan")}, {"n": 1.0, "value": 1.25}])
    duplicate = Frame([
        {"n": 1, "value": 1.25},
        {"n": 1, "value": 1.25},
        {"n": 2, "value": None},
    ])
    assert benchmark.result_hash(original) == benchmark.result_hash(reordered)
    assert benchmark.result_hash(original) != benchmark.result_hash(duplicate)


def test_prepared_executor_uses_same_client_fetch_boundary_and_separate_bq_job_time(
    monkeypatch,
):
    class FakePostgres:
        def __init__(self):
            self.calls = []
            self.closed = False

        def execute(self, sql):
            self.calls.append(sql)
            if sql.startswith("SET search_path"):
                return None
            return SimpleNamespace(
                fetchall=lambda: [(1, "ok")],
                description=[SimpleNamespace(name="id"), SimpleNamespace(name="label")],
            )

        def close(self):
            self.closed = True

    class FakeBigQueryModule:
        __name__ = "fake_bigquery"

        @staticmethod
        def QueryJobConfig(**values):
            return SimpleNamespace(**values)

    class FakeBigQueryJob:
        job_id = "job-test"
        started = datetime(2026, 10, 27, tzinfo=timezone.utc)
        ended = started + timedelta(milliseconds=230)
        total_bytes_processed = 1234
        total_bytes_billed = 2048
        cache_hit = False

        def result(self):
            return SimpleNamespace(
                to_dataframe=lambda **kwargs: Frame([{"id": 1, "label": "ok"}])
            )

    class FakeBigQueryClient:
        def __init__(self):
            self.query_calls = []
            self.closed = False

        def query(self, sql, *, job_config):
            self.query_calls.append((sql, job_config))
            return FakeBigQueryJob()

        def close(self):
            self.closed = True

    pg_connection = FakePostgres()
    bq_client = FakeBigQueryClient()
    executor = run_sql_module.BenchmarkExecutor(
        project="test-project",
        bigquery_module=FakeBigQueryModule,
        bigquery_client=bq_client,
        postgres_connection=pg_connection,
    )

    times = iter((10.0, 12.5))
    monkeypatch.setattr(run_sql_module.time, "perf_counter", lambda: next(times))
    pg_frame, pg_target, pg_metrics = executor.execute(
        "SELECT 1", engine="pg", scale=1, layout="star"
    )
    assert pg_target == "PostgreSQL schema public"
    assert list(pg_frame.columns) == ["id", "label"]
    assert pg_metrics["client_elapsed_seconds"] == 2.5
    assert pg_metrics["server_elapsed_seconds"] is None
    assert pg_connection.calls[0] == 'SET search_path TO "public"'
    assert pg_connection.calls[1] == "SELECT 1"

    times = iter((20.0, 22.0))
    monkeypatch.setattr(run_sql_module.time, "perf_counter", lambda: next(times))
    bq_frame, bq_target, bq_metrics = executor.execute(
        "SELECT 1", engine="bq", scale=1, layout="star", use_query_cache=False
    )
    query_sql, job_config = bq_client.query_calls[0]
    assert query_sql == "SELECT 1"
    assert job_config.use_query_cache is False
    assert job_config.default_dataset == "test-project.oulad"
    assert bq_target == "BigQuery test-project.oulad"
    assert len(bq_frame) == 1
    assert bq_metrics["client_elapsed_seconds"] == 2.0
    assert bq_metrics["server_elapsed_seconds"] == pytest.approx(0.23)
    assert bq_metrics["bytes_processed"] == 1234
    assert bq_metrics["bytes_billed"] == 2048
    assert bq_metrics["cache_hit"] is False
    executor.close()
    assert pg_connection.closed and bq_client.closed


def test_postgres_preflight_records_settings_stats_and_only_accepts_primary_indexes():
    passing_connection = FakeCatalogConnection()
    report = benchmark._postgres_preflight(passing_connection)
    assert report["status"] == "passed"
    assert report["analyze_performed"] is True
    assert report["server"]["shared_buffers"] == "128MB"
    assert report["server"]["work_mem"] == "4MB"
    assert len(report["schemas"]) == 6
    assert all(row["stats_kind"].startswith("estimates from pg_stat_user_tables")
               for row in report["schemas"])
    assert all(row["indexes"] and all(index["is_primary"] for index in row["indexes"])
               for row in report["schemas"])
    assert not any("DROP INDEX" in statement.upper() or "CREATE INDEX" in statement.upper()
                   for statement, _ in passing_connection.statements)

    secondary_report = benchmark._postgres_preflight(
        FakeCatalogConnection(secondary_index=True)
    )
    assert secondary_report["status"] == "failed"
    public_schema = next(row for row in secondary_report["schemas"] if row["schema"] == "public")
    assert public_schema["non_primary_indexes"][0]["index"] == "extra_idx"

    missing_report = benchmark._postgres_preflight(
        FakeCatalogConnection(missing_relation=True)
    )
    assert missing_report["status"] == "failed"
    wide_x5 = next(row for row in missing_report["schemas"] if row["schema"] == "wide_x5")
    assert wide_x5["missing_required_relations"] == ["wide_enrollment"]


def test_warmup_oracle_scale_rules_and_selected_layout_parity():
    records = _correct_warmups()
    report = benchmark.warmup_correctness_report(records)
    assert report["status"] == "passed"
    assert len(report["groups"]) == 8
    assert all(group["status"] == "passed" for group in report["groups"])

    missing = records[:-1]
    assert benchmark.warmup_correctness_report(missing)["status"] == "failed"
    duplicated = [*records, dict(records[0])]
    assert benchmark.warmup_correctness_report(duplicated)["status"] == "failed"
    wrong_oracle = [dict(row) for row in records]
    baseline = next(row for row in wrong_oracle if (
        row["engine"], row["scale"], row["layout"], row["workload"]
    ) == ("pg", 1, "star", "br1_q07"))
    baseline["result_values"] = [dict(baseline["result_values"][0], late_submissions=0)]
    assert benchmark.warmup_correctness_report(wrong_oracle)["status"] == "failed"


def test_every_measured_repeat_must_be_present_unique_and_match_its_warmup():
    warmups = _correct_warmups()
    warmup_report = benchmark.warmup_correctness_report(warmups)
    measured = _correct_measurements(warmups)
    report = benchmark.measured_correctness_report(measured + warmups, 5, warmup_report)
    assert report["status"] == "passed"
    assert all(group["status"] == "passed" for group in report["groups"])

    missing = measured[:-1]
    assert benchmark.measured_correctness_report(
        missing + warmups, 5, warmup_report
    )["status"] == "failed"
    duplicate = [*measured, dict(measured[0])]
    assert benchmark.measured_correctness_report(
        duplicate + warmups, 5, warmup_report
    )["status"] == "failed"
    changed = [dict(row) for row in measured]
    changed[0]["result_hash"] = "changed"
    assert benchmark.measured_correctness_report(
        changed + warmups, 5, warmup_report
    )["status"] == "failed"


def test_summary_uses_median_min_max_and_inclusive_iqr():
    assert benchmark._stats([1, 2, 3, 4, 5]) == {
        "median": 3,
        "min": 1.0,
        "max": 5.0,
        "iqr": 2.0,
    }
    assert benchmark._stats([None, None]) == {
        "median": None,
        "min": None,
        "max": None,
        "iqr": None,
    }


def test_cli_keeps_the_m3_gate_and_defaults_to_five_measured_runs():
    args = benchmark.build_parser().parse_args(["run", "--confirm-m3"])
    assert args.runs == 5
    assert args.output_dir == "bench/results"
    with pytest.raises(SystemExit):
        benchmark.build_parser().parse_args(["run"])


def test_bigquery_estimate_dry_runs_only_selected_variants_and_counts_six_passes():
    class FakeModule:
        @staticmethod
        def QueryJobConfig(**values):
            return SimpleNamespace(**values)

    class FakeJob:
        total_bytes_processed = 250

    class FakeClient:
        def __init__(self):
            self.calls = []

        def query(self, sql, *, job_config):
            self.calls.append((sql, job_config))
            return FakeJob()

    client = FakeClient()
    estimates = benchmark.estimate_bq(runs=5, client=client, bigquery_module=FakeModule)

    assert len(estimates) == len(benchmark.BQ_MATRIX) == 20
    assert len(client.calls) == 20
    assert all(config.dry_run for _, config in client.calls)
    assert all(config.use_query_cache is False for _, config in client.calls)
    assert all(row["planned_executions"] == 6 for row in estimates)
    assert sum(row["planned_bytes"] for row in estimates) == 20 * 250 * 6


def test_historical_raw_rows_recalculate_all_44_medians_min_and_max():
    results = ROOT / "bench" / "results" / "historical_2026-10-26"
    expected_hashes = {
        "benchmark.raw.csv": "68f070f987f70bd16c30431263c9e6d79d0300367554f5a8e5a05af64449782b",
        "benchmark.medians.csv": "75dba94b93357b3bf5dae8a01c9535e2951a81d9d74f95d927a8792570fdbaf1",
        "benchmark.html": "257daf0e553981bc2427f0a0d76342748b59d6b5f77c365e6bdf06371d7d6c70",
    }
    for name, expected_hash in expected_hashes.items():
        assert hashlib.sha256((results / name).read_bytes()).hexdigest() == expected_hash
    with (results / "benchmark.raw.csv").open(newline="", encoding="utf-8-sig") as source:
        raw_rows = list(csv.DictReader(source))
    with (results / "benchmark.medians.csv").open(newline="", encoding="utf-8-sig") as source:
        median_rows = list(csv.DictReader(source))

    assert len(raw_rows) == 220
    assert len(median_rows) == 44
    grouped = {}
    for row in raw_rows:
        key = (row["engine"], row["scale"], row["layout"], row["query"])
        grouped.setdefault(key, []).append(float(row["seconds"]))
    assert len(grouped) == 44
    assert all(len(values) == 5 for values in grouped.values())
    assert len({(row["engine"], row["scale"], row["layout"], row["query"])
                for row in median_rows}) == 44
    historical_iqrs = []
    for row in median_rows:
        values = grouped[(row["engine"], row["scale"], row["layout"], row["query"])]
        assert math.isclose(statistics.median(values), float(row["median_s"]), abs_tol=1e-12)
        assert math.isclose(min(values), float(row["min_s"]), abs_tol=1e-12)
        assert math.isclose(max(values), float(row["max_s"]), abs_tol=1e-12)
        historical_iqrs.append(benchmark._stats(values)["iqr"])
    assert len(historical_iqrs) == 44 and all(iqr is not None for iqr in historical_iqrs)

    range_ratios = [
        (max(values) - min(values)) / statistics.median(values)
        for values in grouped.values()
    ]
    assert sum(ratio <= 0.10 for ratio in range_ratios) == 18
    assert statistics.median(range_ratios) == pytest.approx(0.21601082442314795)


def test_make_bench_requires_operator_m3_flag_and_passes_runs():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'test "$(CONFIRM_M3)" = "1"' in makefile
    assert "scripts/benchmark_layouts.py run --confirm-m3 --runs $(RUNS)" in makefile
    assert "RUNS ?= 5" in makefile


def test_run_refuses_incomplete_question_gate_before_any_database_work(monkeypatch, tmp_path):
    # Simulate a missing question file instead of relying on the checkout: once all
    # 20 files exist the gate passes and the runner would go on to real database work.
    monkeypatch.setattr(
        benchmark, "missing_question_files", lambda: [benchmark.QUESTIONS_DIR / "q05.sql"]
    )
    with pytest.raises(RuntimeError, match="question-file gate is incomplete"):
        benchmark.run_benchmark(tmp_path, runs=5)

    run_dir = next(path for path in tmp_path.iterdir() if path.is_dir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["coverage"]["planned"] == 48
    assert manifest["coverage"]["selected"] == 44
    assert len(manifest["coverage"]["excluded"]) == 4
    assert manifest["progress"]["completed_executions"] == 0
    assert (run_dir / "raw.csv").is_file()
    assert (run_dir / "diagnostics.txt").is_file()
    assert not (tmp_path / "latest_success.json").exists()
    assert not (run_dir / "medians.csv").exists()
    assert not (run_dir / "chart.html").exists()


def test_synthetic_success_publishes_exact_44_by_6_run_artifacts(monkeypatch, tmp_path):
    _install_fake_repo(monkeypatch, tmp_path)
    import run_sql

    instances = []

    def make_executor():
        run_dir = next(path for path in (tmp_path / "results").iterdir() if path.is_dir())
        manifest_before_first_query = json.loads(
            (run_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest_before_first_query["status"] == "incomplete"
        assert manifest_before_first_query["progress"]["completed_executions"] == 0
        assert (run_dir / "raw.csv").is_file()
        executor = FakeExecutor()
        instances.append(executor)
        return executor

    monkeypatch.setattr(run_sql, "BenchmarkExecutor", make_executor)
    monkeypatch.setattr(benchmark, "_postgres_preflight", lambda connection: _passing_pg_snapshot())
    monkeypatch.setattr(benchmark, "_bigquery_snapshot", lambda client: _passing_bq_snapshot())
    monkeypatch.setattr(benchmark, "estimate_bq", _estimates)

    raw_path, medians_path, chart_path, correctness_path = benchmark.run_benchmark(
        tmp_path / "results", runs=5
    )
    run_dir = raw_path.parent
    pointer = json.loads((tmp_path / "results" / "latest_success.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    correctness = json.loads(correctness_path.read_text(encoding="utf-8"))
    with raw_path.open(newline="", encoding="utf-8-sig") as source:
        raw_rows = list(csv.DictReader(source))
    with medians_path.open(newline="", encoding="utf-8-sig") as source:
        median_rows = list(csv.DictReader(source))

    assert manifest["status"] == "success"
    assert manifest["run_id"] == pointer["run_id"] == run_dir.name
    assert manifest["coverage"]["selected"] == 44
    assert manifest["coverage"]["planned"] == 48
    assert len(manifest["coverage"]["excluded"]) == 4
    assert len(manifest["configuration"]["selected_sql_sha256"]) == 24
    assert manifest["engine_versions"]["postgresql_server"] == "16.test"
    assert manifest["source_snapshot"]["snapshot_kind"].startswith(
        "preflight metadata capture"
    )
    assert manifest["progress"] == {"completed_executions": 264, "planned_executions": 264}
    assert len(raw_rows) == 264
    assert Counter(row["phase"] for row in raw_rows) == {"warmup": 44, "measured": 220}
    assert len(median_rows) == 44
    assert all(int(row["runs"]) == int(row["measured_runs"]) == 5 for row in median_rows)
    raw_groups = {}
    for row in raw_rows:
        if row["phase"] == "measured":
            key = (row["engine"], row["scale"], row["layout"], row["workload"])
            raw_groups.setdefault(key, []).append(float(row["client_elapsed_seconds"]))
    assert len(raw_groups) == 44
    for row in median_rows:
        key = (row["engine"], row["scale"], row["layout"], row["workload"])
        stats = benchmark._stats(raw_groups[key])
        assert int(row["runs"]) == len(raw_groups[key]) == 5
        assert float(row["median_s"]) == pytest.approx(stats["median"])
        assert float(row["min_elapsed_seconds"]) == pytest.approx(stats["min"])
        assert float(row["max_elapsed_seconds"]) == pytest.approx(stats["max"])
        assert float(row["iqr_elapsed_seconds"]) == pytest.approx(stats["iqr"])
    assert all(float(row["median_s"]) == pytest.approx(0.004) for row in median_rows)
    assert all(float(row["iqr_elapsed_seconds"]) == pytest.approx(0.002) for row in median_rows)
    assert all(row.is_file() for row in (raw_path, medians_path, chart_path, correctness_path))
    assert correctness["status"] == "passed"
    html_text = chart_path.read_text(encoding="utf-8")
    assert run_dir.name in html_text and "44 selected of 48 planned" in html_text
    assert instances[0].calls == 264
    assert instances[0].closed


@pytest.mark.parametrize(
    "failure_mode", ["postgres_preflight", "oracle", "cache", "measured_query"]
)
def test_failed_run_keeps_diagnostics_but_never_replaces_success_pointer(
    monkeypatch, tmp_path, failure_mode
):
    _install_fake_repo(monkeypatch, tmp_path)
    import run_sql

    output_dir = tmp_path / "results"
    output_dir.mkdir()
    previous_pointer = {"run_id": "previous_success"}
    pointer_path = output_dir / "latest_success.json"
    pointer_path.write_text(json.dumps(previous_pointer), encoding="utf-8")
    instances = []

    def make_executor():
        executor = FakeExecutor(
            bad_oracle=failure_mode == "oracle",
            cache_hit=failure_mode == "cache",
            fail_measured=failure_mode == "measured_query",
        )
        instances.append(executor)
        return executor

    monkeypatch.setattr(run_sql, "BenchmarkExecutor", make_executor)
    if failure_mode == "postgres_preflight":
        failed_snapshot = _passing_pg_snapshot()
        failed_snapshot["status"] = "failed"
        failed_snapshot["schemas"][0]["missing_required_relations"] = ["fact_vle_daily"]
        failed_snapshot["schemas"][0]["status"] = "failed"
        monkeypatch.setattr(benchmark, "_postgres_preflight", lambda connection: failed_snapshot)
    else:
        monkeypatch.setattr(benchmark, "_postgres_preflight", lambda connection: _passing_pg_snapshot())
    monkeypatch.setattr(benchmark, "_bigquery_snapshot", lambda client: _passing_bq_snapshot())
    monkeypatch.setattr(benchmark, "estimate_bq", _estimates)

    with pytest.raises(RuntimeError, match="Benchmark failed"):
        benchmark.run_benchmark(output_dir, runs=5)

    run_dir = next(path for path in output_dir.iterdir() if path.is_dir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    correctness = json.loads((run_dir / "correctness.json").read_text(encoding="utf-8"))
    assert json.loads(pointer_path.read_text(encoding="utf-8")) == previous_pointer
    assert manifest["status"] == "failed"
    assert correctness["status"] == "failed"
    assert (run_dir / "raw.csv").is_file()
    assert (run_dir / "diagnostics.txt").is_file()
    assert not (run_dir / "medians.csv").exists()
    assert not (run_dir / "chart.html").exists()
    if failure_mode == "measured_query":
        assert correctness["warmup"]["status"] == "passed"
        assert correctness["measured"]["status"] == "incomplete"
        with (run_dir / "raw.csv").open(newline="", encoding="utf-8-sig") as source:
            failure_rows = [row for row in csv.DictReader(source) if row["status"] == "failed"]
        assert len(failure_rows) == 1
    assert instances[0].closed
