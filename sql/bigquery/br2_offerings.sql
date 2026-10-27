-- Offerings available in the refreshed BigQuery BR2 mart.
SELECT DISTINCT
    code_module,
    code_presentation
FROM tv3_br2_weekly_mart
ORDER BY code_module, code_presentation;
