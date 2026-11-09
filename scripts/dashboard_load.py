"""Đo dữ liệu quét và thời gian tải từng trang dashboard trên BigQuery, lần mở đầu tiên; ghi docs/dashboard_load.md.

Script không tự viết lại truy vấn của trang: nó mở từng trang bằng AppTest của Streamlit (chạy đúng mã
app/Home.py ở trạng thái mặc định: đợt, tuần, sinh viên mặc định) và bắt mọi truy vấn app gửi lên
BigQuery qua Client.query_and_wait. Với mỗi truy vấn bị bắt:
  - tắt bộ nhớ đệm kết quả của BigQuery (use_query_cache=False), để lần nào cũng quét thật;
  - đo thời gian từ lúc gửi đến khi có DataFrame, như app nhận;
  - lấy bytes quét từ BigQuery (total_bytes_processed).
Trước mỗi lần mở trang, bộ nhớ đệm của Streamlit (st.cache_data) được xóa, nên đó là lần mở đầu tiên.
Trang "Hoạt động học tập" chỉ chạy truy vấn của tab đang mở, nên script mở tab đầu rồi chuyển sang tab
thứ hai, cộng cả hai.

Mỗi trang mở --runs lần; mỗi truy vấn lấy trung vị thời gian; thời gian của trang là tổng trung vị các
truy vấn (app chạy tuần tự). Kèm thời gian mở trang trong AppTest (gồm cả dựng giao diện) để tham khảo.

Chạy trong container, sau make all, khi kho chính đang ở dạng tối ưu (không chạy ngay sau make load-plain):
    python scripts/dashboard_load.py                        # cũng chính là: make dashboard-load
    python scripts/dashboard_load.py --runs 1 --pages warning progress
Một lượt đủ 8 trang quét khoảng 0,3 GB; --runs 3 khoảng 0,9 GB trên hạn mức 1 TB/tháng.
"""
import argparse
import datetime
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")  # bỏ cảnh báo của chế độ AppTest; đặt trước khi import streamlit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "etl"))
from common import give_back_to_owner  # noqa: E402

DOC = ROOT / "docs" / "dashboard_load.md"
HOME = ROOT / "app" / "Home.py"
COURSE_TAB_2 = "Click trước hạn TMA và điểm"

# (khóa, url_pathname mà AppTest gán cho trang, tên trang, các bước sau khi mở: (khóa session_state, giá trị))
PAGES = [
    ("overview", "", "Tổng quan", []),
    ("course", "render_course_page", "Hoạt động học tập (cả hai tab)", [("course_tab", COURSE_TAB_2)]),
    ("submissions", "Hoc_phan", "Nộp bài và điểm", []),
    ("warning", "Canh_bao", "Cảnh báo sớm và rút lui", []),
    ("faculty", "render_faculty_page", "Khoảng cách IMD", []),
    ("progress", "Sinh_vien", "Tiến độ so với lớp", []),
    ("forum", "render_student_page", "So với nhóm đạt", []),
    ("stream", "render_stream_page", "Click thời gian thực", []),
]

LOG = []  # truy vấn bị bắt trong lần mở trang đang đo


class _Fetched:
    """Thay cho RowIterator: app chỉ gọi .to_dataframe() trên kết quả của query_and_wait."""

    def __init__(self, df):
        self._df = df

    def to_dataframe(self, *args, **kwargs):
        return self._df


def install_recorder():
    """Bọc Client.query_and_wait: tắt cache BigQuery, đo thời gian và bytes của mọi truy vấn app gửi."""
    from google.cloud import bigquery

    original = bigquery.Client.query_and_wait

    def recorded(self, query, *args, job_config=None, **kwargs):
        if job_config is None:
            job_config = bigquery.QueryJobConfig()
        job_config.use_query_cache = False
        start = time.perf_counter()
        rows = original(self, query, *args, job_config=job_config, **kwargs)
        df = rows.to_dataframe(create_bqstorage_client=False)
        seconds = time.perf_counter() - start
        LOG.append({
            "sql": query,
            "params": {p.name: p.value for p in (job_config.query_parameters or [])},
            "bytes": rows.total_bytes_processed or 0,
            "rows": len(df),
            "seconds": seconds,
        })
        return _Fetched(df)

    bigquery.Client.query_and_wait = recorded


def query_names():
    """Văn bản SQL -> mã truy vấn trong app/data.py, để gọi tên truy vấn bị bắt."""
    from app.data import QUERY_FILES

    names = {}
    for query_id, paths in QUERY_FILES.items():
        path = paths.get("bigquery")
        if path is not None and path.is_file():
            names[path.read_text(encoding="utf-8").strip()] = query_id
    return names


def name_of(sql, names):
    found = names.get(sql.strip())
    if found:
        return found
    lines = [ln.strip() for ln in sql.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    return "SQL trong trang: " + (lines[0][:50] if lines else "?")


def check_tuned():
    """Kho chính phải đang tối ưu; ngay sau make load-plain thì số đo không phải của app thật."""
    from google.cloud import bigquery

    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.getenv("BQ_DATASET", "oulad")
    client = bigquery.Client(project=project, location=os.getenv("BQ_LOCATION", "US"))
    week = client.get_table(f"{project}.{dataset}.fact_student_week")
    vle = client.get_table(f"{project}.{dataset}.fact_vle_daily")
    if week.range_partitioning is None or not vle.clustering_fields:
        sys.exit("Kho chính trên BigQuery chưa phân vùng / gom cụm (có thể vừa chạy make load-plain): "
                 "chạy make tune rồi đo lại.")
    return project, dataset


def open_page(url, steps):
    """Mở một trang ở trạng thái mặc định với bộ nhớ đệm trống; trả về truy vấn bị bắt, thời gian, lỗi."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(HOME), default_timeout=600).run()  # lần chạy đầu luôn mở trang Tổng quan
    pages = {info["url_pathname"]: h for h, info in at._registered_pages.items()}
    if url not in pages:
        raise SystemExit(f"Không tìm thấy trang {url!r}; các trang hiện có: {sorted(pages)}")
    st.cache_data.clear()
    LOG.clear()
    start = time.perf_counter()
    at._page_hash = pages[url]
    at.run()
    for key, value in steps:
        at.session_state[key] = value
        at.run()
    wall = time.perf_counter() - start
    problems = [str(e.value) for e in at.exception] + [str(e.value) for e in at.error]
    return list(LOG), wall, problems


def measure(page, runs, names):
    key, url, title, steps = page
    attempts = []
    for _ in range(runs):
        queries, wall, problems = open_page(url, steps)
        if problems:
            raise SystemExit(f"Trang {title} báo lỗi: {problems[0]}")
        attempts.append((queries, wall))

    counts = {len(q) for q, _ in attempts}
    if len(counts) != 1:
        raise SystemExit(f"Trang {title}: số truy vấn khác nhau giữa các lần mở ({sorted(counts)}).")
    first = attempts[0][0]
    rows = []
    for i, q in enumerate(first):
        rows.append({
            "name": name_of(q["sql"], names),
            "params": q["params"],
            "rows": q["rows"],
            "bytes": q["bytes"],
            "seconds": statistics.median(a[0][i]["seconds"] for a in attempts),
        })
    return {
        "key": key,
        "title": title,
        "queries": rows,
        "bytes": sum(r["bytes"] for r in rows),
        "seconds": sum(r["seconds"] for r in rows),
        "wall": statistics.median(w for _, w in attempts),
    }


def mb(n):
    return f"{n / 1e6:,.1f} MB".replace(",", "X").replace(".", ",").replace("X", ".")


def sec(s):
    return f"{s:.1f} s".replace(".", ",")


def params_text(params):
    return ", ".join(f"{k}={v}" for k, v in params.items()) or "—"


def write_doc(results, runs, project, dataset):
    today = datetime.date.today().strftime("%d/%m/%Y")
    lines = [
        "# Tải trang dashboard trên BigQuery",
        "",
        f"Sinh bằng `python scripts/dashboard_load.py --runs {runs}` (`make dashboard-load`) ngày {today},"
        f" dataset `{project}.{dataset}`.",
        "",
        "Cách đo:",
        "",
        "- Mở từng trang bằng AppTest của Streamlit, ở trạng thái mặc định, chạy đúng mã của app.",
        "- Bắt mọi truy vấn app gửi lên BigQuery; tắt bộ nhớ đệm kết quả của BigQuery; xóa bộ nhớ đệm",
        "  của Streamlit trước mỗi lần mở, nên đây là lần mở đầu tiên.",
        "- Trang Hoạt động học tập: mở tab đầu rồi chuyển sang tab thứ hai, cộng cả hai.",
        f"- Mỗi trang mở {runs} lần; mỗi truy vấn lấy trung vị thời gian. Thời gian trang là tổng trung vị",
        "  các truy vấn; thời gian mở trang trong AppTest (gồm dựng giao diện) để tham khảo.",
        "",
        "## Theo trang",
        "",
        "| Trang | Số truy vấn | Dữ liệu quét | Thời gian truy vấn | Thời gian mở trang |",
        "|---|--:|--:|--:|--:|",
    ]
    for r in results:
        lines.append(f"| {r['title']} | {len(r['queries'])} | {mb(r['bytes'])} | {sec(r['seconds'])} | {sec(r['wall'])} |")
    lines.append(
        f"| **Cả {len(results)} trang** | **{sum(len(r['queries']) for r in results)}** |"
        f" **{mb(sum(r['bytes'] for r in results))}** | | |"
    )
    lines += [
        "",
        "## Theo truy vấn",
        "",
        "| Trang | Truy vấn | Tham số | Dòng trả về | Dữ liệu quét | Thời gian |",
        "|---|---|---|--:|--:|--:|",
    ]
    for r in results:
        for q in r["queries"]:
            n_rows = f"{q['rows']:,}".replace(",", ".")
            lines.append(
                f"| {r['title']} | `{q['name']}` | {params_text(q['params'])} | {n_rows}"
                f" | {mb(q['bytes'])} | {sec(q['seconds'])} |"
            )
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    give_back_to_owner(DOC)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3, help="số lần mở mỗi trang (mặc định 3)")
    parser.add_argument("--pages", nargs="+", choices=[p[0] for p in PAGES], help="chỉ đo các trang này")
    parser.add_argument("--no-doc", action="store_true", help="chỉ in kết quả, không ghi docs/dashboard_load.md")
    args = parser.parse_args()

    os.environ["DATA_BACKEND"] = "bigquery"  # đo đúng đường app chạy thật
    project, dataset = check_tuned()
    install_recorder()
    names = query_names()

    chosen = [p for p in PAGES if not args.pages or p[0] in args.pages]
    results = []
    for page in chosen:
        print(f"Đo trang {page[2]} ...", flush=True)
        r = measure(page, args.runs, names)
        results.append(r)
        print(f"  {len(r['queries'])} truy vấn, {mb(r['bytes'])}, truy vấn {sec(r['seconds'])},"
              f" mở trang {sec(r['wall'])}")
        for q in r["queries"]:
            print(f"    {q['name']:<32} {mb(q['bytes']):>10} {sec(q['seconds']):>7}  {params_text(q['params'])}")

    total = sum(r["bytes"] for r in results)
    print(f"Tổng {sum(len(r['queries']) for r in results)} truy vấn, {mb(total)}")
    if not args.no_doc:
        write_doc(results, args.runs, project, dataset)
        print(f"Đã ghi {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
