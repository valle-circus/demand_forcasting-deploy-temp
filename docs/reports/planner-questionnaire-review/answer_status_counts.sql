WITH question_status(question_number, assessment) AS (
    VALUES
        (1, 'Partial'),
        (2, 'Partial'),
        (3, 'Partial'),
        (4, 'Partial'),
        (5, 'Confirmed baseline'),
        (6, 'Partial'),
        (7, 'Partial'),
        (8, 'Partial'),
        (9, 'Confirmed baseline'),
        (10, 'Confirmed baseline'),
        (11, 'Partial'),
        (12, 'Inconclusive'),
        (13, 'Partial')
)
SELECT
    assessment,
    COUNT(*) AS question_count,
    GROUP_CONCAT('Q' || question_number, ', ') AS question_ids,
    ROUND(CAST(COUNT(*) AS REAL) / 13.0, 6) AS share_of_13
FROM question_status
GROUP BY assessment
ORDER BY CASE assessment
    WHEN 'Confirmed baseline' THEN 1
    WHEN 'Partial' THEN 2
    ELSE 3
END;
