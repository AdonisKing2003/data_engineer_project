-- BR3: Spearman correlation between clicks before the first weighted TMA
-- deadline and the student's score on that TMA, per module presentation.
-- Tied values receive average ranks; zero-click students remain in the sample.
WITH first_weighted_tma AS (
    SELECT
        id_assessment,
        code_module,
        code_presentation,
        deadline
    FROM read_parquet('data/warehouse/dim_assessment/*.parquet')
    WHERE assessment_type = 'TMA'
      AND weight > 0
      AND is_first_weighted_tma
), eligible_submissions AS (
    SELECT
        submission.id_student,
        assessment.code_module,
        assessment.code_presentation,
        assessment.deadline,
        submission.score
    FROM first_weighted_tma AS assessment
    INNER JOIN read_parquet('data/warehouse/fact_submission/*.parquet') AS submission
        ON submission.id_assessment = assessment.id_assessment
    WHERE submission.score IS NOT NULL
      AND NOT submission.is_banked
), clicks_before_deadline AS (
    SELECT
        submission.id_student,
        submission.code_module,
        submission.code_presentation,
        SUM(click.sum_click) AS clicks_before_deadline
    FROM eligible_submissions AS submission
    INNER JOIN read_parquet('data/warehouse/fact_vle_daily/*.parquet') AS click
        ON click.id_student = submission.id_student
       AND click.code_module = submission.code_module
       AND click.code_presentation = submission.code_presentation
       AND click.date < submission.deadline
    GROUP BY
        submission.id_student,
        submission.code_module,
        submission.code_presentation
), student_pairs AS (
    SELECT
        submission.id_student,
        submission.code_module,
        submission.code_presentation,
        COALESCE(clicks.clicks_before_deadline, 0) AS clicks_before_deadline,
        submission.score
    FROM eligible_submissions AS submission
    LEFT JOIN clicks_before_deadline AS clicks
        ON clicks.id_student = submission.id_student
       AND clicks.code_module = submission.code_module
       AND clicks.code_presentation = submission.code_presentation
), ranked_pairs AS (
    SELECT
        id_student,
        code_module,
        code_presentation,
        clicks_before_deadline,
        score,
        RANK() OVER (
            PARTITION BY code_module, code_presentation
            ORDER BY clicks_before_deadline
        )
        + (
            COUNT(*) OVER (
                PARTITION BY code_module, code_presentation, clicks_before_deadline
            ) - 1
        ) / 2.0 AS clicks_average_rank,
        RANK() OVER (
            PARTITION BY code_module, code_presentation
            ORDER BY score
        )
        + (
            COUNT(*) OVER (
                PARTITION BY code_module, code_presentation, score
            ) - 1
        ) / 2.0 AS score_average_rank
    FROM student_pairs
), correlations AS (
    SELECT
        id_student,
        code_module,
        code_presentation,
        clicks_before_deadline,
        score,
        COUNT(*) OVER (
            PARTITION BY code_module, code_presentation
        ) AS n,
        CORR(clicks_average_rank, score_average_rank) OVER (
            PARTITION BY code_module, code_presentation
        ) AS rho
    FROM ranked_pairs
)
SELECT
    id_student,
    code_module,
    code_presentation,
    clicks_before_deadline,
    score,
    n,
    rho
FROM correlations
ORDER BY code_module, code_presentation, clicks_before_deadline, score;
