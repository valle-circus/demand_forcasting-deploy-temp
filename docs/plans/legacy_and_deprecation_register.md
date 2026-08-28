# Legacy, deprecation and archive candidate register

**Created:** 2026-08-27

**Last code scan:** 2026-08-27 at repository revision `d7e9212`

**Status:** inventory only; no file has been moved or deleted

## Purpose

This register prevents historical compatibility code, active V1 code, unused
scaffolding and discovery evidence from being mixed together. It is the
authoritative cleanup inventory until the candidates are either moved, removed,
renamed or explicitly retained.

A single undifferentiated `legacy/` folder would become another source of
confusion. The preferred future split is:

- `compatibility/kw34/` for intentionally executable old-workbook behavior;
- removal or implementation for unused type definitions;
- neutral renaming for active code whose old names are misleading; and
- `docs/archive/` for completed discovery evidence that is no longer an active
  engineering reference.

## Current recurring V1 input contract

`python -m supply_planning v1-run` is the active end-to-end local workflow. Its
four inputs are:

| CLI argument | What it is | Maintained in our schema? |
|---|---|---:|
| `--master-workbook` | Filled `Phase2_Master_Data_Template_v1.xlsx` with `Items`, `Locations` and `Delivery_Rules` | Yes |
| `--planning-workbook` | Filled `Phase2_Planning_Input_Template_v1.xlsx` with `Demand_Plan`, `Menu_Calendar` and `BOM_Lines` | Yes |
| `--stock-workbook` | Raw current Apicbase `Stock Report` XLSX export | No; it is normalized at upload |
| `--po-pdf-dir` | Raw cumulative Transgourmet order PDFs, including pod orders | No; they are normalized at upload |

The name `stock_workbook` does **not** refer to a third project-owned template.
It is the raw Apicbase export. A future UI should label it “Apicbase stock
export”; a later code-only rename to `apicbase_stock_export` would also make the
contract clearer.

There is no active adapter for the original `Supply_Planning_Rewe.xlsx`,
`KW33/KW34`, `CW36_*` or pod-metadata workbook layouts. Those files supplied
evidence used to design and prefill the project-owned templates. They are not
recurring runtime inputs.

## Classification used in this register

| Classification | Meaning | Future action |
|---|---|---|
| Active runtime | Used by `v1-run` or its calculation path | Keep |
| Active support | Developer, fixture or interim import path still useful to V1 | Keep; possibly rename or consolidate later |
| Compatibility legacy | Intentionally reproduces the old KW34 behavior | Move together only after the compatibility gate |
| Remove or revive | Has no repository consumer, but may represent an unfinished future contract | Decide explicitly; do not hide in `legacy/` |
| Archive evidence | Historical analysis or decision evidence, not runtime code | Move to a documentation archive after its active gate closes |
| Rename for clarity | Active code whose historical name is misleading | Rename atomically without changing behavior |

## A. True compatibility-legacy candidates

These files and fragments form one isolated KW34 compatibility feature. They
implement the old flat `1.20` factor, six-day coverage and `2.5` bridge. That
arithmetic is not invoked by `v1-run`. Some legacy modules are nevertheless
imported while Python initializes the current package because of the stale
facades in section B; this is an import side effect, not calculation behavior.

| Path or fragment | Current purpose | Candidate action |
|---|---|---|
| `src/supply_planning/engine/legacy_kw34.py` | Old-workbook arithmetic | Move to `src/supply_planning/compatibility/kw34/engine.py` |
| `src/supply_planning/application/run_legacy.py` | Compatibility orchestration and audit records | Move beside the compatibility engine |
| `src/supply_planning/adapters/legacy_csv.py` | Compatibility-only CSV input and JSON output | Move beside the compatibility engine |
| `tests/test_legacy_kw34.py` | Unit/integration coverage for the old arithmetic | Move to `tests/compatibility/kw34/` with the feature |
| `tests/test_cli.py` | Currently tests only `legacy-run` | Move/rename with the compatibility CLI tests; add separate active CLI tests elsewhere |
| `tests/fixtures/synthetic_legacy/` | Synthetic KW34 compatibility rows | Move with the compatibility tests |
| `src/supply_planning/cli.py` — `legacy-run` parser and branch | Public entry point for the compatibility feature | Keep only if KW34 parity remains a supported tool; otherwise remove with the feature |
| `src/supply_planning/domain/issues.py` — `UNEXPLAINED_BLANK_ORDER`, `OBSERVED_ORDER_DIFFERS` | Codes used only by `run_legacy.py` | Move to compatibility-local issues or remove with the feature |
| `README.md` — verified workbook baseline and `legacy-run` example | Historical explanation and command | Reduce to a short link if the detailed material moves to `docs/legacy/kw34_compatibility.md` |

### Gate before moving or deleting this group

1. Receive maintainer feedback on the new templates and active policy.
2. Rerun the template-driven workflow with the corrected real inputs.
3. Decide whether exact KW33/KW34 comparison remains an ongoing regression
   requirement or has served its migration purpose.
4. If it remains supported, move the complete feature atomically under
   `compatibility/kw34/` and preserve its tests. If not, delete the complete
   feature atomically. Do not leave half of it imported from active packages.

## B. Stale package facades — cleanup candidates, not legacy folders

No repository module imports names from the public facades below. Their current
contents are still executed during normal Python package initialization, are
misleading, and cause legacy modules to be imported when the corresponding
package is imported.

| Path | Finding | Recommended action |
|---|---|---|
| `src/supply_planning/__init__.py` | The root package exports only `run_legacy_kw34`, even though `v1-run` is the current workflow | Replace with a minimal version-only facade or an explicitly supported active API |
| `src/supply_planning/application/__init__.py` | Imports legacy symbols, then overwrites `__all__` with improved-run symbols | Define one deliberate active public API; remove import side effects |
| `src/supply_planning/adapters/__init__.py` | Imports legacy CSV symbols, then overwrites `__all__` with canonical symbols | Export only the intended active adapter API or keep the initializer minimal |
| `src/supply_planning/engine/__init__.py` | Imports legacy and active engines, then overwrites `__all__` a second time | Export a coherent active engine surface or keep the initializer minimal |
| `src/supply_planning/domain/__init__.py` | Re-exports unused old/future types and omits active policy types | Rebuild the facade from the active contract or remove the facade |

This cleanup can happen before the KW34 move because it changes package
presentation, not business calculations. It needs import/CLI tests because
external consumers, if any, are not visible from this repository scan.

## C. Unused or superseded type-definition candidates

Repository-wide exact-name searches found no consumer outside the definition
and `domain/__init__.py` re-export for these types.

| Symbol in `src/supply_planning/domain/models.py` | Why it is questionable | Decision needed |
|---|---|---|
| `Supplier` | Supplier identity is currently carried by maintained item policy fields; no separate supplier entity is loaded | Remove, or define the future master-table use before keeping it |
| `SupplierItem` | Its lead/MOQ/case fields overlap the active `ItemPlanningPolicy` contract | Remove unless persistence deliberately normalizes it as a separate entity |
| `DeliveryScheduleRule` | Superseded in the active engine by location-aware `DeliveryCoverageRule` | Remove after confirming no external package import |
| `PlanningRun` | Unused persistence-shaped record; the current result is `ImprovedRunResult` plus audit/table outputs | Revive as the agreed Snowflake run-row DTO in Milestone 3, or remove |
| `PlanningRunInput` | Unused persistence-shaped source record; current source status/audit uses `InputSourceStatus` and manifest rows | Revive with the agreed persistence schema, or remove |
| `PlanningExceptionRecord` | Unused persistence-shaped record; current runtime uses `PlanningIssue` and generated exception rows | Revive with the agreed persistence schema, or remove |

These symbols should not be moved to `legacy/`: doing so would falsely imply
that they reproduce an old supported behavior. The first three look superseded;
the last three may be useful only when the Snowflake persistence contract is
agreed.

## D. Active code with historical or ambiguous names

These are **not legacy candidates**. They are used by the current template run
or its deterministic developer contract.

| Current path or name | Why it remains active | Later clarity improvement |
|---|---|---|
| `src/supply_planning/application/run_improved.py` | `run_template_v1.py` calls `run_improved_plan` as the active calculation orchestrator | Rename to neutral `run_plan.py` after the UI/API boundary is fixed |
| `src/supply_planning/adapters/improved_json.py` | Writes the active deterministic audit used by V1 outputs | Rename with `run_improved.py` |
| CLI `improved-run` and profile `improved_file/v1` | Direct canonical-file developer/fixture path; useful for engine tests and recovery | Rename to `canonical-run` or similar, without removing the path |
| `tests/test_improved_run.py` and `tests/fixtures/synthetic_improved/` | Active deterministic canonical-engine coverage | Rename with the active profile, not move to legacy |
| `src/supply_planning/adapters/canonical_csv.py` | `v1-run` writes and reloads the canonical bundle through this adapter | Keep; it is the stable table-shaped boundary |
| CLI `--stock-workbook` / function `stock_workbook` | Active raw Apicbase upload, but easily mistaken for a maintained template | Later rename to `--apicbase-stock-export` with a compatibility alias if needed |

## E. Active interim support — retain for now

| Path | Why it is still needed | Retirement gate |
|---|---|---|
| `src/supply_planning/adapters/transgourmet_pdf.py` | Active PDF parser/scanner and standalone private extraction support | Accepted Transgourmet API or normalized operational table |
| `src/supply_planning/adapters/transgourmet_v1.py` | Active reviewed mapping and order-unit normalization for `v1-run` | Replaced only by an equivalent accepted source adapter |
| `scripts/extract_transgourmet_pos.ps1` | Repeatable manual PDF-history bridge and recovery tool | Accepted API/table plus an explicit recovery decision |
| CLI `transgourmet-import` | Exposes the standalone private extraction path | Same gate as the script |
| `src/supply_planning/adapters/apicbase_stock_xlsx.py` | Active raw stock upload normalizer | Accepted Apicbase API or normalized operational stock table |

## F. Historical evidence and future archive candidates

These are not source-code legacy and should not be mixed into a Python
`legacy/` package.

| Path | Current value | Candidate destination and gate |
|---|---|---|
| `scripts/snowflake_discovery.sql` | Explicitly marked superseded first-pass discovery | `docs/archive/snowflake/` after Milestone 3 source decisions |
| `scripts/snowflake_verification.sql` | Completed V1-V12 verification queries | Archive after persistence/source integration no longer needs them |
| `scripts/explore_snowflake.py` | One-off KW34/source exploration helper | Archive with Snowflake discovery evidence |
| `docs/scratchpads/snowflake_verification_evidence.md` | Durable evidence behind the completed source review | Archive only after an authoritative source contract replaces it |
| `docs/reports/build-sequencing-decision/` | Historical build-order decision artifact | `docs/archive/reports/` once no longer used for onboarding |
| `docs/reports/planner-questionnaire-review/` | Q1-Q13 reconciliation and evidence | Keep through maintainer validation, then archive |
| `docs/plans/v1_template_first_delivery_plan.md` | Completed technical Milestone 1 plan with an open operational gate | Later move to `docs/plans/completed/`, not `legacy/`, after the gate closes |

The main `phase2_supply_planning_brief.md` remains authoritative. It contains
substantial historical KW33/KW34 evidence, but the whole file must not be moved.
After the compatibility decision, the detailed old-workbook sections may be
extracted into `docs/legacy/kw34_compatibility.md` and replaced by a concise
summary/link in the active brief.

`MEMORY.md` also remains in place. Its superseded entries are intentional
decision history, not stray files.

## G. Active runtime files that must not be moved

The current end-to-end path is centered on:

- `src/supply_planning/application/run_template_v1.py`;
- `src/supply_planning/adapters/template_xlsx.py`;
- `src/supply_planning/adapters/apicbase_stock_xlsx.py`;
- `src/supply_planning/adapters/transgourmet_v1.py` and the parser portions of
  `transgourmet_pdf.py`;
- `src/supply_planning/adapters/canonical_csv.py` and `v1_outputs.py`;
- `src/supply_planning/application/run_improved.py`;
- `src/supply_planning/engine/explode.py`, `netting.py` and `recommend.py`;
- `src/supply_planning/validation/gates.py`; and
- their active tests: `test_canonical_csv.py`, `test_domain_models.py`,
  `test_explode.py`, `test_improved_run.py`, `test_netting.py`,
  `test_run_mode_gates.py`, `test_transgourmet_pdf.py`,
  `test_v1_recommendation_and_po.py` and `test_v1_xlsx_adapters.py`.

## Recommended cleanup order

- [x] Create this classified register without moving behavior.
- [ ] Add active `v1-run` CLI smoke/error tests, separate from the
      compatibility-only `tests/test_cli.py`.
- [ ] Clean the five stale package facades and verify direct imports plus the
      full test suite.
- [ ] Decide the six unused domain records: remove the superseded three and
      defer/revive the persistence three only against an agreed table schema.
- [ ] Rename the active `improved_*` profile to neutral planning terminology in
      one no-behavior-change refactor.
- [ ] Pass the maintainer/real-input gate and decide whether KW34 compatibility
      is retained.
- [ ] Move the complete retained compatibility feature atomically, or delete
      it atomically.
- [ ] Archive completed discovery/report artifacts only after their named
      source or maintainer gate closes.

## Verification performed for this inventory

- Traced the `v1-run` CLI arguments through `run_template_v1`, both fixed
  template readers, raw stock/PO normalization, canonical reload and the active
  planning engine.
- Searched all Python source, tests and scripts for KW/CW/legacy references and
  exact uses of the candidate domain symbols.
- Reviewed every package initializer, test/fixture group, discovery script,
  report directory and active plan/scratchpad.
- Ran the repository check after this documentation-only change: compileall and
  all 44 tests passed; `git diff --check` reported no whitespace errors.
