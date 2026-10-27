"""Run the BR2 DuckDB query against the local Parquet warehouse."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "sql" / "br2_vle_weekly.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional CSV path for the full presentation-week-activity result.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.chdir(ROOT)
    query = QUERY_PATH.read_text(encoding="utf-8")

    with duckdb.connect(database=":memory:") as connection:
        result = connection.execute(query).fetchdf()

    print(f"BR2 rows: {len(result):,}")
    print(f"Presentations: {result[['code_module', 'code_presentation']].drop_duplicates().shape[0]:,}")
    print(f"Activity types: {result['activity_type'].nunique():,}")

    anchor = result.loc[
        (result["code_module"] == "FFF")
        & (result["code_presentation"] == "2014J")
        & (result["week_no"] == 0)
    ]
    if anchor.empty:
        print("FFF 2014J week 0: no rows found")
    else:
        week = anchor.iloc[0]
        oucontent = anchor.loc[anchor["activity_type"] == "oucontent"]
        oucontent_share = (
            float(oucontent.iloc[0]["activity_type_click_share"])
            if not oucontent.empty
            else 0.0
        )
        print(
            "FFF 2014J week 0: "
            f"{int(week['enrolled_students']):,} enrolled, "
            f"{int(week['offering_week_total_clicks']):,} clicks, "
            f"{week['avg_clicks_per_enrolled_student']:.1f} average clicks/student, "
            f"oucontent share {oucontent_share:.1%}"
        )

    weekly = result[
        [
            "code_module",
            "code_presentation",
            "week_no",
            "enrolled_students",
            "offering_week_total_clicks",
            "avg_clicks_per_enrolled_student",
            "avg_clicks_rank",
            "total_clicks_rank",
        ]
    ].drop_duplicates()
    fff_2014j = weekly.loc[
        (weekly["code_module"] == "FFF")
        & (weekly["code_presentation"] == "2014J")
    ]
    if not fff_2014j.empty:
        average_peak = fff_2014j.loc[fff_2014j["avg_clicks_rank"] == 1]
        total_peak = fff_2014j.loc[fff_2014j["total_clicks_rank"] == 1]
        average_weeks = ", ".join(average_peak["week_no"].astype(str))
        total_weeks = ", ".join(total_peak["week_no"].astype(str))
        print(
            "FFF 2014J peak week(s): "
            f"average clicks/student = {average_weeks} "
            f"({average_peak['avg_clicks_per_enrolled_student'].max():.1f}); "
            f"total clicks = {total_weeks} "
            f"({int(total_peak['offering_week_total_clicks'].max()):,})"
        )

    if args.output:
        output_path = args.output if args.output.is_absolute() else ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False, encoding="utf-8")
        print(f"Wrote CSV: {output_path}")


if __name__ == "__main__":
    main()
