"""Load BR3 student pairs and print per-presentation Spearman summaries."""

from __future__ import annotations

from math import atanh, isfinite, sqrt, tanh
from pathlib import Path
import os

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "sql" / "br3_spearman.sql"


def fisher_confidence_interval(rho: float | None, n: int) -> tuple[float | None, float | None]:
    """Return a two-sided 95% Fisher z interval for a correlation estimate."""
    if rho is None or not isfinite(rho) or n <= 3:
        return None, None
    if rho <= -1.0 or rho >= 1.0:
        # Fisher's transform is unbounded at +/-1; use its limiting interval.
        endpoint = -1.0 if rho < 0 else 1.0
        return endpoint, endpoint

    margin = 1.96 / sqrt(n - 3)
    transformed = atanh(rho)
    return tanh(transformed - margin), tanh(transformed + margin)


def load_br3_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return per-presentation summaries and chart pairs without student IDs."""
    os.chdir(ROOT)
    query = QUERY_PATH.read_text(encoding="utf-8")
    with duckdb.connect(database=":memory:") as connection:
        details = connection.execute(query).fetchdf()

    summary_rows: list[dict[str, object]] = []
    for (code_module, code_presentation), group in details.groupby(
        ["code_module", "code_presentation"], sort=True
    ):
        n = int(group["n"].iloc[0])
        rho_value = group["rho"].iloc[0]
        rho = None if pd.isna(rho_value) else float(rho_value)
        lower, upper = fisher_confidence_interval(rho, n)
        summary_rows.append(
            {
                "code_module": code_module,
                "code_presentation": code_presentation,
                "n": n,
                "rho": rho,
                "ci_95_lower": lower,
                "ci_95_upper": upper,
            }
        )

    pairs = details.loc[
        :, ["code_module", "code_presentation", "clicks_before_deadline", "score"]
    ].copy()
    pairs["clicks_before_deadline"] = pairs["clicks_before_deadline"].astype("int64")
    pairs["score"] = pairs["score"].astype("int64")
    summaries = pd.DataFrame(
        summary_rows,
        columns=[
            "code_module",
            "code_presentation",
            "n",
            "rho",
            "ci_95_lower",
            "ci_95_upper",
        ],
    )
    return summaries, pairs


def main() -> None:
    summaries, pairs = load_br3_data()
    display = summaries.copy()
    for column in ("rho", "ci_95_lower", "ci_95_upper"):
        display[column] = display[column].map(
            lambda value: "NULL" if pd.isna(value) else f"{value:.3f}"
        )
    print("BR3 — Spearman clicks before first weighted TMA vs score")
    print(display.to_string(index=False))
    zero_click_pairs = int((pairs["clicks_before_deadline"] == 0).sum())
    print(
        f"Student-level pairs: {len(pairs):,}; "
        f"zero-click pairs retained: {zero_click_pairs:,}"
    )


if __name__ == "__main__":
    main()
