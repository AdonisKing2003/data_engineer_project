-- BR2 school-wide view: clicks of every enrollment (withdrawn students included)
-- by week and activity type, from fact_vle_daily. Sums to 39,605,099 clicks.
-- Unlike br2_dashboard, there is no "still enrolled at week end" filter, so
-- these totals answer sample questions 9 and 10.
SELECT
    vle.week_no,
    site.activity_type,
    SUM(vle.sum_click) AS total_clicks
FROM read_parquet('data/warehouse/fact_vle_daily/*.parquet') AS vle
INNER JOIN read_parquet('data/warehouse/dim_vle_site/*.parquet') AS site
    ON site.id_site = vle.id_site
   AND site.code_module = vle.code_module
   AND site.code_presentation = vle.code_presentation
GROUP BY vle.week_no, site.activity_type
ORDER BY vle.week_no, site.activity_type;
