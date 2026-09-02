# Order-requirement status alignment

**Goal:** make Overview and Location answer the same operational question:
does accepted supply cover the item-specific protection window before an
unplaced proposal is counted? Keep the separate post-proposal outcome visible.

## Scope

- Derive one explicit order-requirement status in Python from persisted v3
  coverage evidence.
- Return order-required and residual post-proposal risk counts separately.
- Make Overview, Location status, sorting, filtering, and counts consume those
  backend fields without date comparison in React.
- Preserve compatibility with already persisted v3 runs; no Supabase migration
  or recomputation should be required.

## Checklist

- [x] Add and test the pure Python order-requirement classification.
- [x] Decorate run and Overview read models with the explicit status and counts.
- [x] Align React types, Overview semantics, and Location presentation.
- [x] Update backend/frontend regression tests.
- [x] Reconcile canonical contracts, UI handover, backlog, and project memory.
- [x] Run focused checks and the broader applicable suites.

## Decision

`order_requirement_status` answers the pre-proposal action question using
usable stock plus accepted open POs. The existing `actionable_risk_status` is
retained as the post-proposal outcome for compatibility; its name is historical
and its meaning must be labelled explicitly. Because the v3 rows already
persist the first uncovered date for accepted supply and the protection-window
evidence, the API can derive the new field without a database migration or a
fresh planning run.

## Progress

- 2026-09-02 — Completed end to end. Existing coverage-v3 rows are decorated at
  read time, so no migration or recomputation is needed. The full Python suite
  passes with 91 tests; focused Ruff and strict mypy pass on the changed Python
  boundary. The full web check passes with 143 tests plus lint, typecheck, and
  production build. Repository-wide Ruff still reports 35 unrelated legacy or
  concurrently edited adapter findings; none are in this change's files. A
  post-change authenticated browser inspection was not available in this task;
  the maintainer should restart/reload the API and refresh the existing UI.
