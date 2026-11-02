-- Danh sách các đợt học (BigQuery)
SELECT DISTINCT code_module, code_presentation,
       code_module || ' ' || code_presentation AS presentation_label
FROM dim_presentation
ORDER BY code_module, code_presentation;

