# PostgreSQL 1x layout build and validation

**Result: VERIFIED** for building the PostgreSQL 1x `three_nf` and `wide` layouts and checking BR1, BR2, BR4, and BR6 result parity against `public`.

This validation covers row counts, declared grain keys, and one result-hash comparison per workload and layout. It is not a performance benchmark. BR1/Q7 and BR4/Q14 are benchmark-only SQL and are not accepted TV2 business semantics.

## Verification result

- **Status:** VERIFIED
- **Claim:** PostgreSQL 1x `three_nf` and `wide` were built from the existing `public` star schema; all selected builder grain checks passed; BR1/BR2/BR4/BR6 each returned matching row counts and normalized SHA-256 result hashes across `star`, `3nf`, and `wide`.
- **Evidence:** Fresh PostgreSQL, Parquet, and source-count checks; `build_layouts.py` exit code 0; 12 `run_sql.py` invocations through its CLI `main()` exit code 0; every workload has a matching hash across the three layouts.
- **Gaps:** One execution per workload/layout only. No timing conclusion, BigQuery run, 5x build, or full gated benchmark was performed.
- **Notes:** BR1/Q7 and BR4/Q14 remain benchmark-only. Their matching outputs establish layout parity for these SQL files, not acceptance of their business definitions.

## Environment and source gate

Docker was available (`docker info --format '{{.ServerVersion}}'` returned `29.5.3`). Both Compose containers were stopped initially. Started PostgreSQL and then the dependent app container:

```powershell
docker compose up -d postgres
docker compose up -d app
```

PostgreSQL reported healthy. The 1x `public` source counts matched both the existing Parquet warehouse and the row counts documented in `docs/contract.md` and `docs/etl_timing.md`:

| Source table | PostgreSQL `public` | 1x Parquet | Result |
|---|---:|---:|---|
| `dim_assessment` | 206 | 206 | Match |
| `dim_presentation` | 22 | 22 | Match |
| `dim_student` | 28,785 | 28,785 | Match |
| `dim_vle_site` | 6,364 | 6,364 | Match |
| `dim_week` | 43 | 43 | Match |
| `fact_enrollment` | 32,593 | 32,593 | Match |
| `fact_student_week` | 1,342,949 | 1,342,949 | Match |
| `fact_submission` | 173,912 | 173,912 | Match |
| `fact_vle_daily` | 8,459,320 | 8,459,320 | Match |

All nine `public` tables have primary keys matching the expected grains:

| Table | Primary key |
|---|---|
| `dim_assessment` | `id_assessment` |
| `dim_presentation` | `code_module, code_presentation` |
| `dim_student` | `id_student` |
| `dim_vle_site` | `id_site` |
| `dim_week` | `week_no` |
| `fact_enrollment` | `id_student, code_module, code_presentation` |
| `fact_student_week` | `id_student, code_module, code_presentation, week_no` |
| `fact_submission` | `id_student, id_assessment` |
| `fact_vle_daily` | `id_student, code_module, code_presentation, id_site, date` |

The current raw CSV files were counted and matched `data/staging/_row_counts.json` (both `rows` and `expected`): `courses.csv` 22; `assessments.csv` 206; `vle.csv` 6,364; `studentInfo.csv` 32,593; `studentRegistration.csv` 32,593; `studentAssessment.csv` 173,912; `studentVle.csv` 10,655,280.

## Layout build

Command:

```powershell
docker compose exec -T app python scripts/build_layouts.py --engine pg --scale 1 --layout all
```

Exit code: **0**. The builder reported all output row counts equal to their source counts and all unique-grain counts equal to output row counts.

| Layout object | Rows | Unique grain keys | Result |
|---|---:|---:|---|
| `three_nf.dim_assessment` | 206 | 206 | Pass |
| `three_nf.dim_presentation` | 22 | 22 | Pass |
| `three_nf.dim_student` | 28,785 | 28,785 | Pass |
| `three_nf.dim_vle_site` | 6,364 | 6,364 | Pass |
| `three_nf.dim_week` | 43 | 43 | Pass |
| `three_nf.fact_enrollment` | 32,593 | 32,593 | Pass |
| `three_nf.fact_student_week` | 1,342,949 | 1,342,949 | Pass |
| `three_nf.fact_submission_n` | 173,912 | 173,912 | Pass |
| `three_nf.fact_vle_daily_n` | 8,459,320 | 8,459,320 | Pass |
| `three_nf.fact_submission` contract view | 173,912 | 173,912 | Pass |
| `three_nf.fact_vle_daily` contract view | 8,459,320 | 8,459,320 | Pass |
| `wide.wide_enrollment` | 32,593 | 32,593 | Pass |
| `wide.wide_submission` | 173,912 | 173,912 | Pass |
| `wide.wide_vle_daily` | 8,459,320 | 8,459,320 | Pass |
| `wide.wide_student_week` | 1,342,949 | 1,342,949 | Pass |
| `wide.wide_presentation` | 22 | 22 | Pass |

For the normalized physical facts, the builder validated `fact_submission_n` at (`id_student`, `id_assessment`) and `fact_vle_daily_n` at (`id_student`, `id_site`, `date`). The restored contract views also passed their logical-grain checks.

## BR result parity

The SQL files are the current PostgreSQL benchmark queries under `sql/bench/pg/<layout>/`. For each workload and layout, `scripts/run_sql.py`'s `main()` was invoked with the equivalent arguments below. The returned DataFrame was hashed with `result_hash` from `scripts/benchmark_layouts.py` (column names plus normalized, order-independent rows; duplicates retained). The in-memory audit driver wrote no result files.

| Workload | Query file suffix | Rows in each layout | Result hash (SHA-256) | Match across layouts |
|---|---|---:|---|---|
| BR1 (Q7) | `br1_q07.sql` | 1 | `3933df4b3ee689eea4c397634f10c113bcc6870941af0bcfe65c4f248d5079c9` | Yes |
| BR2 (Q9) | `br2_q09.sql` | 1 | `d29ae6e4997ad2d6e7cc63bbeb65f6de02a18fada7bf852d3c15f83dbd7bd0db` | Yes |
| BR4 (Q14) | `br4_q14.sql` | 1 | `b6407900be7dabb1815590a21b58d145f1fc86347afd2b654441e922753862e6` | Yes |
| BR6 (Q18) | `br6_q18.sql` | 1 | `c591d78004f8458148c1f021b369309c45bab181e2b6f2fe8c45994466aa1c04` | Yes |

Observed outputs were identical for all three layouts:

- **BR1/Q7:** 97,088 non-banked TMA submissions; 16,320 late; 16.8% late rate.
- **BR2/Q9:** `oucontent`; 11,206,803 clicks out of 39,605,099; 28.3% share.
- **BR4/Q14:** 27,250 enrolled; 3,958 listed; 3,189 true positives; 80.6% precision; 26.9% recall; 43.5% baseline bad rate.
- **BR6/Q18:** IMD 0–10%: 615 students/enrollments, 41.1%; IMD 90–100%: 436 students/enrollments, 63.3%; gap 22.2 percentage points.

Equivalent CLI arguments used for the 12 runs:

```powershell
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/star/br1_q07.sql --engine pg --layout star --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/3nf/br1_q07.sql --engine pg --layout 3nf --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/wide/br1_q07.sql --engine pg --layout wide --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/star/br2_q09.sql --engine pg --layout star --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/3nf/br2_q09.sql --engine pg --layout 3nf --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/wide/br2_q09.sql --engine pg --layout wide --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/star/br4_q14.sql --engine pg --layout star --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/3nf/br4_q14.sql --engine pg --layout 3nf --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/wide/br4_q14.sql --engine pg --layout wide --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/star/br6_q18.sql --engine pg --layout star --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/3nf/br6_q18.sql --engine pg --layout 3nf --scale 1
docker compose exec -T app python scripts/run_sql.py sql/bench/pg/wide/br6_q18.sql --engine pg --layout wide --scale 1
```

No BigQuery commands, source reload, ETL staging, scaling, Git staging, or commits were performed.
