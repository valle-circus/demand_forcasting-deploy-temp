# Agent Scratchpad — Phase 2 Supply Planning

> Living working memory for the build. Keep this short and update it after each meaningful step.

## Goal
- Deliver a trustworthy Phase 2 planning system that first reproduces KW34, then improves ordering logic, connects real data, passes shadow validation, and finally supports non-technical users through a React/Tailwind UI.

## Current plan
- [x] Inspect the linked workbook and independently reconcile KW34 values.
- [x] Correct the engineering brief and target mathematics.
- [x] Define the script-first, data-later, UI-last architecture.
- [x] Create the cross-session master backlog.
- [x] Implement the first Milestone 0/Milestone 1 foundation: contracts, pure BOM explosion, isolated legacy calculation, synthetic tests, and audit CLI.
- [x] Implement the first unblocked Milestone 2 tranche: canonical CSV bundle, daily menu/BOM validation, dated inventory/open-PO ledger and netting, strict source gates, deterministic improved audit output, and scenario tests.
- [ ] Add the approved real KW34 golden fixture and remaining legacy workbook paths after the relevant human gates clear.
- [ ] Implement the next M2 policy tranche: item-specific protection periods, yield/safety inputs, constraints, supplier/fresh scheduling, and order-proposal derivations.

## Key decisions (and why)
- 2026-08-22: Keep separate `legacy_kw34` and `improved` policy profiles. Exact reproduction must not contaminate corrected policy.
- 2026-08-22: Build one Python application service behind the CLI; later FastAPI/UI callers reuse it.
- 2026-08-22: Use daily forecast and menu contracts from day one, even while KW34 is hardcoded flat by day.
- 2026-08-22: Missing waste, OOS, forecast-error, receipt, and lot data do not block engine development. Use explicit placeholders/defaults with provenance and warnings.
- 2026-08-22: Unknown current stock, pack/SKU, lead time, or open-PO pipeline may proceed in fixture/scenario mode but blocks operational approval.
- 2026-08-22: CSV/YAML plus the CLI are a technical bootstrap path for fixtures, tests, local runs, initial import, fallback, and export. They are not the intended configuration interface for non-technical planners.
- 2026-08-22: When the operational UI begins, approved Supabase tables become the single source of truth for editable master data, policy versions, runs, proposals, and approvals. Planners change them through React/FastAPI, not direct table or file edits.
- 2026-08-22: Build the UI only after file logic, real-data adapters, and shadow validation; use React/Tailwind with a Python API.
- 2026-08-24: Unanswered business questions are promotion gates, not a global start blocker. Build contracts, engine paths, CLI, and scenario tests now with explicit assumptions; do not promote outputs to shadow or operational use until the inputs required by that stage are resolved.
- 2026-08-24: Use Python 3.12 standard-library dataclasses, `Decimal`, CSV/JSON, `argparse`, and `unittest` for the first foundation. Defer runtime dependencies to the adapter/API milestone that owns them.
- 2026-08-24: Canonical contracts are engine boundaries, not assumed SQL schemas. Source adapters must map real Snowflake/ERP/API columns after discovery; the canonical daily field is `service_date`.
- 2026-08-24: Canonical output records now cover runs, input snapshots, derivation lines, proposals, exceptions, and approvals. Calculation remains separate from human approval, and the current CLI has no approval or dispatch path.
- 2026-08-24: Keep `last_order_date_offset_days` and `pipeline_cancellable` in item master data as specified for menu transitions; validate timestamps as timezone-aware at adapter/domain boundaries.
- 2026-08-24: Separate source states strictly: `MEASURED`, `CATALOGUED/CANDIDATE`, planner/purchasing `POLICY`, and `OPEN`. Table or column existence does not authorize an operational adapter.
- 2026-08-24: Continue the pure engine and file-driven work. Existing Snowflake forecast/order models are a scope gate for integration, not a global stop-work condition.
- 2026-08-25: Keep audiences separate. The already-sent Q1-Q13 set belongs to the Excel owner and needs no correction. Joel answered the technical model and PO-ingestion questions; Ops now owns current-process/source discovery, while Joel/data platform owns later ingestion and model publication. Investigate other technical questions through SQL before requesting targeted follow-ups.
- 2026-08-25: Joel confirmed that `FACT_CG_DISH_DEMAND_FORECASTS`, `FACT_CG_INGREDIENT_DEMAND_FORECASTS`, `FACT_CG_PURCHASE_ORDERS`, and `BASE_INVENTORY` are abandoned previous-data-team models. They may be replaced in `data-transformation`, but are not authoritative inputs or approved logic. Inspect that repository after access and decide its boundary with this repository's pure engine before changing models.
- 2026-08-25: Joel will provision a stable RSA-authenticated Snowflake service account and share credentials through 1Password. Never record the private key/token in git or documentation. Connection readiness is separate from the unresolved source of live open-PO data.
- 2026-08-25: Joel confirmed that PO data is not currently ingested into Snowflake to his knowledge. Work with Deepali/Dor/Ilona to identify the operational source/process, then with Joel to ingest and normalize it; Fivetran is only a candidate after source fit is known. This blocks real PO adapters, shadow, and operational netting—not pure/file engine implementation.
- 2026-08-25: The first improved file-engine tranche uses a required source manifest to distinguish a known zero-row PO result from an unknown `empty_placeholder`/`unavailable` source. Fixture/scenario mode warns; shadow/operational mode fails closed before netting output. Manual `open_pos.csv` is therefore a safe development bridge, not evidence that operational pipeline data exists.
- 2026-08-25: Dated netting treats the selected inventory snapshot as the opening balance on the planning date and applies same-day receipts before daily demand. Overdue POs are reported but not counted; after-horizon and after-final-demand receipts are reported separately. Net requirements remain unrounded grams and exclude candidate receipts so later policy/scheduling cannot be hidden in the ledger.

## What we learned (facts, not guesses)
- Source is `Supply_Planning_Rewe.xlsx`, an Office workbook stored in Drive, modified 2026-08-21. KW34 reference tabs are `Plan KW34` and `Stock KW34`.
- Displayed KW34 values reconcile to: buffered `Daily` rounded to 2 decimals; `Need = ceil(Daily × 6)`; bridge from KW33 daily × 2.5 rounded to 2 decimals; `After` rounded to 1 decimal; `Order = ceil(Need − After)`.
- All 27 filled KW34 stocked-item order cells match that displayed-value path exactly.
- All 28 continuing stocked-item bridge values match the prior week's demand rate within displayed precision. The old claim that KW34 used the new week's rate was wrong.
- Four stocked rows have a positive gap and blank order: Gewürze Quinoa, Roasted Sesame Sauce, Röstzweibeln, and Udon Nudeln. Their operational meaning is unknown.
- `Paprika - big` and `Mischsalat` appear in `Plan KW34` but are absent from `Stock KW34`; each implies about 5 buffered packs over six days.
- KW34 contains master-data conflicts: Creme Fraiche is planned with a 1,000 g pack but netted as 5,000 g; Schnittlauch appears with 250/500/1,000 g pack sizes; names and storage labels drift.
- The original target netting equation double-counted demand. Correct netting uses protection-period demand minus inventory position, followed by a daily stock projection.
- The original safety-stock equation did not clearly match daily sigma. For daily errors use root-sum-of-squares over the protection period, with explicit correlation assumptions.
- MOQ/case rounding can violate an earlier shelf-life cap; hard caps must be rechecked after rounding and infeasible combinations must become exceptions.
- The runnable foundation now includes canonical input/output dataclasses, legacy and canonical CSV adapters, critical-source run-mode gates, pure daily BOM explosion, exact displayed-value legacy rounding, a pure dated event ledger, time-phased stock/open-PO netting, and deterministic audit JSON for both CLI paths.
- The checked-in synthetic fixture produces three audit lines, ten calculated units, one `UNEXPLAINED_BLANK_ORDER` warning, and no blockers.
- The repository verification wrapper passes 33 tests covering domain contracts, BOM/pre-mix aggregation, legacy rounding, canonical file/cross-dataset validation, typed PO statuses, dated netting, audit determinism, actionable CLI errors, stale-snapshot handling, and fixture/scenario/shadow/operational source gates.
- `CIRCUS_MODELS_READER` can read 140 physical tables across `BASE`, `INTERMEDIATE`, `REPORTING`, and `TECH_OPS`; access itself is no longer a blocker.
- Snowflake catalogues generated order recommendations and dish/ingredient forecasts. Joel confirmed that all three are abandoned previous-data-team models; the scheduled refresh observed by SQL does not make them operational.
- V6/V8 measured on 2026-08-25: dish forecasts (115 rows), ingredient forecasts (190), and recommendations (76) refreshed sequentially around 04:31-04:32 Berlin time for one location. Forecasts cover 2026-08-25 through 2026-08-29. This is useful reference evidence for the old automated pipeline, not a live planning source.
- V6 quality: 73 `Sufficient`, 3 `Order Today`; all net, pack-rounding, and cost calculations reconcile. Positive-demand rows use an exact 1.05 uplift. Caveats are one missing ingredient ID, two missing prices, only `FRESH`/`FROZEN`, and one-location coverage.
- V8 key checks: both duplicate/conflict queries returned zero rows. The follow-up classifies 19 ingredient IDs: 12 placeholder-only, six with a real unit plus null/zero placeholders, and one (`Rotes Thai Curry`) mixing `g` and `ml`. No null-unit row is nonzero. The abandoned model is reference only; its anomaly becomes a canonical-unit validation test.
- V7 measured on 2026-08-25: `BASE_INVENTORY` has 106 lines/35 POs, all closed and fully delivered, last synced 2025-10-20; all 106 nonblank delivery strings fail `TRY_TO_DATE`. It is ruled out for open-PO netting and is not yet fit even as receipt history.
- `BASE_STOCKS` has 21 one-location rows, last synced 2025-10-30, with every supplier-article field missing; it is not a current operational stock/supplier master.
- V9 measured: the current flattened BOM has 1,193 clean rows and zero tested revision-key duplicates; all 763 materialized unit-days/26 menu keys resolve; the 11,990-row history has valid intervals. Raw recipe-slot and positive pre-mix mappings exist. Physical silo-to-effective-recipe-slot mapping remains unverified.
- V3 measured: an ingredient-only silo/BOM join is many-to-many for 62 ingredients. Corrected V3B tested 2,576 stock keys: 610 lack active-menu/detailed-menu context, 1,636 match through `INGREDIENT_KEY`, but zero match `SILO_RESOURCE_ID` to `RECIPE_SLOT_INSERTING_POSITION` and no physical slot resolves. The tested direct position join is rejected; inspect lineage or ask the responsible owner for the authoritative bridge before using capacity.
- V10 measured: all 6,497 tested silo-days carry expiry, with `DAYS_UNTIL_EXPIRATION` from -2 to 368. Observation coverage is strong; sealed/opened shelf-life remains approved policy.
- V12 measured: 148,158 raw stock rows are high-frequency state updates. Of 147,980 lagged transitions, 12.0% change ingredient and 62.1% are unchanged; gross positive/negative changes exceed 15 tonnes and contain 7 kg jumps. This is not physical consumption without reset filtering and semantics.
- V4 measured field sums: 3,750.3 kg and EUR 31,339 across six units, 63 ingredients, and 314 unit-days. This is not one dish/unit and must not be called physical disposal before waste/valuation lineage is confirmed.
- V5 measured: 76 item-master rows/75 non-null IDs, one blank ID, no bad pack quantities or missing units, seven missing EANs, and ten missing Apicbase IDs; only the blank ID appears in the duplicate/conflict exception output.
- V11 measured: `INT_UNIT_DAY_MENU` spans 2025-10-21 through 2026-08-24 across six units/26 menus and had no forward-day coverage on 2026-08-25. Base menu rows extend later but mix operational-looking records with pilot/demo/training/far-future/terminated entries.
- V1/V2 corrected output: `CLOSED/SERVED` filtering gives 622 portions across 221 dish-unit-days, including 39 zero-sale days; the 626 provisional total is superseded. Each of six observed location names maps to one unit, and V2B reconciles 622 portions across five selling/production units at 8.4–31.8 portions per service day.
- Detailed query counts and interpretations are preserved in `docs/scratchpads/snowflake_verification_evidence.md`; raw CSVs remain private.

## Open questions / unknowns
- Does `Demand/Silo Load` mean daily portions, silo refill level, or a capacity-limited planning number?
- Exact stock-count timestamp and operational reason for the 2.5-day KW34 bridge.
- Whether blank/reduced order cells mean missed work or manual netting of goods already in transit.
- Canonical item/SKU mapping and pack size, especially Creme Fraiche and Schnittlauch.
- Whether missing fresh rows were ordered through another process.
- Item/supplier production and transport lead times, delivery calendars/cut-offs, MOQ/case, and split-delivery rules.
- Sealed versus opened shelf life, lot/expiry availability, and acceptable max-cover policy.
- Forward committed menu source/horizon and transition ownership; the materialized table currently has no forward-day coverage.
- Authority, lineage, units, coverage, freshness, and ownership for the Snowflake candidates selected for adapters.
- Operational PO system/process and owner, followed by a Snowflake ingestion/model with open quantity, expected receipt, receipt/cancellation/date-change history, and freshness. Joel confirmed no current PO ingestion; Deepali/Dor/Ilona are the next contacts.
- Cross-repository ownership boundary between `data-transformation` models and this repository's pure engine; inspect after GitHub access is granted.
- Stable Snowflake service-account readiness and least-privilege role once Joel provisions it.
- Physical-waste field/valuation semantics and refill/consumption event semantics/state transitions.
- Exact three-level BOM and silo-resource/dock-to-recipe-slot mapping.
- Supabase project ownership, region, auth/RLS roles, retention, and environment access.

## Next steps
- Human now: wait for replies to the already-sent Q1-Q13 set under `HA-01`; do not send a correction. Separately decide the KW34 fixture policy (`HA-02`) and provide raw formulas/owner walkthrough if available (`HA-03`). These are M1 acceptance gates, not a stop-work gate.
- Data now: ask Deepali/Dor (optionally Ilona) for the current PO/expected-delivery source walkthrough, then return the findings to Joel for ingestion/model design. In parallel request `data-transformation` access, complete the least-privilege service-account setup through 1Password, inspect source and physical-slot lineage, and decide the cross-repository boundary. No required verification SQL remains; enhanced V12 is optional until calibration. Defer the waste-definition question until the V4 field sums will be shared or used.
- Engineering next: build the remaining improved-policy layers on the validated event ledger: item-specific protection periods; separate yield/safety inputs; supplier calendars; shelf-life/max-cover; MOQ/case rounding with post-rounding feasibility; fresh delivery-slot coverage; and explainable proposal derivations. Keep real SQL adapters, shadow promotion, and production policy claims behind their recorded gates.
- After `HA-02`, add the minimal real KW33/KW34 fixture, 27-cell golden assertions, four unexplained blank-order assertions, two missing-fresh-row assertions, and master-data quarantine cases.
- Keep accepted SQL adapters, Supabase, real-data backtests, UI, and dispatch behind their recorded milestone gates in `docs/plans/human_action_register.md`.

## Risks / gotchas (things not to forget)
- The connector exposed displayed values, not the raw formula AST; preserve value-level validation caveat until formulas/owner walkthrough are available.
- Never commit the production workbook or sensitive supplier/operational data without approval.
- Do not silently normalize names in the engine; aliases must map to stable IDs through validated master data.
- Do not round early in the improved engine. Legacy rounding belongs only to the compatibility profile.
- Do not treat missing optional data as zero or measured history.
- Do not present CSV/YAML as the final planner workflow or allow files and Supabase to act as competing operational sources of truth.
- Do not create a Supabase project or external infrastructure without explicit approval.
- No supplier dispatch until a separately approved operational milestone.

## Commands / environment notes
- Workbook ID: `1W0fwiO_mf7pQ6G0Oqmp6QE92MCljrXQ-`.
- Workbook URL: `https://docs.google.com/spreadsheets/d/1W0fwiO_mf7pQ6G0Oqmp6QE92MCljrXQ-/edit`.
- Google reports the source as XLSX, not a native Sheet; use read-only Drive fetch rather than native Sheets range APIs.
- On this desktop sandbox, Git commands may need a command-scoped `safe.directory` value and permission to write `.git` metadata.
- Verification: `scripts/check.ps1 -PythonExecutable <python-3.12-path>` sets `PYTHONPATH`, compiles `src`/`tests`, and runs the standard-library suite.
- Current verified result on 2026-08-25: 33 tests passed. Ruff/mypy are configured in `pyproject.toml` but their executables are not installed in the bundled runtime.
