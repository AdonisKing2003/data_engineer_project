-- Câu 13 (BR3): Spearman giữa click trước hạn và điểm TMA đầu tiên của AAA 2013J là bao nhiêu?
-- Đáp án chuẩn: rho ≈ 0,37 trên n = 358 lượt nộp hợp lệ.
WITH first_weighted_tma AS (
    SELECT
        id_assessment,
        code_module,
        code_presentation,
        deadline
    FROM dim_assessment
    WHERE assessment_type = 'TMA'
      AND weight > 0
      AND is_first_weighted_tma
      AND code_module = 'AAA'
      AND code_presentation = '2013J'
), eligible_submissions AS (
    SELECT
        submission.id_student,
        assessment.code_module,
        assessment.code_presentation,
        assessment.deadline,
        submission.score
    FROM first_weighted_tma AS assessment
    INNER JOIN fact_submission AS submission
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
    INNER JOIN fact_vle_daily AS click
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
)
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS n,
    CORR(clicks_average_rank, score_average_rank) AS rho
FROM ranked_pairs
GROUP BY code_module, code_presentation;
