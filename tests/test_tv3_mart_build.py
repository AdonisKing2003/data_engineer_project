"""Reject unusable BigQuery mart snapshots before declaring a refresh valid."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts.build_tv3_marts import MARTS, _validate_mart


@pytest.mark.parametrize(
    ("row_count", "grain_count", "metadata_count", "valid"),
    [(0, 0, 0, False), (2, 1, 2, False), (2, 2, 1, False), (2, 2, 2, True)],
    ids=["empty-snapshot", "duplicate-grain", "metadata-mismatch", "valid-snapshot"],
)
def test_refresh_requires_nonempty_unique_and_consistent_snapshot(
    row_count, grain_count, metadata_count, valid
):
    timestamp = datetime(2026, 10, 27, tzinfo=timezone.utc)
    mart = MARTS[0]
    table = SimpleNamespace(
        schema=[SimpleNamespace(name=name) for name in mart.required_columns],
        num_rows=metadata_count,
        created=timestamp,
    )
    result = {
        "row_count": row_count,
        "grain_count": grain_count,
        "mart_created_at": timestamp if row_count else None,
    }
    job = SimpleNamespace(result=lambda: [result], total_bytes_processed=0)
    client = SimpleNamespace(get_table=lambda _: table, query=lambda *args, **kwargs: job)
    bigquery = SimpleNamespace(QueryJobConfig=lambda **kwargs: kwargs)
    if valid:
        _validate_mart(client, bigquery, "test-project", "oulad", "US", mart)
    else:
        with pytest.raises(RuntimeError, match="validation failed"):
            _validate_mart(client, bigquery, "test-project", "oulad", "US", mart)
