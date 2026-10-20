"""Run a SQL file on BigQuery, PostgreSQL, or the local DuckDB/Parquet warehouse."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ENGINES = ("bq", "pg", "duckdb")
LAYOUTS = ("star", "3nf", "wide")


def _target(engine: str, layout: str, scale: int) -> str:
    if layout not in LAYOUTS:
        raise ValueError(f"Unsupported layout {layout!r}; choose from {', '.join(LAYOUTS)}")
    if scale < 1:
        raise ValueError("--scale must be a positive integer")
    if engine == "duckdb":
        if layout != "star":
            raise ValueError("DuckDB supports --layout star only; 3NF/wide variants are built in BigQuery and PostgreSQL")
        return str(ROOT / "data" / ("warehouse" if scale == 1 else f"warehouse_{scale}x"))
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
        return base if scale == 1 else f"{base}_{scale}x"
    if layout == "3nf":
        return f"{base}_3nf" if scale == 1 else f"{base}_3nf_{scale}x"
    return f"{base}_wide" if scale == 1 else f"{base}_wide_{scale}x"


def run_bigquery(sql: str, scale: int, layout: str = "star", use_query_cache: bool = True):
    """Return (DataFrame, location, run metrics) for a BigQuery query."""
    from google.cloud import bigquery

    project = os.getenv("GCP_PROJECT_ID", "").strip()
    if not project or project.lower() in {"dien-project-id-vao-day", "your-project-id"}:
        raise RuntimeError("GCP_PROJECT_ID is missing or still has the example value")
    dataset = _target("bq", layout, scale)
    client = bigquery.Client(project=project, location=os.getenv("BQ_LOCATION", "US"))
    job_config = bigquery.QueryJobConfig(
        default_dataset=f"{project}.{dataset}",
        use_query_cache=use_query_cache,
    )
    job = client.query(sql, job_config=job_config)
    df = job.result().to_dataframe(create_bqstorage_client=False)
    elapsed = (job.ended - job.started).total_seconds() if job.ended and job.started else None
    metrics = {
        "elapsed_seconds": elapsed,
        "bytes_processed": job.total_bytes_processed,
        "bytes_billed": job.total_bytes_billed,
        "cache_hit": job.cache_hit,
        "job_id": job.job_id,
    }
    return df, f"BigQuery {project}.{dataset}", metrics


def run_postgres(sql: str, scale: int, layout: str = "star"):
    import psycopg

    schema = _target("pg", layout, scale)
    conninfo = (
        f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
        f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
        f"dbname={os.getenv('POSTGRES_DB', 'oulad')}"
    )
    started = time.perf_counter()
    with psycopg.connect(conninfo) as connection:
        connection.execute(f'SET search_path TO "{schema}"')
        cursor = connection.execute(sql)
        df = pd.DataFrame(cursor.fetchall(), columns=[column.name for column in cursor.description])
    elapsed = time.perf_counter() - started
    return df, f"PostgreSQL schema {schema}", {"elapsed_seconds": elapsed}


def run_duckdb(sql: str, scale: int, layout: str = "star"):
    import duckdb

    warehouse = Path(_target("duckdb", layout, scale))
    if not warehouse.is_dir():
        raise FileNotFoundError(f"DuckDB warehouse is missing: {warehouse}")
    started = time.perf_counter()
    with duckdb.connect(config={"file_search_path": str(ROOT)}) as connection:
        for table_path in sorted(warehouse.iterdir()):
            if table_path.is_dir() and table_path.name.startswith(("dim_", "fact_")):
                parquet_glob = (table_path / "*.parquet").as_posix().replace("'", "''")
                table_name = table_path.name.replace('"', '""')
                connection.execute(
                    f'CREATE VIEW "{table_name}" AS SELECT * FROM read_parquet(\'{parquet_glob}\')'
                )
        df = connection.execute(sql).fetchdf()
    elapsed = time.perf_counter() - started
    return df, f"DuckDB on {warehouse.relative_to(ROOT).as_posix()}", {"elapsed_seconds": elapsed}


def execute_sql(
    sql: str,
    engine: str = "bq",
    scale: int = 1,
    layout: str = "star",
    use_query_cache: bool = True,
):
    if engine not in ENGINES:
        raise ValueError(f"Unsupported engine {engine!r}; choose from {', '.join(ENGINES)}")
    runner = {"bq": run_bigquery, "pg": run_postgres, "duckdb": run_duckdb}[engine]
    if engine == "bq":
        return runner(sql, scale, layout, use_query_cache)
    return runner(sql, scale, layout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="one SQL file containing a SELECT query")
    parser.add_argument("--engine", choices=ENGINES, default="bq")
    parser.add_argument("--layout", choices=LAYOUTS, default="star")
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--no-cache", action="store_true", help="disable BigQuery query cache")
    parser.add_argument("--output-csv", help="optional path to save the query result as CSV")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        sys.exit(f"SQL file does not exist: {path}")
    if args.scale < 1:
        parser.error("--scale must be a positive integer")

    sql = path.read_text(encoding="utf-8")
    started = time.perf_counter()
    df, target, metrics = execute_sql(
        sql,
        engine=args.engine,
        scale=args.scale,
        layout=args.layout,
        use_query_cache=not args.no_cache,
    )
    wall_seconds = time.perf_counter() - started
    if args.output_csv:
        output = Path(args.output_csv)
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, index=False)

    with pd.option_context("display.max_rows", 50, "display.max_columns", 30, "display.width", 180):
        print(df.to_string(index=False) if len(df) <= 50 else df)
    details = [f"{len(df):,} rows", target, f"wall {wall_seconds:.2f}s"]
    if metrics.get("bytes_processed") is not None:
        details.append(f"scanned {metrics['bytes_processed'] / 1e6:,.1f} MB")
    if metrics.get("cache_hit") is not None:
        details.append(f"cache_hit={metrics['cache_hit']}")
    print(" | ".join(details))


if __name__ == "__main__":
    main()
