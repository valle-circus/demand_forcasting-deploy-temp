-- HISTORICAL SNAPSHOT. Superseded by the Q1-Q13 audience/topic map in
-- docs/descriptions/phase2_supply_planning_brief.md section 10 and the
-- action status in docs/plans/human_action_register.md.
-- Retained only as evidence for the original report.
SELECT *
FROM (
    VALUES
        (1, 'Q1', 'In-transit', 'A', 'Dated PO schema, empty/manual fixtures, pipeline netting and exceptions', 'Operational netting and explanation of blank orders', 'M2/M4'),
        (2, 'Q2', 'Lead times', 'B', 'Item/supplier overrides, calendars, defaults and scenarios', 'Trusted order and receipt dates', 'M2/M4'),
        (3, 'Q3', 'Shelf life', 'B', 'Policy fields, approximate caps, lot-ready interface and conflict tests', 'Trusted expiry and max-cover enforcement', 'M2/M4'),
        (4, 'Q4', 'S/M/W/Fr columns', 'A', 'Reproduce calculated Order and preserve manual columns as observations', 'Replication of actual placed quantity and weekday split', 'M1/M4'),
        (5, 'Q5', 'Demand/Silo Load', 'A', 'Treat as daily demand in legacy mode and define daily input contract', 'Final Phase 1 semantics and silo-capacity behavior', 'M1/M6'),
        (6, 'Q6', 'Stock count', 'A', 'Reproduce 2.5-day bridge and implement timestamped inventory input', 'Correct opening projection for real runs', 'M2/M4'),
        (7, 'Q7', 'Menu changes', 'B', 'Forward menu schema plus launch and discontinuation scenarios', 'Operational transition dates and menu-horizon validation', 'M2/M4'),
        (8, 'Q8', '20% buffer', 'C', 'Keep 1.20 in legacy and separate configurable yield and safety policies', 'Calibrated replacement policy', 'M4'),
        (9, 'Q9', 'Master data', 'A', 'Stable IDs, aliases, quarantine rules and KW34 quality cases', 'Complete coverage and safe operational joins', 'M1/M3'),
        (10, 'Q10', 'Fresh products', 'B', 'Configurable delivery-slot coverage with fixture calendars', 'Correct live fresh consumption windows', 'M2/M4'),
        (11, 'Q11', 'Weekly process', 'B', 'Run and approval objects with mandatory human approval', 'Final cadence, urgent-order path, ownership and UI workflow', 'M4/M5'),
        (12, 'Q12', 'Other data', 'C', 'File adapters, SQL ports, provenance and unavailable metrics', 'Real connectors, calibration, backtests and shadow runs', 'M3/M4'),
        (13, 'Q13', 'Planner experience', 'C', 'Explanations, exceptions, overrides and auditability as baseline', 'Final UX priority and automation boundary', 'M5')
) AS question_gates(sort_order, question, topic, priority, build_now, must_wait, gate)
ORDER BY sort_order;
