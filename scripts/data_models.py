"""Mô hình hóa từ quan hệ đến phi quan hệ: đo 2 mô hình phi quan hệ so với bảng phẳng, ghi docs/data_models.md.

  A. BigQuery dạng lồng (ARRAY<STRUCT>): nested_student_timeline, mỗi lượt đăng ký một dòng, tuần nằm trong mảng.
  B. PostgreSQL dạng tài liệu (JSONB): doc.student_timeline, mỗi lượt đăng ký một tài liệu.

Cả hai dựng từ fact_student_week và được so trên 2 kiểu truy vấn: lấy dòng thời gian của một sinh viên
(trang Sinh viên) và cắt ngang mọi sinh viên tại tuần 4 (trang Cảnh báo). Cách đo giống scripts/optimize.py:
chạy --runs lần lấy trung vị, BigQuery tắt cache, kiểm hai bên ra cùng kết quả.

Chạy trong container, sau make all:
    python scripts/data_models.py           # cũng chính là: make models
"""
import argparse
import datetime
import sys
import time
from pathlib import Path

from optimize import BigQuery, give_back_to_owner, mb, ok, pg_connect, pg_measure, ratio, same_result

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql" / "models"
DOC = ROOT / "docs" / "data_models.md"
NESTED_TABLE = "nested_student_timeline"


def read_sql(name):
    return (SQL_DIR / name).read_text(encoding="utf-8")


def bq_size(bq, table):
    t = bq.client.get_table(f"{bq.ds}.{table}")
    return t.num_rows, t.num_bytes


def experiment_nested(bq):
    print("== A. BigQuery dạng lồng")
    ddl = bq.ddl(read_sql("bq_build_nested.sql"), NESTED_TABLE)
    sizes = {name: bq_size(bq, name) for name in ("fact_student_week", NESTED_TABLE)}
    queries = {
        "timeline": (read_sql("timeline_flat.sql"), read_sql("bq_timeline_nested.sql")),
        "week4": ((ROOT / "sql" / "optimize" / "br4_week4.sql").read_text(encoding="utf-8"),
                  read_sql("bq_br4_week4_nested.sql")),
    }
    result = {"ddl": ddl, "sizes": sizes}
    for key, (flat_sql, nested_sql) in queries.items():
        flat_df, flat = bq.measure(flat_sql)
        nested_df, nested = bq.measure(nested_sql)
        result[key] = {"flat": flat, "nested": nested, "same": same_result(flat_df, nested_df), "n_rows": len(flat_df)}
        for label, m in (("phẳng", flat), ("lồng", nested)):
            print(f"   {key:8} {label:6} {mb(m['bytes']):>10} {m['slot_ms']:>7,} slot ms {m['seconds']:.2f}s")
    if result["week4"]["same"]:
        result["answer"] = flat_df.iloc[0].to_dict()
    return result


def experiment_document(runs):
    print("== B. PostgreSQL dạng tài liệu JSONB")
    with pg_connect() as conn:
        conn.execute("SET search_path TO public")
        started = time.perf_counter()
        conn.execute(read_sql("pg_build_document.sql"))
        build_seconds = time.perf_counter() - started
        sizes = {}
        for name in ("public.fact_student_week", "doc.student_timeline"):
            sizes[name] = conn.execute(
                f"SELECT (SELECT COUNT(*) FROM {name}), pg_total_relation_size('{name}')"
            ).fetchone()
        result = {"build_seconds": build_seconds, "sizes": sizes}
        queries = {
            "timeline": (read_sql("timeline_flat.sql"), read_sql("pg_timeline_document.sql")),
            "week4": (read_sql("pg_week4_flat.sql"), read_sql("pg_week4_document.sql")),
        }
        for key, (flat_sql, doc_sql) in queries.items():
            flat_df, flat = pg_measure(conn, flat_sql, runs)
            doc_df, doc = pg_measure(conn, doc_sql, runs)
            result[key] = {"flat": flat, "doc": doc, "same": same_result(flat_df, doc_df), "n_rows": len(flat_df)}
            for label, m in (("phẳng", flat), ("tài liệu", doc)):
                print(f"   {key:8} {label:8} {m['seconds'] * 1000:9.2f} ms")
    return result


def write_doc(a, b, runs):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    flat_rows, flat_bytes = a["sizes"]["fact_student_week"]
    nested_rows, nested_bytes = a["sizes"][NESTED_TABLE]
    pg_flat_rows, pg_flat_bytes = b["sizes"]["public.fact_student_week"]
    pg_doc_rows, pg_doc_bytes = b["sizes"]["doc.student_timeline"]

    def bq_row(label, m):
        return f"| {label} | {mb(m['bytes'])} | {m['slot_ms']:,} | {m['seconds']:.2f} |"

    def pg_ms(m):
        return f"{m['seconds'] * 1000:,.2f}"

    lines = [
        "# Mô hình hóa dữ liệu: từ quan hệ đến phi quan hệ",
        "",
        "## 1. Các mô hình dữ liệu dùng trong project",
        "",
        "Cùng dữ liệu OULAD được tổ chức theo nhiều mô hình, mỗi mô hình hợp với một kiểu truy cập.",
        "",
        "| Mô hình | Ở đâu trong project | Hợp với | Không hợp với |",
        "|---|---|---|---|",
        "| Quan hệ chuẩn hóa (3NF) | PostgreSQL schema `three_nf` (TV3, [layouts.md](layouts.md)) | Hệ thống ghi nhiều (OLTP): mỗi dữ kiện lưu một chỗ, sửa không lệch | Phân tích: phải nối nhiều bảng |",
        "| Mô hình chiều (star) | Kho chính: BigQuery `oulad`, PostgreSQL `public` ([design_levels.md](design_levels.md)) | Phân tích theo nhiều chiều, ít phép nối, dễ hiểu với người dùng | Ghi/sửa từng dòng |",
        "| Bảng rộng phi chuẩn hóa | PostgreSQL/BigQuery `wide` (TV3) | Truy vấn không cần nối | Tốn chỗ, đổi một thuộc tính phải sửa nhiều dòng |",
        "| Lưu trữ theo cột | Parquet (`data/warehouse`), BigQuery | Quét nhiều dòng, ít cột; nén tốt | Lấy trọn một dòng, ghi từng dòng |",
        "| **Dạng lồng (nested, repeated)** | BigQuery `nested_student_timeline` (mục 2) | Dữ liệu cha-con luôn đọc cùng nhau | Câu hỏi cắt ngang phần tử con của mọi dòng |",
        "| **Tài liệu (document, JSON)** | PostgreSQL `doc.student_timeline`, kiểu JSONB (mục 3) | Lấy trọn hồ sơ một đối tượng, cấu trúc linh hoạt | Tổng hợp trên nhiều tài liệu |",
        "| **Khóa-giá trị (key-value)** | State store của Spark Structured Streaming ([report_tv1.md](report_tv1.md) mục 4): khóa SV × đợt × tuần → tổng click | Cập nhật và tra cứu theo khóa rất nhanh | Mọi truy vấn không đi theo khóa |",
        "",
        "Mô hình đồ thị không dùng: các câu hỏi của 8 BR không cần duyệt quan hệ nhiều bước (kiểu \"bạn của bạn\").",
        "Quan hệ sinh viên - học liệu chỉ có một bước, nối bảng là đủ.",
        "",
        "Số đo so sánh 3NF / star / bảng rộng nằm ở [benchmark.md](benchmark.md). Tài liệu này đo hai mô hình phi quan",
        "hệ, cùng dựng từ `fact_student_week` (sinh viên × đợt × tuần), so với chính bảng phẳng đó.",
        "",
        f"Đo lúc {now}. Mỗi truy vấn chạy {runs} lần, thời gian lấy trung vị; BigQuery tắt cache.",
        "File này do `scripts/data_models.py` tự sinh; chạy lại `make models` để cập nhật.",
        "",
        "## 2. Dạng lồng trên BigQuery",
        "",
        "**Mô hình:** mỗi lượt đăng ký một dòng, các tuần nằm trong cột `weeks` kiểu `ARRAY<STRUCT<…>>`",
        "([sql/models/bq_build_nested.sql](../sql/models/bq_build_nested.sql)):",
        "",
        "```",
        "nested_student_timeline",
        "├── id_student, code_module, code_presentation      ← khóa, lưu 1 lần",
        "└── weeks: ARRAY of STRUCT                          ← 37–43 phần tử, sắp theo tuần",
        "        week_no, clicks_week, clicks_cum, avg_score_cum, n_tma_missed_cum, is_enrolled, …",
        "```",
        "",
        "| | Số dòng | Kích thước |",
        "|---|---:|---:|",
        f"| Bảng phẳng `fact_student_week` | {flat_rows:,} | {mb(flat_bytes)} |",
        f"| Bảng lồng `{NESTED_TABLE}` | {nested_rows:,} | {mb(nested_bytes)} |",
        "",
        f"Bảng lồng nhỏ hơn {ratio(flat_bytes, nested_bytes)} vì 3 cột khóa không còn lặp lại ở mỗi tuần.",
        "",
        "**Truy vấn 1: dòng thời gian của một sinh viên** (11391, AAA 2013J; trang Sinh viên).",
        "Bản phẳng [timeline_flat.sql](../sql/models/timeline_flat.sql) lọc 43 dòng trong 1,3 triệu dòng; bản lồng",
        "[bq_timeline_nested.sql](../sql/models/bq_timeline_nested.sql) lấy đúng một dòng rồi trải mảng ra.",
        "",
        "| | Bytes quét | Slot ms | Thời gian (s) |",
        "|---|---:|---:|---:|",
        bq_row("Phẳng", a["timeline"]["flat"]),
        bq_row("Lồng", a["timeline"]["nested"]),
        "",
        f"Kết quả: {ok(a['timeline']['same'])} ({a['timeline']['n_rows']} tuần).",
        "",
        "**Truy vấn 2: BR4 tuần 4 trên mọi đợt** (câu 14; trang Cảnh báo). Bản phẳng",
        "[br4_week4.sql](../sql/optimize/br4_week4.sql) phải **nối bảng với chính nó** để lấy click tuần 3 cạnh tuần 4.",
        "Bản lồng [bq_br4_week4_nested.sql](../sql/models/bq_br4_week4_nested.sql) không cần phép nối: tuần 3 nằm",
        "ngay trong mảng của cùng dòng.",
        "",
        "| | Bytes quét | Slot ms | Thời gian (s) |",
        "|---|---:|---:|---:|",
        bq_row("Phẳng (nối với chính nó)", a["week4"]["flat"]),
        bq_row("Lồng (không nối)", a["week4"]["nested"]),
        "",
    ]
    answer = a.get("answer")
    lines.append(
        f"Kết quả: {ok(a['week4']['same'])}"
        + (f" ({int(answer['n_enrolled']):,} lượt còn học, {int(answer['n_listed']):,} vào danh sách, "
           f"độ chính xác {answer['precision_pct']}%)." if answer else ".")
    )
    w4_flat, w4_nested = a["week4"]["flat"], a["week4"]["nested"]
    lines += [
        "",
        "**Đọc kết quả:**",
        "",
        "- BigQuery lưu mỗi trường con của mảng thành một cột riêng, nên bảng lồng vẫn được quét theo cột. Bytes quét",
        "  giảm vì cột khóa chỉ còn 32.593 giá trị thay vì 1,3 triệu.",
        f"- Nhưng ở truy vấn BR4, slot ms (công tính toán) tăng {ratio(w4_nested['slot_ms'], w4_flat['slot_ms'])}: bỏ được",
        "  phép nối bảng với chính nó, nhưng BigQuery phải dựng lại mảng của từng dòng để tìm tuần 3 và tuần 4. Công",
        "  việc không mất đi mà chuyển từ phép nối sang xử lý mảng.",
        "- Với cách tính tiền theo bytes quét (on-demand, như Sandbox) bản lồng rẻ hơn; với cách tính theo công tính",
        "  toán (mua slot) và về thời gian chờ thì bản phẳng tốt hơn.",
        "- Thêm nữa, SQL khó viết hơn (`UNNEST`, truy vấn con trên mảng) và sửa một tuần phải ghi lại cả dòng.",
        "",
        "## 3. Dạng tài liệu JSONB trên PostgreSQL",
        "",
        "**Mô hình:** mỗi lượt đăng ký một tài liệu JSON, giống cách một cơ sở dữ liệu tài liệu (MongoDB…) lưu hồ sơ",
        "học tập ([sql/models/pg_build_document.sql](../sql/models/pg_build_document.sql)):",
        "",
        "```json",
        '{"weeks": [{"week_no": -4, "clicks_week": 0, "clicks_cum": 0, "avg_score_cum": null, "is_enrolled": true, ...},',
        '           {"week_no": -3, ...}, ...]}',
        "```",
        "",
        f"Dựng bảng mất {b['build_seconds']:.1f} s.",
        "",
        "| | Số dòng | Kích thước (gồm TOAST và khóa chính) |",
        "|---|---:|---:|",
        f"| Bảng phẳng `public.fact_student_week` | {pg_flat_rows:,} | {mb(pg_flat_bytes)} |",
        f"| Tài liệu `doc.student_timeline` | {pg_doc_rows:,} | {mb(pg_doc_bytes)} |",
        "",
        f"Bản tài liệu nhỏ hơn {ratio(pg_flat_bytes, pg_doc_bytes)} dù JSONB lặp lại tên trường ở mỗi tuần: tài liệu lớn",
        "được PostgreSQL nén khi lưu ngoài dòng (TOAST), mỗi lượt đăng ký chỉ tốn một phần đầu dòng thay vì 37–43, và",
        "khóa chính chỉ có 32.593 mục thay vì 1,3 triệu. Bảng phẳng thì không nén.",
        "",
        "| Truy vấn | Phẳng (ms) | Tài liệu (ms) | Kết quả |",
        "|---|---:|---:|---|",
        f"| Dòng thời gian một sinh viên ([phẳng](../sql/models/timeline_flat.sql), [tài liệu](../sql/models/pg_timeline_document.sql)) | "
        f"{pg_ms(b['timeline']['flat'])} | {pg_ms(b['timeline']['doc'])} | {ok(b['timeline']['same'])} |",
        f"| Tuần 4 theo đợt, cắt ngang mọi sinh viên ([phẳng](../sql/models/pg_week4_flat.sql), [tài liệu](../sql/models/pg_week4_document.sql)) | "
        f"{pg_ms(b['week4']['flat'])} | {pg_ms(b['week4']['doc'])} | {ok(b['week4']['same'])} |",
        "",
        "**Đọc kết quả:**",
        "",
        "- Lấy hồ sơ một sinh viên: cả hai đều đi qua khóa chính. Bản phẳng đọc 43 dòng; bản tài liệu đọc đúng một",
        "  dòng rồi giải nén và tách mảng. Ở cỡ này cả hai đều dưới 1 ms, khác biệt không đáng kể.",
        f"- Câu hỏi cắt ngang tuần 4: bản tài liệu chậm hơn {ratio(b['week4']['doc']['seconds'], b['week4']['flat']['seconds'])}",
        "  vì phải mở toàn bộ tài liệu, giải nén và tách mọi phần tử chỉ để giữ lại tuần 4. Bảng phẳng chỉ cần lọc theo",
        "  cột `week_no`.",
        "",
        "## 4. Kết luận: chọn mô hình theo cách truy cập",
        "",
        "| Kiểu truy cập trong app | Mô hình hợp | Lý do |",
        "|---|---|---|",
        "| Tổng hợp nhiều chiều, cắt ngang mọi sinh viên (BR1–BR6) | Star, lưu theo cột | Lọc và gom theo cột nhanh, ít phép nối |",
        "| Hồ sơ trọn vẹn của một sinh viên (BR7, trang Sinh viên) | Tài liệu hoặc dạng lồng | Một lần đọc ra cả hồ sơ, không cần nối |",
        "| So tuần này với tuần trước của cùng sinh viên (BR4) | Star phẳng, phân vùng theo tuần | Dạng lồng bỏ được phép nối và quét ít bytes hơn, nhưng tốn công tính toán hơn nhiều (mục 2); phân vùng giảm bytes mà không tốn thêm ([optimization.md](optimization.md)) |",
        "| Cập nhật liên tục theo khóa (stream) | Khóa-giá trị | Mỗi sự kiện chỉ chạm một khóa |",
        "| Ghi và sửa dữ liệu gốc | Quan hệ 3NF | Mỗi dữ kiện một chỗ, không lệch khi sửa |",
        "",
        "Kho chính của project giữ star vì 6/8 BR là câu hỏi tổng hợp cắt ngang. Các mô hình khác dùng ở đúng chỗ",
        "hợp với chúng, không thay thế kho chính.",
    ]
    for section, plans in (("Kế hoạch truy vấn PostgreSQL: tuần 4", b["week4"]),):
        lines += ["", f"<details><summary>{section}</summary>", ""]
        for label, key in (("Phẳng", "flat"), ("Tài liệu", "doc")):
            lines += [f"**{label}**", "", "```", plans[key]["plan"], "```", ""]
        lines.append("</details>")
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    give_back_to_owner(DOC)
    print(f"Đã ghi {DOC.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=5, help="số lần chạy mỗi truy vấn (lấy trung vị)")
    args = parser.parse_args()

    a = experiment_nested(BigQuery(args.runs))
    b = experiment_document(args.runs)
    write_doc(a, b, args.runs)
    checks = [a["timeline"]["same"], a["week4"]["same"], b["timeline"]["same"], b["week4"]["same"]]
    if not all(checks):
        sys.exit("Có truy vấn cho kết quả khác bản phẳng, xem docs/data_models.md")


if __name__ == "__main__":
    main()
