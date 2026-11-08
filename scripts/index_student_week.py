"""Chỉ mục cho fact_student_week (trang Cảnh báo BR4, trang Sinh viên BR7): đo 3 mức, ghi docs/indexing.md.

BigQuery không có chỉ mục B+-tree; thứ thay thế là phân vùng + gom cụm. Ba mức trên bảng thử, cùng dữ liệu:
  1. bảng thường   2. phân vùng theo week_no   3. phân vùng + gom cụm
Cách phân vùng / gom cụm lấy đúng từ etl/04_load_bq.py (TUNING), nên mức 3 là cách lưu của kho chính.
Truy vấn là đúng các file SQL app đang chạy (sql/bigquery/br4_*.sql, br7_*.sql), chỉ đổi tên bảng.

PostgreSQL (kho đối chứng) có chỉ mục B+-tree. Ba mức trên bản sao của bảng:
  1. chỉ khóa chính (id_student, code_module, code_presentation, week_no)
  2. thêm chỉ mục ix_fact_student_week_week (week_no, code_module, code_presentation), lấy từ etl/05_load_pg.py
  3. CLUSTER bảng theo chỉ mục đó: xếp lại dòng trên đĩa để các dòng cùng tuần nằm liền nhau
Truy vấn: sql/optimize/br4_week4_pg.sql (cùng logic br4_at_risk_all, tuần 4). Đo thêm chi phí ghi:
INSERT cả bảng vào bảng rỗng khi chỉ có khóa chính và khi có thêm chỉ mục.

Không đụng bảng thật: BigQuery dùng bảng idx_fsw_* trong dataset oulad (5× chỉ khi gọi --bq-scales 1 5),
PostgreSQL dùng schema
idx_test, idx_test_x5; tất cả bị xóa sau khi đo. Mỗi truy vấn chạy --runs lần (BigQuery tắt cache), lấy trung
vị thời gian, và kết quả 3 mức phải giống hệt nhau.

Chạy trong container:
    python scripts/index_student_week.py          # cũng chính là: make indexing
    python scripts/index_student_week.py --pg-scales 1 --runs 3
"""
import argparse
import datetime
import importlib
import os
import re
import statistics
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
sys.path.insert(0, str(ROOT / "scripts"))
from common import give_back_to_owner  # noqa: E402
from optimize import mb, pg_connect, rename_table, rows_read, same_result  # noqa: E402

TUNING = importlib.import_module("04_load_bq").TUNING["fact_student_week"]
_pg = importlib.import_module("05_load_pg")
PG_INDEX_DDL, PG_CLUSTER_DDL = _pg.INDEXES["fact_student_week"]
PG_PK = _pg.PRIMARY_KEYS["fact_student_week"]
PG_INDEX = re.search(r"CREATE INDEX (\w+)", PG_INDEX_DDL).group(1)

DOC = ROOT / "docs" / "indexing.md"
BQ_SQL = ROOT / "sql" / "bigquery"
PG_SQL = ROOT / "sql" / "optimize" / "br4_week4_pg.sql"
MODULE, PRESENTATION, WEEK = "BBB", "2014J", 4

FIELD, START, END, STEP = TUNING["range"]
CLUSTER = TUNING["cluster"]
PARTITION_BY = f"PARTITION BY RANGE_BUCKET({FIELD}, GENERATE_ARRAY({START}, {END}, {STEP}))"
BQ_LEVELS = [
    ("plain", "Bảng thường", "idx_fsw_plain", ""),
    ("part", "Phân vùng", "idx_fsw_part", PARTITION_BY),
    ("clust", "Phân vùng + gom cụm", "idx_fsw_part_clust", f"{PARTITION_BY}\nCLUSTER BY {', '.join(CLUSTER)}"),
]
# (khóa, mô tả, file SQL của app, có đọc fact_enrollment không)
BQ_QUERIES = [
    ("br4_all", f"BR4 tuần {WEEK}, toàn trường", "br4_at_risk_all", True),
    ("br4_list", f"BR4 tuần {WEEK}, một đợt ({MODULE} {PRESENTATION})", "br4_at_risk_list", True),
    ("br7_cohort", f"BR7 phân vị theo tuần, một đợt", "br7_cohort_benchmark", False),
    ("br7_student", "BR7 tiến trình một sinh viên", "br7_student_progress", True),
]
SCALES = {1: ("oulad", "public"), 5: ("oulad_5x", "x5")}  # BigQuery dataset, PostgreSQL schema


# ---------------------------------------------------------------- BigQuery

class BigQuery:
    def __init__(self, runs):
        from google.cloud import bigquery

        self.bq = bigquery
        self.runs = runs
        self.project = os.environ["GCP_PROJECT_ID"]
        self.base = os.getenv("BQ_DATASET", "oulad")
        self.client = bigquery.Client(project=self.project, location=os.getenv("BQ_LOCATION", "US"))

    def ds(self, scale):
        return f"{self.project}.{self.base}" if scale == 1 else f"{self.project}.{self.base}_{scale}x"

    def run(self, sql, ds, params=None, dry=False):
        config = self.bq.QueryJobConfig(
            default_dataset=ds, use_query_cache=False, dry_run=dry,
            query_parameters=[
                self.bq.ScalarQueryParameter(k, "INT64" if isinstance(v, int) else "STRING", v)
                for k, v in (params or {}).items()
            ],
        )
        return self.client.query(sql, job_config=config)

    def measure(self, sql, ds, params):
        times = []
        for _ in range(self.runs):
            job = self.run(sql, ds, params)
            df = job.result().to_dataframe(create_bqstorage_client=False)
            times.append((job.ended - job.started).total_seconds())
        return df, {"seconds": statistics.median(times), "bytes": job.total_bytes_processed,
                    "billed": job.total_bytes_billed, "slot_ms": job.slot_millis, "rows_read": rows_read(job)}

    def drop(self, ds, table):
        self.client.delete_table(f"{ds}.{table}", not_found_ok=True)


def bq_scale(bq, scale):
    ds = bq.ds(scale)
    print(f"== BigQuery {scale}× ({ds})")
    sid = int(bq.run(
        "SELECT MIN(id_student) AS s FROM fact_enrollment WHERE code_module = @m AND code_presentation = @p",
        ds, {"m": MODULE, "p": PRESENTATION}).result().to_dataframe(create_bqstorage_client=False)["s"][0])
    params = {
        "br4_all": {"week_no": WEEK},
        "br4_list": {"week_no": WEEK, "code_module": MODULE, "code_presentation": PRESENTATION},
        "br7_cohort": {"code_module": MODULE, "code_presentation": PRESENTATION},
        "br7_student": {"id_student": sid, "code_module": MODULE, "code_presentation": PRESENTATION},
    }
    # Phần đọc fact_enrollment như nhau ở cả 3 mức; dry run bảng thường cho số chính xác.
    enroll = bq.run("SELECT id_student, code_module, code_presentation, final_result FROM fact_enrollment",
                    ds, dry=True).total_bytes_processed
    tables, results = {}, {key: {} for key, *_ in BQ_QUERIES}
    try:
        for level, _, table, spec in BQ_LEVELS:
            bq.run(f"CREATE OR REPLACE TABLE `{ds}.{table}`\n{spec}\nAS SELECT * FROM `{ds}.fact_student_week`",
                   ds).result()
            t = bq.client.get_table(f"{ds}.{table}")
            tables[level] = {"rows": t.num_rows, "bytes": t.num_bytes}
            for key, _, name, _ in BQ_QUERIES:
                sql = rename_table((BQ_SQL / f"{name}.sql").read_text(encoding="utf-8"), "fact_student_week", table)
                df, m = bq.measure(sql, ds, params[key])
                results[key][level] = (df, m)
                print(f"   {level:6} {key:12} {mb(m['bytes']):>10} {m['rows_read']:>10,} dòng "
                      f"{m['slot_ms']:>6,} slot ms {m['seconds']:.2f}s")
    finally:
        for _, _, table, _ in BQ_LEVELS:
            bq.drop(ds, table)
    same = {key: all(same_result(r["plain"][0], r[lv][0]) for lv in ("part", "clust"))
            for key, r in results.items()}
    metrics = {key: {lv: m for lv, (_, m) in r.items()} for key, r in results.items()}
    n_rows = {key: len(r["plain"][0]) for key, r in results.items()}
    br4 = results["br4_all"]["plain"][0]
    return {"scale": scale, "dataset": ds, "tables": tables, "metrics": metrics, "same": same,
            "n_rows": n_rows, "enroll_bytes": enroll, "student": sid,
            "br4_answer": (len(br4), int((br4["risk_score"] >= 2).sum()))}


# ---------------------------------------------------------------- PostgreSQL

def pg_time(conn, sql, runs):
    conn.execute(sql).fetchall()  # chạy nóng một lần
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        cur = conn.execute(sql)
        rows = cur.fetchall()
        times.append(time.perf_counter() - started)
    df = pd.DataFrame(rows, columns=[c.name for c in cur.description])
    plan = "\n".join(r[0] for r in conn.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql).fetchall())
    exec_ms = float(re.search(r"Execution Time: ([\d.]+) ms", plan).group(1))
    return df, {"seconds": statistics.median(times), "exec_ms": exec_ms, "plan": plan, "scans": scan_lines(plan)}


def scan_lines(plan):
    """Các bước quét fact_student_week trong kế hoạch, kèm số buffer của mỗi bước."""
    lines = plan.splitlines()
    out = []
    for i, line in enumerate(lines):
        if "fact_student_week" in line and "Scan" in line:
            scan = re.sub(r"\s*\(cost=.*", "", line.strip().lstrip("-> ").strip())
            buffers = next((l.strip() for l in lines[i + 1:i + 8] if l.strip().startswith("Buffers:")), "")
            out.append(f"{scan}; {buffers}" if buffers else scan)
    return out


def correlation(conn, schema):
    row = conn.execute("SELECT correlation FROM pg_stats WHERE schemaname = %s AND tablename = 'fact_student_week' "
                       "AND attname = 'week_no'", (schema,)).fetchone()
    return float(row[0]) if row else None


def pg_scale(conn, scale, runs):
    src = SCALES[scale][1]
    schema = "idx_test" if scale == 1 else f"idx_test_x{scale}"
    table = f"{schema}.fact_student_week"
    sql = PG_SQL.read_text(encoding="utf-8")
    print(f"== PostgreSQL {scale}× (bản sao của {src}.fact_student_week trong schema {schema})")
    out = {"scale": scale, "schema": schema, "levels": {}}
    try:
        conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        conn.execute(f"CREATE SCHEMA {schema}")
        conn.execute("SET synchronize_seqscans = off")  # giữ đúng thứ tự dòng của bảng gốc khi chép
        conn.execute(f"CREATE TABLE {table} AS SELECT * FROM {src}.fact_student_week")
        conn.execute(f"ALTER TABLE {table} ADD PRIMARY KEY ({', '.join(PG_PK)})")
        conn.execute(f"VACUUM (ANALYZE, PARALLEL 0) {table}")
        conn.execute(f"SET search_path TO {schema}, {src}")  # fact_enrollment lấy từ kho thật
        steps = [
            ("pk", "Chỉ khóa chính", None),
            ("index", "+ chỉ mục B+-tree", PG_INDEX_DDL.format(table=table)),
            ("cluster", "+ CLUSTER theo chỉ mục", PG_CLUSTER_DDL.format(table=table)),
        ]
        for level, label, ddl in steps:
            build = None
            if ddl:
                started = time.perf_counter()
                conn.execute(ddl)
                conn.execute(f"VACUUM (ANALYZE, PARALLEL 0) {table}")
                build = time.perf_counter() - started
            df, m = pg_time(conn, sql, runs)
            sizes = conn.execute(f"SELECT pg_relation_size('{table}'), pg_indexes_size('{table}')").fetchone()
            out["levels"][level] = {"label": label, "df": df, "build_seconds": build, "table_bytes": sizes[0],
                                    "index_bytes": sizes[1], "corr": correlation(conn, schema), **m}
            print(f"   {level:8} {m['seconds'] * 1000:8.1f} ms  corr(week_no)={out['levels'][level]['corr']:.3f}")
            for s in m["scans"]:
                print(f"            {s}")
        if scale == 1:
            out["write"] = pg_write_cost(conn, schema, src, runs=3)
    finally:
        conn.execute("RESET search_path")
        conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    lv = out["levels"]
    out["same"] = all(same_result(lv["pk"]["df"], lv[k]["df"]) for k in ("index", "cluster"))
    out["n_rows"] = len(lv["pk"]["df"])
    out["n_risk"] = int((lv["pk"]["df"]["risk_score"] >= 2).sum())
    return out


def pg_write_cost(conn, schema, src, runs):
    """Chi phí ghi (slide 101): INSERT cả bảng vào bảng rỗng, chỉ khóa chính so với có thêm chỉ mục."""
    t = f"{schema}.write_test"
    res = {}
    for label, extra in (("pk", False), ("index", True)):
        times = []
        for _ in range(runs):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
            conn.execute(f"CREATE TABLE {t} (LIKE {src}.fact_student_week)")
            conn.execute(f"ALTER TABLE {t} ADD PRIMARY KEY ({', '.join(PG_PK)})")
            if extra:
                conn.execute(PG_INDEX_DDL.replace(PG_INDEX, "ix_write_test").format(table=t))
            started = time.perf_counter()
            conn.execute(f"INSERT INTO {t} SELECT * FROM {src}.fact_student_week")
            times.append(time.perf_counter() - started)
        res[label] = statistics.median(times)
        print(f"   ghi {label:6} {res[label]:.2f}s")
    conn.execute(f"DROP TABLE IF EXISTS {t}")
    return res


# ---------------------------------------------------------------- báo cáo

def ratio(a, b):
    return f"{a / b:,.1f}×" if b else "—"


def ok(flag):
    return "giống hệt" if flag else "**KHÁC** (cần xem lại)"


def write_doc(bq_res, pg_res, runs):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    L = [
        "# Chỉ mục cho `fact_student_week` (trang Cảnh báo BR4, trang Sinh viên BR7)",
        "",
        f"Đo lúc {now}. Mỗi truy vấn chạy {runs} lần, thời gian lấy trung vị; BigQuery tắt cache kết quả.",
        "File này do `scripts/index_student_week.py` tự sinh (`make indexing`). Đo trên bảng thử, cùng dữ liệu với",
        "kho thật, tạo khi đo rồi xóa; bảng thật không bị đụng tới.",
        "",
        "## Cách lưu được đo",
        "",
        "BigQuery, theo `TUNING` trong `etl/04_load_bq.py`:",
        "",
        "```sql",
        "CREATE TABLE fact_student_week (...)",
        BQ_LEVELS[2][3],
        "```",
        "",
        "PostgreSQL, theo `INDEXES` trong `etl/05_load_pg.py` (khóa chính có sẵn: "
        f"`({', '.join(PG_PK)})`):",
        "",
        "```sql",
        PG_INDEX_DDL.format(table="fact_student_week") + ";",
        PG_CLUSTER_DDL.format(table="fact_student_week") + ";",
        "```",
        "",
    ]
    for r in bq_res:
        s = r["scale"]
        L += [
            f"## BigQuery {s}× (`{r['dataset']}`)",
            "",
            "| Mức | Dòng | Dung lượng bảng |",
            "|---|---:|---:|",
        ]
        for level, label, _, _ in BQ_LEVELS:
            L.append(f"| {label} | {r['tables'][level]['rows']:,} | {mb(r['tables'][level]['bytes'])} |")
        L += [
            "",
            f"Tham số: tuần {WEEK}, đợt {MODULE} {PRESENTATION}, sinh viên {r['student']}. "
            f"Phần đọc `fact_enrollment` (giống nhau ở mọi mức) là {mb(r['enroll_bytes'])}.",
            "",
            "| Truy vấn | Mức | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for key, desc, name, _ in BQ_QUERIES:
            for level, label, _, _ in BQ_LEVELS:
                m = r["metrics"][key][level]
                L.append(f"| {desc} (`{name}`) | {label} | {mb(m['bytes'])} | {mb(m['billed'])} | "
                         f"{m['rows_read']:,} | {m['slot_ms']:,} | {m['seconds']:.2f} |")
        L += ["", "Kết quả 3 mức: " + "; ".join(
            f"`{name}` {ok(r['same'][key])} ({r['n_rows'][key]:,} dòng)" for key, _, name, _ in BQ_QUERIES) + ".", ""]
    if 5 not in [r["scale"] for r in bq_res]:
        L += ["**BigQuery 5×: chưa đo.** Ba bản sao 5× (~1,9 GB) vượt hạn mức lưu trữ 10 GB của gói Sandbox "
              "(project đang dùng ~8,6 GB; bảng vừa xóa vẫn tính vào hạn mức trong thời gian time travel).", ""]
    for r in pg_res:
        s = r["scale"]
        lv = r["levels"]
        L += [
            f"## PostgreSQL {s}× (bản sao trong schema `{r['schema']}`)",
            "",
            f"Truy vấn: [sql/optimize/br4_week4_pg.sql](../sql/optimize/br4_week4_pg.sql), BR4 tuần {WEEK} toàn trường.",
            "",
            "| Mức | Thời gian (ms) | Execution Time (ms) | Tương quan `week_no` | Tạo (s) | Bảng | Chỉ mục (gồm khóa chính) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for level in ("pk", "index", "cluster"):
            x = lv[level]
            build = f"{x['build_seconds']:.1f}" if x["build_seconds"] is not None else "—"
            L.append(f"| {x['label']} | {x['seconds'] * 1000:,.1f} | {x['exec_ms']:,.1f} | {x['corr']:.3f} | {build} | "
                     f"{mb(x['table_bytes'])} | {mb(x['index_bytes'])} |")
        L += ["", "Cách quét `fact_student_week` (phía `w` tuần 4 và phía `p` tuần 3):", ""]
        for level in ("pk", "index", "cluster"):
            L.append(f"- **{lv[level]['label']}**")
            L += [f"  - `{scan}`" for scan in lv[level]["scans"]]
        L += ["", f"Kết quả 3 mức: {ok(r['same'])} ({r['n_rows']:,} lượt còn học, {r['n_risk']:,} có risk_score ≥ 2).", ""]
        if "write" in r:
            w = r["write"]
            L += [
                "**Chi phí ghi:** INSERT toàn bộ bảng vào bảng rỗng (trung vị 3 lần):",
                "",
                "| Bảng đích | Thời gian (s) |",
                "|---|---:|",
                f"| Chỉ khóa chính | {w['pk']:.2f} |",
                f"| Khóa chính + chỉ mục | {w['index']:.2f} |",
                "",
                f"Chỉ mục làm việc ghi chậm thêm {(w['index'] / w['pk'] - 1) * 100:.0f}%.",
                "",
            ]
    L += ["## Kế hoạch truy vấn PostgreSQL đầy đủ", ""]
    for r in pg_res:
        for level in ("pk", "index", "cluster"):
            x = r["levels"][level]
            L += [f"<details><summary>{r['scale']}× — {x['label']}</summary>", "", "```", x["plan"], "```", "",
                  "</details>", ""]
    DOC.write_text("\n".join(L), encoding="utf-8")
    give_back_to_owner(DOC)
    print(f"Đã ghi {DOC.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=5, help="số lần chạy mỗi truy vấn (lấy trung vị)")
    # BigQuery mặc định chỉ 1×: 3 bản sao 5× (~1,9 GB) vượt hạn mức 10 GB của gói Sandbox, vì kho đã dùng ~8,6 GB.
    parser.add_argument("--bq-scales", type=int, nargs="*", default=[1], choices=sorted(SCALES),
                        help="đo BigQuery trên kho nào (5× cần make scale và đủ hạn mức lưu trữ)")
    parser.add_argument("--pg-scales", type=int, nargs="*", default=[1, 5], choices=sorted(SCALES),
                        help="đo PostgreSQL trên kho nào (5× cần make scale trước)")
    args = parser.parse_args()

    bq = BigQuery(args.runs)
    bq_res = [bq_scale(bq, s) for s in args.bq_scales]
    with pg_connect() as conn:
        pg_res = [pg_scale(conn, s, args.runs) for s in args.pg_scales]
    write_doc(bq_res, pg_res, args.runs)
    if not all(all(r["same"].values()) for r in bq_res) or not all(r["same"] for r in pg_res):
        sys.exit("Có mức cho kết quả khác nhau, xem docs/indexing.md")


if __name__ == "__main__":
    main()
