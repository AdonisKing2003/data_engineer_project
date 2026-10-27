"""Runner benchmark cũ của TV1 (lần đo 26/10/2026): star / 3NF / bảng rộng trên PostgreSQL và BigQuery, 1× và 5×.

Runner chính thức của việc 3.9 là scripts/benchmark_layouts.py (make bench), có kiểm đáp án và hash từng lượt.
Script này giữ lại để tái lập bộ số liệu lịch sử trong bench/results/historical_2026-10-26/; nó ghi vào
bench/results/tv1_runner/ và không đụng tới docs/benchmark.md.

Chạy 4 truy vấn trong sql/bench/{pg,bq}/{star,3nf,wide}/ (BR1 câu 7, BR2 câu 9, BR4 câu 14, BR6 câu 18).
Mỗi ô engine × quy mô × bố trí × truy vấn chạy --runs lần, lấy trung vị; PostgreSQL chạy nóng một lần
trước khi đo, BigQuery tắt cache. Ba bố trí của cùng engine và quy mô phải ra cùng kết quả.

Kết quả, trong bench/results/tv1_runner/:
    benchmark.raw.csv       mọi lần chạy
    benchmark.medians.csv   trung vị mỗi ô
    benchmark.html          biểu đồ
    benchmark.md            cấu hình, bảng số

Cần dựng trước: make all, make scale, và scripts/build_layouts.py cho từng engine/quy mô (xem docs/layouts.md).
BigQuery 5× bỏ bố trí bảng rộng: dataset oulad_wide_5x (~8 GB) vượt hạn mức 10 GB của Sandbox.

Chạy trong container:
    python scripts/run_bench.py
    python scripts/run_bench.py --skip-bq     # chỉ PostgreSQL
    python scripts/run_bench.py --runs 3
"""
import argparse
import datetime
import os
import statistics
import sys
import time
from pathlib import Path

import pandas as pd

from optimize import PG_INDEX, give_back_to_owner, pg_connect, same_result
from run_all import machine_info
from run_sql import _target, execute_sql

ROOT = Path(__file__).resolve().parents[1]
BENCH_SQL = ROOT / "sql" / "bench"
OUT_DIR = ROOT / "bench" / "results" / "tv1_runner"
DOC = OUT_DIR / "benchmark.md"
EXPLAIN_HEADING = "## Giải thích (viết tay, script giữ nguyên khi chạy lại)"

QUERIES = {  # file -> (BR, mô tả)
    "br1_q07": ("BR1 câu 7", "tỷ lệ nộp trễ TMA: fact_submission + dim_assessment"),
    "br2_q09": ("BR2 câu 9", "tỷ trọng click theo loại hoạt động: fact_vle_daily + dim_vle_site"),
    "br4_q14": ("BR4 câu 14", "danh sách nguy cơ tuần 4: fact_student_week nối với chính nó + fact_enrollment"),
    "br6_q18": ("BR6 câu 18", "khoảng cách IMD: fact_enrollment + dim_student"),
}
LAYOUTS = ("star", "3nf", "wide")
LAYOUT_LABELS = {"star": "Star", "3nf": "3NF", "wide": "Bảng rộng"}
LAYOUT_COLORS = {"star": "#2a78d6", "3nf": "#eb6834", "wide": "#1baf7a"}  # 3 ô đầu bảng màu tham chiếu
MATRIX = [  # (engine, quy mô, bố trí)
    *[("pg", scale, layout) for scale in (1, 5) for layout in LAYOUTS],
    *[("bq", 1, layout) for layout in LAYOUTS],
    ("bq", 5, "star"),
    ("bq", 5, "3nf"),
]


def read_query(engine, layout, query):
    return (BENCH_SQL / engine / layout / f"{query}.sql").read_text(encoding="utf-8")


def bench_pg(scale, layout, runs):
    schema = _target("pg", layout, scale)
    rows, frames = [], {}
    with pg_connect() as conn:
        conn.execute(f'SET search_path TO "{schema}"')
        for query in QUERIES:
            sql = read_query("pg", layout, query)
            conn.execute(sql).fetchall()  # chạy nóng
            for run in range(1, runs + 1):
                started = time.perf_counter()
                cur = conn.execute(sql)
                data = cur.fetchall()
                rows.append({"engine": "pg", "scale": scale, "layout": layout, "query": query, "run": run,
                             "seconds": time.perf_counter() - started, "bytes_processed": None})
            frames[query] = pd.DataFrame(data, columns=[c.name for c in cur.description])
    return rows, frames


def bench_bq(scale, layout, runs):
    rows, frames = [], {}
    for query in QUERIES:
        sql = read_query("bq", layout, query)
        for run in range(1, runs + 1):
            df, _, metrics = execute_sql(sql, engine="bq", scale=scale, layout=layout, use_query_cache=False)
            rows.append({"engine": "bq", "scale": scale, "layout": layout, "query": query, "run": run,
                         "seconds": metrics["elapsed_seconds"], "bytes_processed": metrics["bytes_processed"]})
        frames[query] = df
    return rows, frames


def summarize(raw, frames):
    medians = (
        raw.groupby(["engine", "scale", "layout", "query"], sort=False)
        .agg(median_s=("seconds", "median"), min_s=("seconds", "min"), max_s=("seconds", "max"),
             bytes_processed=("bytes_processed", "max"), runs=("run", "count"))
        .reset_index()
    )
    same = []
    for row in medians.itertuples():
        star = frames.get((row.engine, row.scale, "star", row.query))
        mine = frames[(row.engine, row.scale, row.layout, row.query)]
        same.append(True if row.layout == "star" else (star is not None and same_result(star, mine)))
    medians["same_as_star"] = same
    return medians


def write_chart(medians):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    groups = [f"{'PostgreSQL' if e == 'pg' else 'BigQuery'} {s}×"
              for e, s in dict.fromkeys(zip(medians["engine"], medians["scale"]))]
    fig = make_subplots(rows=2, cols=2, subplot_titles=[f"{br}: {desc.split(':')[0]}" for br, desc in QUERIES.values()],
                        vertical_spacing=0.16, horizontal_spacing=0.08)
    for i, query in enumerate(QUERIES):
        r, c = divmod(i, 2)
        for layout in LAYOUTS:
            part = medians[(medians["query"] == query) & (medians["layout"] == layout)]
            labels = [f"{'PostgreSQL' if e == 'pg' else 'BigQuery'} {s}×" for e, s in zip(part["engine"], part["scale"])]
            fig.add_trace(
                go.Bar(x=labels, y=part["median_s"], name=LAYOUT_LABELS[layout], legendgroup=layout,
                       showlegend=i == 0, marker={"color": LAYOUT_COLORS[layout], "line": {"color": "#fcfcfb", "width": 2}},
                       hovertemplate="%{x}<br>" + LAYOUT_LABELS[layout] + ": %{y:.3f} s<extra></extra>"),
                row=r + 1, col=c + 1,
            )
        fig.update_xaxes(categoryorder="array", categoryarray=groups, row=r + 1, col=c + 1)
        fig.update_yaxes(title_text="Trung vị (s)", rangemode="tozero", gridcolor="#e6e5e0", row=r + 1, col=c + 1)
    fig.update_layout(
        title="Benchmark star / 3NF / bảng rộng: thời gian trung vị mỗi truy vấn (thấp hơn là tốt hơn)",
        barmode="group", bargap=0.25, bargroupgap=0.05, height=760, width=1200,
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb", font={"color": "#0b0b0b"},
        legend={"orientation": "h", "y": 1.08, "x": 0},
    )
    path = OUT_DIR / "benchmark.html"
    fig.write_html(path, include_plotlyjs="cdn")
    return path


def fmt_mb(value):
    return "" if pd.isna(value) else f"{value / 1e6:,.1f}"


def write_doc(medians, runs, started_at, seconds_total, pg_settings):
    def cell(engine, scale, layout, query):
        row = medians[(medians.engine == engine) & (medians.scale == scale)
                      & (medians.layout == layout) & (medians["query"] == query)]
        return None if row.empty else row.iloc[0]

    def ratio_text(engine, scale, layout, query):
        base, other = cell(engine, scale, "star", query), cell(engine, scale, layout, query)
        if base is None or other is None:
            return "—"
        return f"{other.median_s / base.median_s:.2f}×"

    lines = [
        "# Benchmark star / 3NF / bảng rộng (việc 3.9)",
        "",
        f"Đo lúc {started_at}, chạy hết {seconds_total / 60:.1f} phút. File này do `scripts/run_bench.py` tự sinh;",
        "chạy lại `python scripts/run_bench.py` để cập nhật. Số liệu thô: `benchmark.raw.csv`, trung vị:",
        "`benchmark.medians.csv`, biểu đồ: `benchmark.html`, cùng thư mục với file này.",
        "",
        "## Cấu hình",
        "",
        "| | |",
        "|---|---|",
        f"| Máy | {machine_info()} |",
        f"| PostgreSQL | 16, container mặc định: `shared_buffers` {pg_settings['shared_buffers']}, `work_mem` {pg_settings['work_mem']}; "
        "chỉ có khóa chính theo grain ở mọi bố trí (bỏ chỉ mục tối ưu của optimization.md trước khi đo) |",
        "| BigQuery | Sandbox, vùng US, giá on-demand; tắt cache kết quả; thời gian là thời gian job (bắt đầu → kết thúc) |",
        f"| Lặp | {runs} lần mỗi ô, lấy trung vị; PostgreSQL `VACUUM ANALYZE` mọi bảng rồi chạy nóng 1 lần trước khi đo |",
        "| Bố trí | Star: kho chính. 3NF: `fact_submission`, `fact_vle_daily` bỏ cột mã đợt và tuần, tra lại qua dimension bằng view. Bảng rộng: mỗi fact nối sẵn mọi thuộc tính dimension. Chi tiết: [layouts.md](layouts.md) |",
        "| Không đo | BigQuery bảng rộng 5×: dataset khoảng 8 GB, cộng các dataset đang có thì vượt hạn mức 10 GB của Sandbox |",
        "",
        "## Truy vấn",
        "",
        "| Mã | BR | Nội dung |",
        "|---|---|---|",
    ]
    for query, (br, desc) in QUERIES.items():
        lines.append(f"| `{query}` | {br} | {desc} |")
    lines += [
        "",
        "Ba bố trí của cùng engine và quy mô cho kết quả "
        + ("**giống hệt nhau ở mọi ô**." if medians["same_as_star"].all()
           else "**khác nhau ở một số ô** (cột `same_as_star` trong CSV trung vị)."),
        "",
        "## Thời gian trung vị (giây)",
        "",
        "Trong ngoặc là tỷ lệ so với star cùng engine và quy mô (lớn hơn 1 là chậm hơn star).",
        "",
        "| Truy vấn | Engine | Quy mô | Star | 3NF | Bảng rộng |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for query, (br, _) in QUERIES.items():
        for engine, scale in dict.fromkeys(zip(medians.engine, medians.scale)):
            cells = []
            for layout in LAYOUTS:
                c = cell(engine, scale, layout, query)
                if c is None:
                    cells.append("—")
                elif layout == "star":
                    cells.append(f"{c.median_s:.3f}")
                else:
                    cells.append(f"{c.median_s:.3f} ({ratio_text(engine, scale, layout, query)})")
            lines.append(f"| {br} | {'PostgreSQL' if engine == 'pg' else 'BigQuery'} | {scale}× | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Bytes quét trên BigQuery (MB)",
        "",
        "Với BigQuery, tiền và hạn mức tính theo bytes quét nên đây là chỉ số chính.",
        "",
        "| Truy vấn | Quy mô | Star | 3NF | Bảng rộng |",
        "|---|---:|---:|---:|---:|",
    ]
    for query, (br, _) in QUERIES.items():
        for scale in (1, 5):
            cells = []
            for layout in LAYOUTS:
                c = cell("bq", scale, layout, query)
                cells.append("—" if c is None else fmt_mb(c.bytes_processed))
            lines.append(f"| {br} | {scale}× | " + " | ".join(cells) + " |")
    # Phần giải thích viết tay sau khi đọc số; chạy lại thì giữ nguyên phần đó, chỉ sinh lại phần trên.
    notes = "\n_Chưa có giải thích: viết tay ở đây sau khi đọc số liệu._\n"
    if DOC.exists() and EXPLAIN_HEADING in DOC.read_text(encoding="utf-8"):
        notes = DOC.read_text(encoding="utf-8").split(EXPLAIN_HEADING, 1)[1]
    DOC.write_text("\n".join(lines) + "\n\n" + EXPLAIN_HEADING + notes, encoding="utf-8")
    give_back_to_owner(DOC)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--skip-bq", action="store_true", help="chỉ chạy PostgreSQL")
    args = parser.parse_args()

    started_at = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    t0 = time.perf_counter()
    with pg_connect() as conn:
        conn.execute(f"DROP INDEX IF EXISTS public.{PG_INDEX}")  # để star 1× chỉ có khóa chính như các bố trí khác
        pg_settings = {name: conn.execute(f"SHOW {name}").fetchone()[0] for name in ("shared_buffers", "work_mem")}
        # Bảng vừa dựng xong sẽ bị autovacuum xử lý giữa lúc đo và tranh đĩa với truy vấn.
        # VACUUM ANALYZE trước để mọi bố trí cùng ở trạng thái ổn định (thống kê, visibility map).
        schemas = sorted({_target("pg", layout, scale) for engine, scale, layout in MATRIX if engine == "pg"})
        tables = conn.execute(
            "SELECT schemaname, tablename FROM pg_tables WHERE schemaname = ANY(%s) ORDER BY 1, 2", (schemas,)
        ).fetchall()
        print(f"VACUUM ANALYZE {len(tables)} bảng trong {', '.join(schemas)}", flush=True)
        for schema, table in tables:
            conn.execute(f'VACUUM (ANALYZE, PARALLEL 0) "{schema}"."{table}"')

    raw, frames = [], {}
    for engine, scale, layout in MATRIX:
        if engine == "bq" and args.skip_bq:
            continue
        print(f"== {engine} {scale}× {layout}", flush=True)
        rows, got = (bench_pg if engine == "pg" else bench_bq)(scale, layout, args.runs)
        raw += rows
        frames.update({(engine, scale, layout, q): df for q, df in got.items()})
        for q in QUERIES:
            secs = [r["seconds"] for r in rows if r["query"] == q]
            print(f"   {q}: trung vị {statistics.median(secs):.3f}s")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_df = pd.DataFrame(raw)
    medians = summarize(raw_df, frames)
    raw_df.to_csv(OUT_DIR / "benchmark.raw.csv", index=False)
    medians.to_csv(OUT_DIR / "benchmark.medians.csv", index=False)
    chart = write_chart(medians)
    write_doc(medians, args.runs, started_at, time.perf_counter() - t0, pg_settings)
    give_back_to_owner(OUT_DIR)
    print(f"Đã ghi {OUT_DIR.relative_to(ROOT)}/, {chart.relative_to(ROOT)}, {DOC.relative_to(ROOT)}")
    if not medians["same_as_star"].all():
        sys.exit("Có ô cho kết quả khác star, xem cột same_as_star")


if __name__ == "__main__":
    main()
