# Historical build-sequencing report

This folder is a 2026-08-24 snapshot created before full-schema Snowflake
catalogue exports were reconciled. Its central decision—build the pure engine
while treating unanswered business questions as stage gates—still applies.
Its source-access status, question wording, and integration next steps are no
longer current.

Use these files instead:

- `docs/descriptions/data_requirements.md` for current source status;
- `docs/descriptions/phase2_supply_planning_brief.md` section 10 for the
  audience/topic map of the already-sent Q1-Q13 set;
- `docs/plans/human_action_register.md` for owners, timing, and next actions;
- `scripts/snowflake_verification.sql` for current read-only verification.

The HTML, JSON, and SQL files in this folder are retained only as historical
decision evidence. Do not use them to decide whether access exists or which
Snowflake model is authoritative.
