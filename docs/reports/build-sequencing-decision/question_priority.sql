-- HISTORICAL SNAPSHOT. Superseded by the Q1-Q13 audience/topic map in
-- docs/descriptions/phase2_supply_planning_brief.md section 10 and the
-- action status in docs/plans/human_action_register.md.
-- Retained only as evidence for the original report.
SELECT *
FROM (
    VALUES
        (1, 'Tier A — ask now', 5, 'Q1, Q4, Q5, Q6, Q9', 'M1 interpretation and M2 netting'),
        (2, 'Tier B — before M2/M4 exit', 5, 'Q2, Q3, Q7, Q10, Q11', 'Improved-policy sign-off and shadow design'),
        (3, 'Tier C — before M3/M5 completion', 3, 'Q8, Q12, Q13', 'Calibration, live data, and final workflow')
) AS priority_counts(sort_order, priority, question_count, questions, first_gate)
ORDER BY sort_order;
