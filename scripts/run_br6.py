"""Run the BR6 DuckDB query against the local Parquet warehouse."""

from pathlib import Path
import os

import duckdb


ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "sql" / "br6_imd_gap.sql"


def main() -> None:
    os.chdir(ROOT)
    query = QUERY_PATH.read_text(encoding="utf-8")
    with duckdb.connect(database=":memory:") as connection:
        result = connection.execute(query).fetchdf()
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
