"""Local-only tests for the manifest-backed benchmark quality page."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import streamlit

from scripts import benchmark_layouts as benchmark


ROOT = Path(__file__).resolve().parents[1]


class Column:
    def __init__(self, ui):
        self.ui = ui

    def metric(self, label, value):
        self.ui.metrics[label] = value

    def selectbox(self, label, options, **kwargs):
        value = list(options)[0]
        self.ui.selections[label] = value
        return value


class FakeStreamlit:
    def __init__(self):
        self.titles = []
        self.writes = []
        self.infos = []
        self.errors = []
        self.captions = []
        self.subheaders = []
        self.metrics = {}
        self.dataframes = []
        self.downloads = []
        self.figures = []
        self.selections = {}

    def title(self, value):
        self.titles.append(value)

    def write(self, value):
        self.writes.append(value)

    def info(self, value):
        self.infos.append(value)

    def error(self, value):
        self.errors.append(value)

    def caption(self, value):
        self.captions.append(value)

    def subheader(self, value):
        self.subheaders.append(value)

    def columns(self, count):
        return [Column(self) for _ in range(count)]

    def dataframe(self, value, **kwargs):
        self.dataframes.append(value)

    def download_button(self, *args, **kwargs):
        self.downloads.append((args, kwargs))

    def plotly_chart(self, value, **kwargs):
        self.figures.append(value)


def _load_quality_page(monkeypatch):
    """Load the real page function without starting Streamlit's navigation loop."""
    monkeypatch.setattr(
        streamlit,
        "navigation",
        lambda *args, **kwargs: SimpleNamespace(run=lambda: None),
    )
    module_name = f"task39_quality_page_{id(monkeypatch)}"
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / "app" / "Home.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    ui = FakeStreamlit()
    module.st = ui
    return module, ui


def _write_success_artifacts(root: Path, *, median_schema="compat") -> Path:
    results = root / "bench" / "results"
    run_id = "run-44-of-48"
    run_dir = results / run_id
    run_dir.mkdir(parents=True)
    if median_schema == "compat":
        median_column, runs_column = "median_s", "runs"
    else:
        median_column, runs_column = "median_elapsed_seconds", "measured_runs"
    fields = ["query", "engine", "scale", "layout", "workload", median_column, runs_column]
    with (run_dir / "medians.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for engine, scale, layout, workload in benchmark.MATRIX:
            writer.writerow({
                "query": workload,
                "engine": engine,
                "scale": scale,
                "layout": layout,
                "workload": workload,
                median_column: 0.25,
                runs_column: 5,
            })
    (run_dir / "chart.html").write_text("<html>task 3.9 chart</html>", encoding="utf-8")
    excluded = [
        {
            "engine": engine,
            "scale": scale,
            "layout": layout,
            "workload": workload,
            "reason": "BigQuery Sandbox 5x wide storage quota",
        }
        for engine, scale, layout, workload in benchmark.EXCLUDED_MATRIX
    ]
    (run_dir / "manifest.json").write_text(
        json.dumps({
            "status": "success",
            "run_id": run_id,
            "completed_at_utc": "2026-10-27T12:00:00Z",
            "coverage": {"planned": 48, "selected": 44, "excluded": excluded},
            "artifacts": {"medians_csv": "medians.csv", "chart_html": "chart.html"},
        }),
        encoding="utf-8",
    )
    results.mkdir(parents=True, exist_ok=True)
    (results / "latest_success.json").write_text(
        json.dumps({"run_id": run_id}), encoding="utf-8"
    )
    return run_dir


def test_quality_page_shows_only_manifest_success_with_scope_runs_and_exclusions(
    monkeypatch, tmp_path
):
    module, ui = _load_quality_page(monkeypatch)
    run_dir = _write_success_artifacts(tmp_path)
    module.PROJECT_ROOT = tmp_path

    module.render_quality_page()

    assert not ui.errors
    assert ui.metrics["Phạm vi"] == "44/48"
    assert ui.metrics["Tổ hợp loại trừ"] == 4
    assert ui.metrics["Lượt đo theo CSV"] == "5 / tổ hợp"
    assert any("run-44-of-48" in caption for caption in ui.captions)
    assert any("Thời điểm run thành công gần nhất" in caption for caption in ui.captions)
    assert len(ui.figures) == 1
    assert len(ui.downloads) == 1
    excluded_frame = ui.dataframes[0]
    assert len(excluded_frame) == 4
    assert set(excluded_frame["Lý do"]) == {"BigQuery Sandbox 5x wide storage quota"}
    summary_frame = ui.dataframes[1]
    assert len(summary_frame) == 44
    assert (run_dir / "chart.html").is_file()


@pytest.mark.parametrize("median_schema", ["compat", "extended"])
def test_quality_page_reads_both_median_schema_variants(monkeypatch, tmp_path, median_schema):
    module, ui = _load_quality_page(monkeypatch)
    _write_success_artifacts(tmp_path, median_schema=median_schema)
    module.PROJECT_ROOT = tmp_path

    module.render_quality_page()

    assert not ui.errors
    assert len(ui.figures) == 1
    assert ui.metrics["Phạm vi"] == "44/48"


def test_quality_page_ignores_an_incomplete_run(monkeypatch, tmp_path):
    module, ui = _load_quality_page(monkeypatch)
    run_dir = _write_success_artifacts(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "incomplete"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    module.PROJECT_ROOT = tmp_path

    module.render_quality_page()

    assert not ui.errors
    assert any("chưa được đánh dấu thành công" in message for message in ui.infos)
    assert not ui.dataframes
    assert not ui.figures


def test_quality_page_rejects_success_manifest_with_wrong_matrix(monkeypatch, tmp_path):
    module, ui = _load_quality_page(monkeypatch)
    run_dir = _write_success_artifacts(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["coverage"]["excluded"][0]["layout"] = "star"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    module.PROJECT_ROOT = tmp_path

    module.render_quality_page()

    assert ui.errors
    assert "44/48" in ui.errors[-1]
    assert not ui.figures


def test_quality_page_explains_when_no_success_pointer_exists(monkeypatch, tmp_path):
    module, ui = _load_quality_page(monkeypatch)
    historical = tmp_path / "bench" / "results" / "historical"
    historical.mkdir(parents=True)
    (historical / "benchmark.medians.csv").write_text(
        "query,median_s,runs\nbr1_q07,0.1,5\n", encoding="utf-8"
    )
    module.PROJECT_ROOT = tmp_path

    module.render_quality_page()

    assert not ui.errors
    assert any("Chưa có lượt benchmark thành công" in message for message in ui.infos)
    assert not ui.dataframes and not ui.figures
