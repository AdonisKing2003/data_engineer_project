"""Build the alternate 3NF and grain-safe wide layouts for TV3 benchmarks.

The star sources are read only: PostgreSQL public/x5 and BigQuery
<BQ_DATASET>/<BQ_DATASET>_5x. Only the selected destination tables are replaced.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any


LAYOUTS = ("3nf", "wide", "all")
SCALES = (1, 5)

LOGICAL_TABLES = (
    "dim_assessment",
    "dim_presentation",
    "dim_student",
    "dim_vle_site",
    "dim_week",
    "fact_enrollment",
    "fact_student_week",
    "fact_submission",
    "fact_vle_daily",
)

LOGICAL_GRAINS = {
    "dim_assessment": ("id_assessment",),
    "dim_presentation": ("code_module", "code_presentation"),
    "dim_student": ("id_student",),
    "dim_vle_site": ("id_site",),
    "dim_week": ("week_no",),
    "fact_enrollment": ("id_student", "code_module", "code_presentation"),
    "fact_student_week": ("id_student", "code_module", "code_presentation", "week_no"),
    "fact_submission": ("id_student", "id_assessment"),
    "fact_vle_daily": (
        "id_student", "code_module", "code_presentation", "id_site", "date",
    ),
}

# These attributes are available through the corresponding dimension or can
# be derived from the event date. The remaining source columns and row grain
# are kept in the normalized fact tables.
THREE_NF_OMIT = {
    "fact_submission": {"code_module", "code_presentation", "week_no"},
    "fact_vle_daily": {"code_module", "code_presentation", "week_no"},
}

THREE_NF_PHYSICAL_GRAINS = {
    "fact_submission_n": ("id_student", "id_assessment"),
    # id_site identifies its presentation in dim_vle_site.
    "fact_vle_daily_n": ("id_student", "id_site", "date"),
}

WIDE_SPEC = (
    {
        "name": "wide_enrollment",
        "kind": "wide_enrollment",
        "source_count_table": "fact_enrollment",
        "grain": LOGICAL_GRAINS["fact_enrollment"],
        "sources": ("fact_enrollment", "dim_student", "dim_presentation"),
    },
    {
        "name": "wide_submission",
        "kind": "wide_submission",
        "source_count_table": "fact_submission",
        "grain": LOGICAL_GRAINS["fact_submission"],
        "sources": ("fact_submission", "dim_student", "dim_assessment", "dim_presentation"),
    },
    {
        "name": "wide_vle_daily",
        "kind": "wide_vle_daily",
        "source_count_table": "fact_vle_daily",
        "grain": LOGICAL_GRAINS["fact_vle_daily"],
        "sources": ("fact_vle_daily", "dim_student", "dim_vle_site", "dim_presentation"),
    },
    {
        "name": "wide_student_week",
        "kind": "wide_student_week",
        "source_count_table": "fact_student_week",
        "grain": LOGICAL_GRAINS["fact_student_week"],
        "sources": ("fact_student_week", "dim_student", "dim_presentation", "dim_week"),
    },
    {
        "name": "wide_presentation",
        "kind": "wide_presentation",
        "source_count_table": "dim_presentation",
        "grain": LOGICAL_GRAINS["dim_presentation"],
        "sources": ("dim_presentation",),
    },
)

THREE_NF_VIEW_SPEC = (
    {
        "name": "fact_submission",
        "kind": "3nf_view_submission",
        "object_type": "view",
        "source_count_table": "fact_submission",
        "grain": LOGICAL_GRAINS["fact_submission"],
        "sources": ("fact_submission", "dim_assessment"),
    },
    {
        "name": "fact_vle_daily",
        "kind": "3nf_view_vle_daily",
        "object_type": "view",
        "source_count_table": "fact_vle_daily",
        "grain": LOGICAL_GRAINS["fact_vle_daily"],
        "sources": ("fact_vle_daily", "dim_vle_site"),
    },
)

WIDE_REQUIRED_COLUMNS = {
    "dim_presentation": {
        "code_module", "code_presentation", "year", "semester", "length_days",
        "n_weeks", "has_exam_result", "has_weighted_tma",
    },
    "dim_student": {
        "id_student", "gender", "region", "highest_education", "imd_band",
        "imd_unknown", "disability",
    },
    "dim_assessment": {
        "id_assessment", "code_module", "code_presentation", "assessment_type",
        "deadline", "weight", "assessment_order", "deadline_imputed",
        "zero_weight", "is_first_weighted_tma", "has_submissions",
    },
    "dim_vle_site": {
        "id_site", "code_module", "code_presentation", "activity_type", "week_from",
        "week_to", "has_planned_week", "never_clicked",
    },
    "dim_week": {"week_no", "day_from", "day_to", "is_pre_start"},
    "fact_enrollment": {"id_student", "code_module", "code_presentation"},
    "fact_submission": {"id_student", "id_assessment"},
    "fact_vle_daily": {"id_student", "code_module", "code_presentation", "id_site", "date"},
    "fact_student_week": {
        "id_student", "code_module", "code_presentation", "week_no",
    },
}


def _selected_layouts(layout: str) -> tuple[str, ...]:
    return ("3nf", "wide") if layout == "all" else (layout,)


def _target(engine: str, layout: str, scale: int, base_dataset: str = "oulad") -> str:
    if engine == "pg":
        return {
            ("3nf", 1): "three_nf",
            ("3nf", 5): "three_nf_x5",
            ("wide", 1): "wide",
            ("wide", 5): "wide_x5",
        }[(layout, scale)]
    return {
        ("3nf", 1): f"{base_dataset}_3nf",
        ("3nf", 5): f"{base_dataset}_3nf_5x",
        ("wide", 1): f"{base_dataset}_wide",
        ("wide", 5): f"{base_dataset}_wide_5x",
    }[(layout, scale)]


def _specs(layout: str) -> tuple[dict[str, Any], ...]:
    if layout == "3nf":
        tables = []
        for name in LOGICAL_TABLES:
            output_name = f"{name}_n" if name in THREE_NF_OMIT else name
            tables.append({
                "name": output_name,
                "kind": "3nf_copy",
                "source_count_table": name,
                "source_table": name,
                "grain": THREE_NF_PHYSICAL_GRAINS.get(output_name, LOGICAL_GRAINS[name]),
                "object_type": "table",
                "sources": (name,),
            })
        return tuple(tables) + THREE_NF_VIEW_SPEC
    return WIDE_SPEC


def _source_names(layouts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({source for layout in layouts for spec in _specs(layout)
                         for source in spec["sources"]}))


def _quote(engine: str, identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Unsupported SQL identifier: {identifier!r}")
    return f'"{identifier}"' if engine == "pg" else identifier


def _source_table(engine: str, source_schema: str, table: str) -> str:
    if engine == "pg":
        return f"{_quote(engine, source_schema)}.{_quote(engine, table)}"
    # BigQuery source references stay unqualified; QueryJobConfig selects the
    # source dataset explicitly for every dry run and query.
    return _quote(engine, table)


def _col(engine: str, alias: str, name: str) -> str:
    return f"{_quote(engine, alias)}.{_quote(engine, name)}"


def _as(engine: str, expression: str, alias: str) -> str:
    return f"{expression} AS {_quote(engine, alias)}"


def _student_projection(engine: str, alias: str) -> list[str]:
    return [
        _as(engine, _col(engine, alias, column), column)
        for column in (
            "gender", "region", "highest_education", "imd_band", "imd_unknown", "disability",
        )
    ]


def _presentation_projection(engine: str, alias: str) -> list[str]:
    return [
        _as(engine, _col(engine, alias, column), column)
        for column in (
            "year", "semester", "length_days", "n_weeks", "has_exam_result", "has_weighted_tma",
        )
    ]


def _select_sql(
    engine: str,
    source_schema: str,
    spec: dict[str, Any],
    source_columns: dict[str, tuple[str, ...]],
) -> str:
    kind = spec["kind"]
    table = spec["source_count_table"]
    if kind == "3nf_copy":
        source_table = spec["source_table"]
        omitted = THREE_NF_OMIT.get(source_table, set())
        columns = [column for column in source_columns[source_table] if column not in omitted]
        if not columns:
            raise ValueError(f"No columns remain for normalized table {source_table}")
        selected = ", ".join(_col(engine, "src", column) for column in columns)
        return f"SELECT {selected}\nFROM {_source_table(engine, source_schema, source_table)} AS src"

    if kind == "3nf_view_submission":
        week = (
            "CAST(FLOOR(f.date_submitted / 7.0) AS BIGINT)"
            if engine == "pg"
            else "CAST(FLOOR(f.date_submitted / 7.0) AS INT64)"
        )
        return (
            "SELECT f.id_student, f.id_assessment, a.code_module, a.code_presentation, "
            f"f.date_submitted, {week} AS week_no, f.score, f.days_late, f.is_banked, "
            "f.is_late, f.score_missing, f.is_beyond_course, f.is_pass_score\n"
            f"FROM {_source_table(engine, source_schema, 'fact_submission_n')} AS f\n"
            f"JOIN {_source_table(engine, source_schema, 'dim_assessment')} AS a "
            "ON a.id_assessment = f.id_assessment"
        )

    if kind == "3nf_view_vle_daily":
        week = (
            "CAST(FLOOR(f.date / 7.0) AS BIGINT)"
            if engine == "pg"
            else "CAST(FLOOR(f.date / 7.0) AS INT64)"
        )
        return (
            "SELECT f.id_student, v.code_module, v.code_presentation, f.id_site, f.date, "
            f"{week} AS week_no, f.sum_click, f.n_records, f.is_pre_start\n"
            f"FROM {_source_table(engine, source_schema, 'fact_vle_daily_n')} AS f\n"
            f"JOIN {_source_table(engine, source_schema, 'dim_vle_site')} AS v "
            "ON v.id_site = f.id_site"
        )

    if kind == "wide_presentation":
        return (
            "SELECT p.*\n"
            f"FROM {_source_table(engine, source_schema, 'dim_presentation')} AS p"
        )

    if kind == "wide_enrollment":
        fact = "fact_enrollment"
        student_join = f"s.id_student = f.id_student"
        presentation_join = (
            "p.code_module = f.code_module AND p.code_presentation = f.code_presentation"
        )
        dimensions = _student_projection(engine, "s") + _presentation_projection(engine, "p")
        joins = (
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_student')} AS s ON {student_join}\n"
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_presentation')} AS p ON {presentation_join}"
        )
    elif kind == "wide_submission":
        fact = "fact_submission"
        student_join = "s.id_student = f.id_student"
        assessment_join = "a.id_assessment = f.id_assessment"
        presentation_join = (
            "p.code_module = a.code_module AND p.code_presentation = a.code_presentation"
        )
        assessment_columns = [
            _as(engine, _col(engine, "a", column), column)
            for column in (
                "assessment_type", "deadline", "weight", "assessment_order",
                "deadline_imputed", "zero_weight", "is_first_weighted_tma", "has_submissions",
            )
        ]
        dimensions = (
            _student_projection(engine, "s")
            + assessment_columns
            + _presentation_projection(engine, "p")
        )
        joins = (
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_student')} AS s ON {student_join}\n"
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_assessment')} AS a ON {assessment_join}\n"
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_presentation')} AS p ON {presentation_join}"
        )
    elif kind == "wide_vle_daily":
        fact = "fact_vle_daily"
        student_join = "s.id_student = f.id_student"
        site_join = "v.id_site = f.id_site"
        presentation_join = (
            "p.code_module = f.code_module AND p.code_presentation = f.code_presentation"
        )
        site_columns = [
            _as(engine, _col(engine, "v", column), column)
            for column in (
                "activity_type", "week_from", "week_to", "has_planned_week", "never_clicked",
            )
        ]
        dimensions = (
            _student_projection(engine, "s")
            + site_columns
            + _presentation_projection(engine, "p")
        )
        joins = (
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_student')} AS s ON {student_join}\n"
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_vle_site')} AS v ON {site_join}\n"
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_presentation')} AS p ON {presentation_join}"
        )
    elif kind == "wide_student_week":
        fact = "fact_student_week"
        student_join = "s.id_student = f.id_student"
        presentation_join = (
            "p.code_module = f.code_module AND p.code_presentation = f.code_presentation"
        )
        week_join = "w.week_no = f.week_no"
        week_columns = [
            _as(engine, _col(engine, "w", column), column)
            for column in ("day_from", "day_to")
        ]
        dimensions = (
            _student_projection(engine, "s")
            + _presentation_projection(engine, "p")
            + week_columns
        )
        joins = (
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_student')} AS s ON {student_join}\n"
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_presentation')} AS p ON {presentation_join}\n"
            f"LEFT JOIN {_source_table(engine, source_schema, 'dim_week')} AS w ON {week_join}"
        )
    else:
        raise ValueError(f"Unsupported table kind {kind!r}")

    projection = ",\n       ".join(["f.*", *dimensions])
    return (
        f"SELECT {projection}\n"
        f"FROM {_source_table(engine, source_schema, fact)} AS f\n"
        f"{joins}"
    )


def _require_columns(
    source_columns: dict[str, tuple[str, ...]],
    names: tuple[str, ...],
    layouts: tuple[str, ...],
) -> None:
    needed: dict[str, set[str]] = {}
    if "3nf" in layouts:
        needed = {
            table: set(LOGICAL_GRAINS[table])
            for table in LOGICAL_TABLES if table in names
        }
        # These source columns are removed from the normalized facts because
        # the corresponding dimension/date path is the normalized lookup.
        for table, columns in THREE_NF_OMIT.items():
            needed[table].update(columns)
    if "wide" in layouts:
        for table, columns in WIDE_REQUIRED_COLUMNS.items():
            needed.setdefault(table, set()).update(columns)

    failures = []
    for table, columns in needed.items():
        missing = columns - set(source_columns.get(table, ()))
        if missing:
            failures.append(f"{table}: {', '.join(sorted(missing))}")
    if failures:
        raise RuntimeError("Source tables do not match docs/contract.md: " + "; ".join(failures))


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:,.1f} {unit}"
        amount /= 1024
    return f"{amount:,.1f} TiB"


def _connect_postgres():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "oulad"),
        password=os.getenv("POSTGRES_PASSWORD", "oulad"),
        dbname=os.getenv("POSTGRES_DB", "oulad"),
    )


def _pg_columns(connection, schema: str, tables: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    result = {}
    for table in tables:
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table),
        ).fetchall()
        if not rows:
            raise RuntimeError(f"Missing source table {schema}.{table}")
        result[table] = tuple(row[0] for row in rows)
    return result


def _pg_count(connection, schema: str, table: str) -> int:
    qualified = f"{_quote('pg', schema)}.{_quote('pg', table)}"
    return connection.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0]


def _pg_validate(connection, schema: str, table: str, expected: int, grain: tuple[str, ...]) -> None:
    qualified = f"{_quote('pg', schema)}.{_quote('pg', table)}"
    distinct_grain = ", ".join(_quote("pg", column) for column in grain)
    row_count, grain_count = connection.execute(
        f"SELECT COUNT(*), COUNT(DISTINCT ({distinct_grain})) FROM {qualified}"
    ).fetchone()
    ok = row_count == expected and grain_count == row_count
    print(
        f"{'OK ' if ok else 'FAIL'} {schema}.{table}: {row_count:,} rows "
        f"(source {expected:,}), {grain_count:,} unique grain keys"
    )
    if not ok:
        raise RuntimeError(f"Row-count or grain validation failed for {schema}.{table}")


def _pg_primary_key(connection, schema: str, table: str, grain: tuple[str, ...]) -> None:
    relation = f"{_quote('pg', schema)}.{_quote('pg', table)}"
    key = ", ".join(_quote("pg", column) for column in grain)
    constraint = _quote("pg", f"{table}_pkey")
    connection.execute(f"ALTER TABLE {relation} ADD CONSTRAINT {constraint} PRIMARY KEY ({key})")


def _pg_drop_output(connection, schema: str, table: str) -> None:
    row = connection.execute(
        "SELECT c.relkind FROM pg_class AS c "
        "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
        "WHERE n.nspname = %s AND c.relname = %s",
        (schema, table),
    ).fetchone()
    if row is None:
        return
    relation = f"{_quote('pg', schema)}.{_quote('pg', table)}"
    if row[0] in ("r", "p"):
        connection.execute(f"DROP TABLE {relation}")
    elif row[0] == "v":
        connection.execute(f"DROP VIEW {relation}")
    else:
        raise RuntimeError(f"Refusing to replace unexpected PostgreSQL object {schema}.{table}")


def _run_postgres(scale: int, layouts: tuple[str, ...]) -> None:
    source_schema = "public" if scale == 1 else "x5"
    source_tables = _source_names(layouts)
    selected = {layout: _target("pg", layout, scale) for layout in layouts}
    if source_schema in selected.values() or any(
        schema in {"public", "x5"} for schema in selected.values()
    ):
        raise RuntimeError("Refusing to write to a PostgreSQL star source schema")

    with _connect_postgres() as connection:
        source_columns = _pg_columns(connection, source_schema, source_tables)
        _require_columns(source_columns, source_tables, layouts)
        source_counts = {table: _pg_count(connection, source_schema, table) for table in source_tables}

        for layout, destination_schema in selected.items():
            specs = _specs(layout)
            view_specs = [spec for spec in specs if spec.get("object_type") == "view"]
            table_specs = [spec for spec in specs if spec.get("object_type", "table") == "table"]
            print(f"Building PostgreSQL {destination_schema} from read-only source schema {source_schema}")
            connection.execute(
                f"CREATE SCHEMA IF NOT EXISTS {_quote('pg', destination_schema)}"
            )
            for spec in view_specs:
                _pg_drop_output(connection, destination_schema, spec["name"])
            for spec in table_specs:
                table = spec["name"]
                relation = f"{_quote('pg', destination_schema)}.{_quote('pg', table)}"
                _pg_drop_output(connection, destination_schema, table)
                select = _select_sql("pg", source_schema, spec, source_columns)
                connection.execute(f"CREATE TABLE {relation} AS\n{select}")
                expected = source_counts[spec["source_count_table"]]
                _pg_validate(connection, destination_schema, table, expected, spec["grain"])
                _pg_primary_key(connection, destination_schema, table, spec["grain"])
            for spec in view_specs:
                table = spec["name"]
                relation = f"{_quote('pg', destination_schema)}.{_quote('pg', table)}"
                select = _select_sql("pg", destination_schema, spec, source_columns)
                connection.execute(f"CREATE VIEW {relation} AS\n{select}")
                expected = source_counts[spec["source_count_table"]]
                _pg_validate(connection, destination_schema, table, expected, spec["grain"])
    print("PostgreSQL layout build and validations committed.")


def _bq_project_and_dataset() -> tuple[str, str]:
    project = os.getenv("GCP_PROJECT_ID", "").strip()
    dataset = os.getenv("BQ_DATASET", "oulad").strip()
    if (
        not project
        or project.lower() in {"dien-project-id-vao-day", "your-project-id"}
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", project)
    ):
        raise RuntimeError("Set GCP_PROJECT_ID to a valid Google Cloud project ID")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", dataset):
        raise RuntimeError("BQ_DATASET must contain only letters, digits, and underscores")
    return project, dataset


def _bq_columns(client, project: str, dataset: str, tables: tuple[str, ...]):
    result = {}
    table_objects = {}
    for table in tables:
        table_id = f"{project}.{dataset}.{table}"
        try:
            table_object = client.get_table(table_id)
        except Exception as exc:
            raise RuntimeError(f"Missing BigQuery source table {table_id}: {exc}") from exc
        table_objects[table] = table_object
        result[table] = tuple(field.name for field in table_object.schema)
    return result, table_objects


def _bq_source_query_config(bigquery, project: str, dataset: str, dry_run: bool = False):
    return bigquery.QueryJobConfig(
        default_dataset=f"{project}.{dataset}",
        dry_run=dry_run,
        use_query_cache=False,
    )


def _bq_validate(
    client,
    bigquery,
    project: str,
    dataset: str,
    location: str,
    table: str,
    expected: int,
    grain: tuple[str, ...],
) -> None:
    fields = ", ".join(f"{column} AS {column}" for column in grain)
    sql = (
        "SELECT COUNT(*) AS row_count, "
        f"COUNT(DISTINCT STRUCT({fields})) AS grain_count FROM {_quote('bq', table)}"
    )
    job = client.query(
        sql,
        job_config=_bq_source_query_config(bigquery, project, dataset),
        location=location,
    )
    row = next(iter(job.result()))
    row_count = row["row_count"]
    grain_count = row["grain_count"]
    ok = row_count == expected and grain_count == row_count
    print(
        f"{'OK ' if ok else 'FAIL'} {dataset}.{table}: {row_count:,} rows "
        f"(source {expected:,}), {grain_count:,} unique grain keys"
    )
    if not ok:
        raise RuntimeError(f"Row-count or grain validation failed for {dataset}.{table}")


def _run_bigquery(scale: int, layouts: tuple[str, ...]) -> None:
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound

    project, base_dataset = _bq_project_and_dataset()
    source_dataset = base_dataset if scale == 1 else f"{base_dataset}_5x"
    destinations = {layout: _target("bq", layout, scale, base_dataset) for layout in layouts}
    source_datasets = {base_dataset, f"{base_dataset}_5x"}
    if any(dataset in source_datasets for dataset in destinations.values()):
        raise RuntimeError("Refusing to write to a BigQuery source dataset")

    client = bigquery.Client(project=project)
    source_dataset_object = client.get_dataset(f"{project}.{source_dataset}")
    location = source_dataset_object.location or os.getenv("BQ_LOCATION", "US")
    source_tables = _source_names(layouts)
    source_columns, source_objects = _bq_columns(client, project, source_dataset, source_tables)
    _require_columns(source_columns, source_tables, layouts)
    source_counts = {}
    for table, table_object in source_objects.items():
        if table_object.num_rows is None:
            raise RuntimeError(f"BigQuery source table has no row count metadata: {source_dataset}.{table}")
        source_counts[table] = int(table_object.num_rows)

    estimates = []
    for layout, destination_dataset in destinations.items():
        for spec in _specs(layout):
            if spec.get("object_type") == "view":
                continue
            select = _select_sql("bq", source_dataset, spec, source_columns)
            dry_run = client.query(
                select,
                job_config=_bq_source_query_config(
                    bigquery, project, source_dataset, dry_run=True
                ),
                location=location,
            )
            if dry_run.total_bytes_processed is None:
                raise RuntimeError(
                    f"Could not estimate source bytes for {destination_dataset}.{spec['name']}"
                )
            estimates.append((destination_dataset, spec["name"], dry_run.total_bytes_processed))

    print("Estimated BigQuery source bytes before copies (dry-run SELECT estimates):")
    total_estimate = 0
    for dataset, table, estimate in estimates:
        print(f"  {dataset}.{table}: {_format_bytes(estimate)}")
        total_estimate += estimate
    print(f"  Total: {_format_bytes(total_estimate)}")

    for layout, destination_dataset in destinations.items():
        specs = _specs(layout)
        view_specs = [spec for spec in specs if spec.get("object_type") == "view"]
        table_specs = [spec for spec in specs if spec.get("object_type", "table") == "table"]
        try:
            existing_dataset = client.get_dataset(f"{project}.{destination_dataset}")
        except NotFound:
            pass
        else:
            if existing_dataset.location != location:
                raise RuntimeError(
                    f"Destination dataset {destination_dataset} is in "
                    f"{existing_dataset.location}, but source is in {location}"
                )
        target_dataset = bigquery.Dataset(f"{project}.{destination_dataset}")
        target_dataset.location = location
        client.create_dataset(target_dataset, exists_ok=True)
        print(
            f"Building BigQuery {project}.{destination_dataset} "
            f"from read-only source dataset {source_dataset}"
        )
        for spec in view_specs:
            client.delete_table(
                f"{project}.{destination_dataset}.{spec['name']}", not_found_ok=True
            )
        for spec in table_specs:
            table = spec["name"]
            select = _select_sql("bq", source_dataset, spec, source_columns)
            target_table = f"`{project}.{destination_dataset}.{table}`"
            job = client.query(
                f"CREATE OR REPLACE TABLE {target_table} AS\n{select}",
                job_config=_bq_source_query_config(
                    bigquery, project, source_dataset
                ),
                location=location,
            )
            job.result()
            expected = source_counts[spec["source_count_table"]]
            _bq_validate(
                client, bigquery, project, destination_dataset, location,
                table, expected, spec["grain"],
            )
        for spec in view_specs:
            table = spec["name"]
            select = _select_sql("bq", destination_dataset, spec, source_columns)
            target_table = f"`{project}.{destination_dataset}.{table}`"
            job = client.query(
                f"CREATE VIEW {target_table} AS\n{select}",
                job_config=_bq_source_query_config(
                    bigquery, project, destination_dataset
                ),
                location=location,
            )
            job.result()
            expected = source_counts[spec["source_count_table"]]
            _bq_validate(
                client, bigquery, project, destination_dataset, location,
                table, expected, spec["grain"],
            )
    print("BigQuery layout build and validations completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=("bq", "pg"))
    parser.add_argument("--scale", type=int, choices=SCALES, default=1)
    parser.add_argument("--layout", required=True, choices=LAYOUTS)
    args = parser.parse_args()
    layouts = _selected_layouts(args.layout)

    try:
        if args.engine == "pg":
            _run_postgres(args.scale, layouts)
        else:
            _run_bigquery(args.scale, layouts)
    except Exception as exc:
        print(f"Layout build failed: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
