-- Student-pair details and presentation statistics, without student identifiers.
SELECT
    code_module,
    code_presentation,
    clicks_before_deadline,
    score,
    n,
    rho
FROM tv3_br3_student_mart
WHERE code_module = @code_module
  AND code_presentation = @code_presentation
ORDER BY code_module, code_presentation, clicks_before_deadline, score;
