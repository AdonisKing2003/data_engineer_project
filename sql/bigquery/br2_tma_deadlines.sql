-- One marker per distinct week containing a TMA deadline for this offering.
SELECT DISTINCT
    CAST(FLOOR(deadline / 7.0) AS INT64) AS week_no
FROM dim_assessment
WHERE code_module = @code_module
  AND code_presentation = @code_presentation
  AND assessment_type = 'TMA'
  AND deadline IS NOT NULL
ORDER BY week_no;
