"""Test cho 1.8: fact_student_week khớp hợp đồng và ra đúng đáp án BR4, BR7 trong tài liệu đặc tả.
Gồm cả test chống rò rỉ nhãn (việc 2.7 của TV2, gom vào đây theo việc 1.10).

Truy vấn BR4 ở đây chỉ là bản tham chiếu để kiểm bảng; SQL chính thức của BR4 vẫn do TV2 viết.
Chạy:  pytest -q tests/test_student_week.py
"""
from pathlib import Path

import duckdb
import pytest

WH = Path(__file__).resolve().parents[1] / "data" / "warehouse"


@pytest.fixture(scope="module")
def db():
    for t in ["fact_student_week", "fact_enrollment"]:
        if not (WH / t).exists():
            pytest.skip(f"chưa chạy ETL ({t})")
    con = duckdb.connect()
    for t in ["fact_student_week", "fact_enrollment"]:
        con.sql(f"create view {t} as select * from read_parquet('{WH / t}/*.parquet')")
    return con


def one(db, sql):
    return db.sql(sql).fetchone()


# BR4 theo Phụ lục kỹ thuật. Chỉ đọc fact_student_week: không có final_result nào lọt vào danh sách.
BR4_LIST = """
with cohort as (
    select w.*, p.clicks_week as clicks_prev_week
    from fact_student_week w
    join fact_student_week p
      on p.id_student = w.id_student and p.code_module = w.code_module
     and p.code_presentation = w.code_presentation and p.week_no = w.week_no - 1
    where w.week_no = {week} and w.is_enrolled {where}
),
p25 as (
    select code_module, code_presentation, quantile_cont(clicks_cum, 0.25) as p25
    from cohort group by all
)
select c.id_student, c.code_module, c.code_presentation,
       (c.clicks_cum < p.p25)::int
     + (c.clicks_week = 0 and c.clicks_prev_week = 0)::int
     + (c.n_tma_missed_cum > 0)::int
     + coalesce(c.avg_score_cum < 40, false)::int as risk
from cohort c join p25 p using (code_module, code_presentation)
"""


def br4(db, week, where=""):
    """(số SV được xét, số SV vào danh sách, độ chính xác %, độ bao phủ %, tỷ lệ nền %)"""
    return one(db, f"""
        with scored as ({BR4_LIST.format(week=week, where=where)}),
        labeled as (
            select s.risk >= 2 as listed, e.final_result in ('Fail', 'Withdrawn') as bad
            from scored s join fact_enrollment e using (id_student, code_module, code_presentation)
        )
        select count(*), count(*) filter (listed),
               round(100 * count(*) filter (listed and bad) / count(*) filter (listed), 1),
               round(100 * count(*) filter (listed and bad) / count(*) filter (bad), 1),
               round(100 * count(*) filter (bad) / count(*), 1)
        from labeled""")


FLAG_COUNTS = [("is_pre_start", 130372), ("is_week_inactive", 715918), ("is_enrolled", 1043478)]


@pytest.mark.parametrize("flag,expected", FLAG_COUNTS)
def test_flag_count(db, flag, expected):
    assert one(db, f"select count(*) from fact_student_week where {flag}")[0] == expected


def test_grain(db):
    assert one(db, "select count(*) from fact_student_week")[0] == 1342949
    assert one(db, """select count(*) - count(distinct (id_student, code_module, code_presentation, week_no))
                      from fact_student_week""")[0] == 0
    # mỗi lượt đăng ký có đủ tuần −4 .. n_weeks − 1, không thiếu tuần nào
    assert one(db, """select count(*) from (
                        select id_student, code_module, code_presentation
                        from fact_student_week group by all
                        having min(week_no) <> -4 or count(*) <> max(week_no) + 5)""")[0] == 0


def test_cumulative_columns_never_decrease(db):
    assert one(db, """select count(*) from (
                        select clicks_cum - lag(clicks_cum) over w as d1,
                               n_submitted_cum - lag(n_submitted_cum) over w as d2
                        from fact_student_week
                        window w as (partition by id_student, code_module, code_presentation order by week_no))
                      where d1 < 0 or d2 < 0""")[0] == 0


def test_click_total_matches_vle(db):
    """Tổng click trong khung tuần = tổng click toàn bộ (không có click nào nằm ngoài khung)."""
    assert one(db, "select sum(clicks_week) from fact_student_week")[0] == 39605099


def test_no_label_column(db):
    cols = {r[0] for r in db.sql("describe fact_student_week").fetchall()}
    assert "final_result" not in cols


def test_br7_aaa_2014j_week10(db):
    """Đáp án câu 19: 336 SV; tổng click đến nay phân vị 25/50/75 = 269 / 593 / 1.083."""
    n, q25, q50, q75 = one(db, """
        select count(*), quantile_cont(clicks_cum, 0.25), quantile_cont(clicks_cum, 0.5),
               quantile_cont(clicks_cum, 0.75)
        from fact_student_week
        where code_module = 'AAA' and code_presentation = '2014J' and week_no = 10 and is_enrolled""")
    assert n == 336
    assert (round(q25), round(q50), round(q75)) == (269, 593, 1083)


def test_br4_ddd_2014j_week4(db):
    """DDD 2014J tuần 4: 1.459 SV còn học, 161 vào danh sách; độ chính xác 90,1% vs nền 45,7%."""
    n, listed, precision, _, base = br4(
        db, 4, "and w.code_module = 'DDD' and w.code_presentation = '2014J'")
    assert (n, listed, precision, base) == (1459, 161, 90.1, 45.7)


@pytest.mark.parametrize("week,expected", [
    (4, (3958, 80.6, 26.9, 43.5)),   # đáp án câu 14
    (8, (4598, 84.6, 35.6, 41.5)),
])
def test_br4_all_presentations(db, week, expected):
    _, listed, precision, recall, base = br4(db, week)
    assert (listed, precision, recall, base) == expected


def test_br4_list_ignores_final_result(db):
    """Chống rò rỉ: đổi final_result của mọi SV thì danh sách tuần 4 không đổi."""
    before = db.sql(f"select * from ({BR4_LIST.format(week=4, where='')}) order by all").fetchall()
    db.sql(f"""create or replace view fact_enrollment as
               select * replace (case when final_result = 'Pass' then 'Fail' else 'Pass' end as final_result)
               from read_parquet('{WH / 'fact_enrollment'}/*.parquet')""")
    try:
        after = db.sql(f"select * from ({BR4_LIST.format(week=4, where='')}) order by all").fetchall()
    finally:
        db.sql(f"create or replace view fact_enrollment as "
               f"select * from read_parquet('{WH / 'fact_enrollment'}/*.parquet')")
    assert before == after
