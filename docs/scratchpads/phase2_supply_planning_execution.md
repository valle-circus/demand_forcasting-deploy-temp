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
- [ ] Add the approved real KW34 golden fixture and remaining legacy workbook paths after the relevant human gates clear.

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
- The runnable foundation now includes canonical input/output dataclasses, critical-source run-mode gates, pure daily BOM explosion, exact displayed-value legacy rounding, a compatibility CSV adapter, and deterministic audit JSON.
- The checked-in synthetic fixture produces three audit lines, ten calculated units, one `UNEXPLAINED_BLANK_ORDER` warning, and no blockers.
- The repository verification wrapper passes 17 tests covering domain contracts, BOM/pre-mix aggregation, legacy rounding, audit determinism, actionable CLI errors, and fixture/shadow/operational source gates.

## Open questions / unknowns
- Does `Demand/Silo Load` mean daily portions, silo refill level, or a capacity-limited planning number?
- Exact stock-count timestamp and operational reason for the 2.5-day KW34 bridge.
- Whether blank/reduced order cells mean missed work or manual netting of goods already in transit.
- Canonical item/SKU mapping and pack size, especially Creme Fraiche and Schnittlauch.
- Whether missing fresh rows were ordered through another process.
- Item/supplier production and transport lead times, delivery calendars/cut-offs, MOQ/case, and split-delivery rules.
- Sealed versus opened shelf life, lot/expiry availability, and acceptable max-cover policy.
- Forward committed menu horizon and transition ownership.
- Source systems/tables and access for stock, POs, receipts, sales, waste, OOS, BOM, and menu.
- Supabase project ownership, region, auth/RLS roles, retention, and environment access.

## Next steps
- Human now: obtain Q1/Q4/Q5/Q6/Q9 answers and supporting examples (`HA-01`), decide the KW34 fixture policy (`HA-02`), and provide raw formulas/owner walkthrough if available (`HA-03`). These are M1 acceptance gates, not a stop-work gate.
- Engineering next: implement canonical multi-dataset validation/file adapters and the remaining legacy stocked/fresh paths without embedding source-system schemas.
- After `HA-02`, add the minimal real KW33/KW34 fixture, 27-cell golden assertions, four unexplained blank-order assertions, two missing-fresh-row assertions, and master-data quarantine cases.
- Keep SQL discovery, Supabase, real-data backtests, UI, and dispatch behind their recorded milestone gates in `docs/plans/human_action_register.md`.

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
- Current verified result on 2026-08-24: 17 tests passed. Ruff/mypy are configured in `pyproject.toml` but their executables are not installed in the bundled runtime.
