"""Việc 1.11: 4 ví dụ tối ưu có số đo, ghi docs/optimization.md.

  1. Phân vùng fact_student_week theo week_no (BigQuery)
  2. Gom cụm fact_vle_daily theo code_module, code_presentation (BigQuery)
  3. Bảng tổng hợp sẵn cho app: mart BR2 của TV3 (BigQuery)
  4. Chỉ mục PostgreSQL trên fact_vle_daily

Mỗi truy vấn chạy --runs lần (tắt cache BigQuery), lấy trung vị thời gian; bytes quét lấy từ job.
Mỗi ví dụ kiểm hai bên trước/sau ra cùng kết quả. Bảng tối ưu tên opt_* nằm cạnh bảng gốc
trong dataset BQ_DATASET; bảng gốc không bị đụng tới. Chỉ mục PostgreSQL được giữ lại sau khi chạy
(make load-pg tạo lại bảng nên sẽ mất, chạy lại script này để có lại).

Chạy trong container, sau make all. Ví dụ 3 cần mart: python scripts/build_tv3_marts.py --apply
    python scripts/optimize.py              # cũng chính là: make optimize
    python scripts/optimize.py --runs 3
"""
import argparse
import datetime
import os
import re
import statistics
import sys
import time
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
from common import give_back_to_owner  # noqa: E402

SQL_DIR = ROOT / "sql" / "optimize"
DOC = ROOT / "docs" / "optimization.md"

PART_TABLE = "opt_fact_student_week_part"
CLUST_TABLE = "opt_fact_vle_daily_clust"
MART_TABLE = "tv3_br2_weekly_mart"
PG_INDEX = "ix_fact_vle_daily_offering"
MODULE, PRESENTATION = "BBB", "2014J"  # đợt dùng cho ví dụ 3 (ví dụ 2, 4 ghi sẵn trong file SQL)
PRUNE_LINE = "      AND p.week_no = 3\n"  # dòng lọc hằng số trong sql/optimize/br4_week4.sql

PART_DDL = (
    "CREATE OR REPLACE TABLE `{ds}.{table}`\n"
    "PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(-4, 39, 1))\n"
    "AS SELECT * FROM `{ds}.fact_student_week`"
)
CLUST_DDL = (
    "CREATE OR REPLACE TABLE `{ds}.{table}`\n"
    "CLUSTER BY code_module, code_presentation\n"
    "AS SELECT * FROM `{ds}.fact_vle_daily`"
)
PG_INDEX_DDL = (
    f"CREATE INDEX {PG_INDEX} ON fact_vle_daily\n"
    "    (code_module, code_presentation, week_no) INCLUDE (id_site, sum_click)"
)


def mb(n):
    return f"{n / 1e6:,.1f} MB"


def ratio(before, after):
    return f"{before / after:,.1f}×" if after else "—"


def rename_table(sql, old, new):
    return re.sub(rf"\b{old}\b", new, sql)


def normalize(df):
    """Đưa về dạng so được giữa engine: Decimal -> float, làm tròn, sắp theo mọi cột."""
    df = df.copy()
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = df[col].astype(float)
        if pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].round(6)
    return df.sort_values(list(df.columns)).reset_index(drop=True)


def same_result(a, b):
    try:
        pd.testing.assert_frame_equal(normalize(a), normalize(b[a.columns]), check_dtype=False)
        return True
    except AssertionError:
        return False


# ---------------------------------------------------------------- BigQuery

class BigQuery:
    def __init__(self, runs):
        from google.cloud import bigquery

        self.bq = bigquery
        self.runs = runs
        self.project = os.environ["GCP_PROJECT_ID"]
        self.dataset = os.getenv("BQ_DATASET", "oulad")
        self.ds = f"{self.project}.{self.dataset}"
        self.client = bigquery.Client(project=self.project, location=os.getenv("BQ_LOCATION", "US"))

    def ddl(self, template, table):
        sql = template.format(ds=self.ds, table=table)
        started = time.perf_counter()
        job = self.client.query(sql, job_config=self.bq.QueryJobConfig(default_dataset=self.ds))
        job.result()
        return {"sql": sql.replace(f"{self.project}.", ""), "seconds": time.perf_counter() - started,
                "bytes": job.total_bytes_processed}

    def has_table(self, table):
        from google.api_core.exceptions import NotFound

        try:
            self.client.get_table(f"{self.ds}.{table}")
            return True
        except NotFound:
            return False

    def measure(self, sql, params=None):
        config = self.bq.QueryJobConfig(
            default_dataset=self.ds,
            use_query_cache=False,
            query_parameters=[self.bq.ScalarQueryParameter(k, "STRING", v) for k, v in (params or {}).items()],
        )
        times = []
        for _ in range(self.runs):
            job = self.client.query(sql, job_config=config)
            df = job.result().to_dataframe(create_bqstorage_client=False)
            times.append((job.ended - job.started).total_seconds())
        return df, {
            "seconds": statistics.median(times),
            "bytes": job.total_bytes_processed,
            "billed": job.total_bytes_billed,
            "slot_ms": job.slot_millis,
            "rows_read": rows_read(job),
        }


def rows_read(job):
    """Tổng số dòng các bước đọc thẳng từ bảng (READ ... FROM <bảng>), lấy từ kế hoạch truy vấn."""
    total = 0
    for stage in job.query_plan:
        reads_table = any(
            step.kind == "READ"
            and any(sub.startswith("FROM ") and "__stage" not in sub for sub in step.substeps)
            for step in stage.steps
        )
        if reads_table:
            total += stage.records_read or 0
    return total


def example_partition(bq):
    """Ví dụ 1: BR4 tuần 4 trên bảng gốc và bảng phân vùng, có và không có dòng lọc hằng số."""
    print("== Ví dụ 1: phân vùng fact_student_week theo week_no")
    ddl = bq.ddl(PART_DDL, PART_TABLE)
    explicit = (SQL_DIR / "br4_week4.sql").read_text(encoding="utf-8")
    assert PRUNE_LINE in explicit, "sql/optimize/br4_week4.sql thiếu dòng lọc p.week_no = 3"
    via_join = explicit.replace(PRUNE_LINE, "")
    variants = [
        ("Bảng gốc", "lọc tuần qua phép nối", via_join, "fact_student_week"),
        ("Bảng gốc", "thêm `p.week_no = 3`", explicit, "fact_student_week"),
        ("Phân vùng", "lọc tuần qua phép nối", via_join, PART_TABLE),
        ("Phân vùng", "thêm `p.week_no = 3`", explicit, PART_TABLE),
    ]
    rows, frames = [], []
    for table_label, query_label, sql, table in variants:
        df, m = bq.measure(rename_table(sql, "fact_student_week", table))
        frames.append(df)
        rows.append({"table": table_label, "query": query_label, **m})
        print(f"   {table_label:10} {query_label:24} {mb(m['bytes']):>10} {m['rows_read']:>10,} dòng {m['seconds']:.2f}s")
    return {"ddl": ddl, "rows": rows, "same": all(same_result(frames[0], f) for f in frames[1:]),
            "answer": frames[0].iloc[0].to_dict()}


def example_cluster(bq):
    print("== Ví dụ 2: gom cụm fact_vle_daily theo code_module, code_presentation")
    ddl = bq.ddl(CLUST_DDL, CLUST_TABLE)
    sql = (SQL_DIR / "vle_offering_week.sql").read_text(encoding="utf-8")
    before_df, before = bq.measure(sql)
    after_df, after = bq.measure(rename_table(sql, "fact_vle_daily", CLUST_TABLE))
    for label, m in (("trước", before), ("sau", after)):
        print(f"   {label:6} {mb(m['bytes']):>10} {m['rows_read']:>10,} dòng {m['seconds']:.2f}s")
    return {"ddl": ddl, "before": before, "after": after, "same": same_result(before_df, after_df),
            "n_rows": len(after_df)}


def example_mart(bq):
    print("== Ví dụ 3: bảng tổng hợp sẵn cho app (mart BR2 của TV3)")
    if not bq.has_table(MART_TABLE):
        sys.exit(f"Thiếu {bq.dataset}.{MART_TABLE}: chạy python scripts/build_tv3_marts.py --apply trước")
    raw = (ROOT / "sql" / "bigquery" / "br2_vle_weekly.sql").read_text(encoding="utf-8").strip().rstrip(";")
    raw = raw[: raw.rfind("ORDER BY")]  # bỏ ORDER BY cuối để bọc thành truy vấn con
    before_sql = (
        f"SELECT * FROM (\n{raw}\n)\n"
        "WHERE code_module = @code_module AND code_presentation = @code_presentation"
    )
    after_sql = (ROOT / "sql" / "bigquery" / "br2_dashboard.sql").read_text(encoding="utf-8")
    params = {"code_module": MODULE, "code_presentation": PRESENTATION}
    before_df, before = bq.measure(before_sql, params)
    after_df, after = bq.measure(after_sql, params)
    for label, m in (("trước", before), ("sau", after)):
        print(f"   {label:6} {mb(m['bytes']):>10} {m['rows_read']:>10,} dòng {m['seconds']:.2f}s")
    mart = bq.client.get_table(f"{bq.ds}.{MART_TABLE}")
    return {"before": before, "after": after, "same": same_result(after_df, before_df),
            "n_rows": len(after_df), "mart_rows": mart.num_rows, "mart_bytes": mart.num_bytes}


# ---------------------------------------------------------------- PostgreSQL

def pg_connect():
    import psycopg

    return psycopg.connect(
        f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={os.getenv('POSTGRES_PORT', '5432')} "
        f"user={os.getenv('POSTGRES_USER', 'oulad')} password={os.getenv('POSTGRES_PASSWORD', 'oulad')} "
        f"dbname={os.getenv('POSTGRES_DB', 'oulad')}",
        autocommit=True,  # VACUUM không chạy được trong transaction
    )


def pg_measure(conn, sql, runs):
    conn.execute(sql).fetchall()  # chạy nóng một lần để hai bên cùng đọc từ bộ đệm
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        cur = conn.execute(sql)
        rows = cur.fetchall()
        times.append(time.perf_counter() - started)
    df = pd.DataFrame(rows, columns=[c.name for c in cur.description])
    plan = "\n".join(r[0] for r in conn.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql).fetchall())
    return df, {"seconds": statistics.median(times), "plan": plan, "scan": scan_line(plan)}


def scan_line(plan):
    """Dòng quét fact_vle_daily trong kế hoạch, kèm số buffer của nó."""
    lines = plan.splitlines()
    for i, line in enumerate(lines):
        if "fact_vle_daily" in line and "Scan" in line:
            scan = re.sub(r"\s*\(cost=.*", "", line.strip().lstrip("-> ").strip())
            buffers = next((l.strip() for l in lines[i + 1:i + 6] if l.strip().startswith("Buffers:")), "")
            return f"{scan}; {buffers}" if buffers else scan
    return "?"


def example_pg_index(runs):
    print("== Ví dụ 4: chỉ mục PostgreSQL trên fact_vle_daily")
    sql = (SQL_DIR / "vle_offering_week.sql").read_text(encoding="utf-8")
    with pg_connect() as conn:
        conn.execute("SET search_path TO public")
        conn.execute(f"DROP INDEX IF EXISTS {PG_INDEX}")
        before_df, before = pg_measure(conn, sql, runs)
        started = time.perf_counter()
        conn.execute(PG_INDEX_DDL)
        # cập nhật visibility map để quét được chỉ trên chỉ mục; PARALLEL 0 vì /dev/shm của container chỉ 64 MB
        conn.execute("VACUUM (ANALYZE, PARALLEL 0) fact_vle_daily")
        build_seconds = time.perf_counter() - started
        after_df, after = pg_measure(conn, sql, runs)
        index_bytes, table_bytes = conn.execute(
            f"SELECT pg_relation_size('{PG_INDEX}'), pg_relation_size('fact_vle_daily')"
        ).fetchone()
    for label, m in (("trước", before), ("sau", after)):
        print(f"   {label:6} {m['seconds'] * 1000:8.1f} ms  {m['scan']}")
    return {"before": before, "after": after, "same": same_result(before_df, after_df),
            "build_seconds": build_seconds, "index_bytes": index_bytes, "table_bytes": table_bytes}


# ---------------------------------------------------------------- báo cáo

def ok(flag):
    return "giống hệt" if flag else "**KHÁC** (cần xem lại)"


def write_doc(r1, r2, r3, r4, runs):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    p1 = {(row["table"], row["query"]): row for row in r1["rows"]}
    base1 = p1[("Bảng gốc", "lọc tuần qua phép nối")]
    best1 = p1[("Phân vùng", "thêm `p.week_no = 3`")]
    a1 = r1["answer"]
    lines = [
        "# Tối ưu truy vấn (việc 1.11)",
        "",
        f"Đo lúc {now}. Mỗi truy vấn chạy {runs} lần, thời gian lấy trung vị; BigQuery tắt cache kết quả.",
        "File này do `scripts/optimize.py` tự sinh; chạy lại `make optimize` để cập nhật.",
        "Mỗi ví dụ đều so kết quả trước/sau tối ưu, hai bên phải ra giống hệt.",
        "",
        "## Tóm tắt",
        "",
        "| # | Kỹ thuật | Engine | Truy vấn | Chỉ số | Trước | Sau | Giảm |",
        "|---|---|---|---|---|---:|---:|---:|",
        f"| 1 | Phân vùng `fact_student_week` theo `week_no` | BigQuery | BR4 tuần 4 | bytes quét | "
        f"{mb(base1['bytes'])} | {mb(best1['bytes'])} | {ratio(base1['bytes'], best1['bytes'])} |",
        f"| 2 | Gom cụm `fact_vle_daily` theo module, kỳ | BigQuery | click 1 đợt theo tuần × loại | bytes quét | "
        f"{mb(r2['before']['bytes'])} | {mb(r2['after']['bytes'])} | {ratio(r2['before']['bytes'], r2['after']['bytes'])} |",
        f"| 3 | Bảng tổng hợp sẵn cho app (mart BR2) | BigQuery | biểu đồ BR2 của 1 đợt | bytes quét | "
        f"{mb(r3['before']['bytes'])} | {mb(r3['after']['bytes'])} | {ratio(r3['before']['bytes'], r3['after']['bytes'])} |",
        f"| 4 | Chỉ mục trên `fact_vle_daily` | PostgreSQL | như ví dụ 2 | thời gian | "
        f"{r4['before']['seconds'] * 1000:,.1f} ms | {r4['after']['seconds'] * 1000:,.1f} ms | "
        f"{ratio(r4['before']['seconds'], r4['after']['seconds'])} |",
        "",
        "Với BigQuery, bytes quét là chỉ số chính: tiền và hạn mức 1 TB/tháng tính theo bytes. Thời gian ở",
        "cỡ dữ liệu này (dưới 1 GB) chủ yếu là chi phí khởi động job nên chênh ít và dao động giữa các lần chạy.",
        "Bytes tính tiền (`billed`) tối thiểu 10 MB cho mỗi bảng được đọc, nên ở bảng nhỏ nó cao hơn bytes quét.",
        "",
        "## 1. Phân vùng `fact_student_week` theo `week_no` (BigQuery)",
        "",
        "**Truy vấn:** [sql/optimize/br4_week4.sql](../sql/optimize/br4_week4.sql), danh sách nguy cơ BR4 tại tuần 4",
        "trên mọi đợt (câu 14). Trang Cảnh báo luôn hỏi theo một tuần cụ thể, nên phân vùng theo tuần khớp với cách app đọc.",
        "",
        "**Thay đổi:** tạo bảng phân vùng theo khoảng số nguyên, mỗi tuần một phân vùng (43 phân vùng, tuần −4 đến 38):",
        "",
        "```sql",
        r1["ddl"]["sql"],
        "```",
        "",
        f"Tạo bảng mất {r1['ddl']['seconds']:.1f} s, quét {mb(r1['ddl']['bytes'])}.",
        "",
        "| Bảng | Truy vấn | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in r1["rows"]:
        lines.append(
            f"| {row['table']} | {row['query']} | {mb(row['bytes'])} | {mb(row['billed'])} | "
            f"{row['rows_read']:,} | {row['slot_ms']:,} | {row['seconds']:.2f} |"
        )
    lines += [
        "",
        f"Kết quả 4 lần chạy: {ok(r1['same'])} ({int(a1['n_enrolled']):,} lượt còn học, "
        f"{int(a1['n_listed']):,} vào danh sách, độ chính xác {a1['precision_pct']}%).",
        "",
        "**Đọc kết quả:**",
        "",
        "- Truy vấn ghép `fact_student_week` với chính nó để lấy click tuần trước (`p.week_no = w.week_no - 1`).",
        "  Điều kiện này chỉ biết giá trị khi chạy phép nối, nên BigQuery không dùng nó để bỏ phân vùng.",
        "  Trên bảng phân vùng, phía `w` (`w.week_no = 4`) đã chỉ đọc tuần 4 nên số dòng đọc giảm gần một nửa,",
        "  nhưng phía `p` vẫn đọc cả bảng nên bytes quét không giảm.",
        "- Thêm điều kiện hằng số `p.week_no = 3` (không đổi kết quả) thì cả hai phía chỉ đọc đúng 1 phân vùng.",
        "  Bài học: phân vùng chỉ có tác dụng khi truy vấn lọc cột phân vùng bằng hằng số hoặc tham số.",
        "- Trên bảng gốc chưa phân vùng, thêm điều kiện đó không giảm bytes: BigQuery vẫn phải đọc cả cột.",
        "",
        "**Đánh đổi:** Google khuyên mỗi phân vùng nên lớn (cỡ từ 1 GB); ở đây mỗi phân vùng chỉ vài MB nên",
        "phân vùng là để minh họa, ở cỡ thật nên cân nhắc gom cụm theo `week_no` thay vì phân vùng.",
        "Mỗi lần nạp lại kho phải tạo lại bảng (hoặc cho `04_load_bq.py` nạp thẳng vào bảng có phân vùng).",
        "",
        "## 2. Gom cụm `fact_vle_daily` theo `code_module`, `code_presentation` (BigQuery)",
        "",
        "**Truy vấn:** [sql/optimize/vle_offering_week.sql](../sql/optimize/vle_offering_week.sql), click theo tuần ×",
        "loại hoạt động của BBB 2014J. Đây là phần nặng nhất của trang Học phần (BR2) khi người dùng chọn một đợt.",
        "",
        "**Thay đổi:** sắp dữ liệu theo module, kỳ khi ghi để các khối lưu trữ của một đợt nằm cạnh nhau:",
        "",
        "```sql",
        r2["ddl"]["sql"],
        "```",
        "",
        f"Tạo bảng mất {r2['ddl']['seconds']:.1f} s, quét {mb(r2['ddl']['bytes'])}.",
        "",
        "| | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, m in (("Bảng gốc", r2["before"]), ("Gom cụm", r2["after"])):
        lines.append(
            f"| {label} | {mb(m['bytes'])} | {mb(m['billed'])} | {m['rows_read']:,} | {m['slot_ms']:,} | {m['seconds']:.2f} |"
        )
    lines += [
        "",
        f"Kết quả: {ok(r2['same'])} ({r2['n_rows']} dòng).",
        "",
        "**Đọc kết quả:** bảng gốc phải đọc 5 cột của cả 8,5 triệu dòng rồi mới lọc. Bảng gom cụm cho BigQuery",
        "bỏ qua các khối không chứa BBB 2014J nên chỉ đọc khoảng 1/22 bảng (22 đợt). Khác phân vùng, gom cụm không",
        "cần cột kiểu ngày/số và không giới hạn số giá trị, hợp với cột chuỗi như mã module, mã kỳ.",
        "",
        "**Đánh đổi:** bytes ước tính trước khi chạy (dry run) không tính được phần bỏ qua nhờ gom cụm, chỉ biết sau",
        "khi chạy. Truy vấn không lọc theo module, kỳ (ví dụ tổng click toàn kho) không được lợi gì.",
        "",
        "## 3. Bảng tổng hợp sẵn cho app: mart BR2 (BigQuery)",
        "",
        "**Truy vấn:** biểu đồ BR2 của trang Học phần cho BBB 2014J (tham số `@code_module`, `@code_presentation`).",
        "",
        "- Trước: tính từ kho star bằng [sql/bigquery/br2_vle_weekly.sql](../sql/bigquery/br2_vle_weekly.sql)",
        "  (ghép `fact_vle_daily`, `fact_enrollment`, `dim_vle_site`, lịch tuần) rồi lọc đợt.",
        "- Sau: đọc [sql/bigquery/br2_dashboard.sql](../sql/bigquery/br2_dashboard.sql) từ bảng `tv3_br2_weekly_mart`",
        "  đã tính sẵn một lần bằng `python scripts/build_tv3_marts.py --apply` (mart do TV3 thiết kế, xem",
        "  [docs/tv3_marts.md](tv3_marts.md)).",
        "",
        f"Mart có {r3['mart_rows']:,} dòng, {mb(r3['mart_bytes'])}.",
        "",
        "| | Bytes quét | Bytes tính tiền | Dòng đọc từ bảng | Slot ms | Thời gian (s) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, m in (("Tính từ kho star", r3["before"]), ("Đọc mart", r3["after"])):
        lines.append(
            f"| {label} | {mb(m['bytes'])} | {mb(m['billed'])} | {m['rows_read']:,} | {m['slot_ms']:,} | {m['seconds']:.2f} |"
        )
    lines += [
        "",
        f"Kết quả: {ok(r3['same'])} ({r3['n_rows']} dòng, so trên các cột trang Học phần dùng).",
        "",
        f"**Đọc kết quả:** mỗi lần người dùng đổi đợt, app chỉ đọc mart {r3['mart_rows']:,} dòng đã tính sẵn thay vì",
        "ghép lại 8,5 triệu dòng click với bảng đăng ký và lịch tuần. Chi phí tính được trả một lần lúc dựng mart.",
        "Mart chưa gom cụm theo module, kỳ nên vẫn đọc cả mart; ở cỡ này không đáng làm thêm.",
        "",
        "**Đánh đổi:** mart phải dựng lại sau mỗi lần nạp kho, nếu quên thì app hiện số cũ; mart chỉ trả lời đúng",
        "các câu hỏi đã thiết kế trước (grain đợt × tuần × loại hoạt động).",
        "",
        "## 4. Chỉ mục PostgreSQL trên `fact_vle_daily`",
        "",
        "**Truy vấn:** giống ví dụ 2, chạy trên schema `public`.",
        "",
        "**Thay đổi:** khóa chính hiện có bắt đầu bằng `id_student` nên không giúp lọc theo đợt. Thêm chỉ mục bắt",
        "đầu bằng module, kỳ, và kèm (`INCLUDE`) hai cột truy vấn cần để PostgreSQL đọc thẳng từ chỉ mục, không",
        "phải mở bảng:",
        "",
        "```sql",
        PG_INDEX_DDL + ";",
        "VACUUM (ANALYZE, PARALLEL 0) fact_vle_daily;",
        "```",
        "",
        f"Tạo chỉ mục + VACUUM mất {r4['build_seconds']:.1f} s. Chỉ mục chiếm {mb(r4['index_bytes'])}"
        f" (bảng {mb(r4['table_bytes'])}).",
        "",
        "| | Thời gian (ms) | Cách quét `fact_vle_daily` |",
        "|---|---:|---|",
    ]
    for label, m in (("Không chỉ mục", r4["before"]), ("Có chỉ mục", r4["after"])):
        lines.append(f"| {label} | {m['seconds'] * 1000:,.1f} | `{m['scan']}` |")
    lines += [
        "",
        f"Kết quả: {ok(r4['same'])}. Thời gian đo phía client, sau một lần chạy nóng.",
        "",
        "**Đọc kết quả:** không có chỉ mục thì PostgreSQL quét tuần tự cả bảng để lấy các dòng của một đợt trong 22.",
        "Bảng lớn hơn bộ đệm `shared_buffers` nên dù đã chạy nóng, phần lớn trang vẫn phải đọc từ ngoài (`read=` trong",
        "`Buffers`). Có chỉ mục thì PostgreSQL nhảy thẳng tới đoạn của BBB 2014J, đọc ít trang hơn hẳn và không mở bảng",
        "(`Index Only Scan`).",
        "",
        "**Đánh đổi:** tốn thêm dung lượng và làm chậm lúc nạp dữ liệu. `make load-pg` tạo lại bảng nên chỉ mục mất,",
        "chạy lại `make optimize` để có lại. Khi so benchmark star / 3NF / bảng rộng cần ghi rõ có chỉ mục này hay không.",
        "",
        "## Kế hoạch truy vấn PostgreSQL đầy đủ",
        "",
    ]
    for label, m in (("Không chỉ mục", r4["before"]), ("Có chỉ mục", r4["after"])):
        lines += [f"<details><summary>{label}</summary>", "", "```", m["plan"], "```", "", "</details>", ""]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    give_back_to_owner(DOC)
    print(f"Đã ghi {DOC.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=5, help="số lần chạy mỗi truy vấn (lấy trung vị)")
    args = parser.parse_args()

    bq = BigQuery(args.runs)
    r1 = example_partition(bq)
    r2 = example_cluster(bq)
    r3 = example_mart(bq)
    r4 = example_pg_index(args.runs)
    write_doc(r1, r2, r3, r4, args.runs)
    if not all(r["same"] for r in (r1, r2, r3, r4)):
        sys.exit("Có ví dụ cho kết quả trước/sau khác nhau, xem docs/optimization.md")


if __name__ == "__main__":
    main()
