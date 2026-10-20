-- One presentation-level row for the BR3 forest plot, without student identifiers.
SELECT DISTINCT
    code_module,
    code_presentation,
    n,
    rho
FROM tv3_br3_student_mart
ORDER BY code_module, code_presentation;
