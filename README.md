# Phase 2 Supply Planning

This repository automates the ingredient and purchasing-demand calculation
currently maintained in `Supply_Planning_Rewe.xlsx`.

> **Current status:** the displayed KW33/KW34 stocked-item arithmetic is
> independently reconciled and implemented as `legacy_kw34/v1`. The real
> workbook rows are not yet an automated golden fixture; current tests use safe
> synthetic data. The first improved file path can validate daily forecast,
> menu, BOM, item, inventory, and open-PO inputs, explode demand, and project
> inventory through time. All 32 tests pass. Required Snowflake verification is
> complete, but the live forecast source, current PO source, production stock
> mapping, and editable policy values still require the recorded follow-ups.

## Phase boundary

Phase 1 and Phase 2 are separate:

```text
Phase 1: forecast portions by location, dish, and service day
                              ↓
Phase 2: convert that forecast into ingredient requirements and recommended
         purchase quantities using BOM, stock, open POs, and planning rules
```

Phase 1 may initially be a manually entered forecast and later a Snowflake
model. This repository consumes the forecast; it does not create it.

Lead time, shelf life, pack size, delivery weekdays, MOQ/case size, current
stock, and open POs are Phase 2 inputs because they determine how much needs to
be available or purchased. Sales, OOS, and waste are mainly Phase 1 or later
calibration inputs; they are not required to reproduce the first Phase 2 flow.

## Verified workbook baseline

For stocked items, the displayed KW34 calculation is:

```text
Daily  = round(grams_per_day / pack_size_g × 1.20, 2)
Need   = ceil(Daily × 6)
Bridge = round(KW33_Daily × 2.5, 2)
After  = round(max(0, Stock - Bridge), 1)
Order  = ceil(max(0, Need - After))
```

This reproduces all 27 filled KW34 `Order` cells and all 28 continuing-item
bridge values at displayed precision. Four positive calculated gaps have blank
order cells, two planned fresh ingredients are absent from the stock tab, and
several item/pack mappings conflict. Those cases remain explicit evidence, not
assumptions to silently repair.

Fresh products use the workbook's Saturday/Monday/Wednesday/Friday
delivery-to-delivery pattern. The exact operational meaning of those columns is
still one of the questions already sent to the Excel owner.

## Target architecture

```text
Snowflake operational inputs ─┐
                              ├─> Python Phase 2 job ─> Snowflake result tables
Supabase planning rules ──────┘
          ↑
internal React UI + Python API
```

- **Snowflake inputs:** forecast, menu/BOM, item identity/pack data, stock, and
  eventually normalized open POs.
- **Supabase:** application-owned editable rules such as lead time, shelf life,
  storage-class defaults, safety settings, MOQ/case size, and simple delivery
  weekday/cut-off rules.
- **Internal UI:** lets non-technical users validate and edit those rules. It is
  not a supplier-ordering or approval application.
- **Python job:** reads the active inputs/configuration, performs the pure
  calculation, and writes recommendations, derivations, warnings, run ID, and
  input/config versions to internal Snowflake result tables.

CSV files remain useful for fixtures, deterministic tests, local development,
and controlled recovery. They are not the long-term editing workflow.

## Phase 2 calculation scope

The intended calculation is:

1. Read daily dish forecast by location.
2. Validate that the dish is active in the menu and select the effective BOM.
3. Explode `Dish → Silo / pre-mix → Ingredient` into daily grams.
4. Aggregate shared ingredients by location and day.
5. Select timestamped usable stock.
6. Include open PO quantities on their expected receipt dates.
7. Determine the demand coverage period from the configured lead time and
   review/delivery cadence.
8. Calculate the remaining ingredient requirement without double-counting
   demand.
9. Apply only confirmed Phase 2 rules: pack rounding and, where configured,
   shelf-life/max-cover, MOQ/case, fresh delivery coverage, and safety policy.
10. Write internal recommendations and visible exceptions to Snowflake.

“Delivery schedule” means simple planning-rule data such as delivery weekdays;
it does not mean an external calendar integration. There is no supplier or ERP
write in this project.

## What is implemented

- typed canonical contracts and stable-ID validation;
- provenance for observed, manual, defaulted, placeholder, and unavailable data;
- pure three-level BOM explosion and shared-item aggregation;
- exact displayed-value `legacy_kw34/v1` arithmetic;
- canonical multi-file CSV adapters with actionable errors;
- timestamped inventory and dated open-PO event ledger;
- daily projected balance and late/stale/stockout exceptions;
- deterministic audit JSON and strict shadow/production source gates;
- synthetic legacy and multi-location improved scenarios.

The improved path currently stops at unrounded net requirement. It does not yet
apply the full configurable Phase 2 policy or persist to Snowflake/Supabase.

## Delivery order

1. Complete the real KW33/KW34 golden validation and planner interpretation.
2. Finish the minimum improved Phase 2 calculation with explicit config inputs.
3. Connect verified Snowflake inputs/results and establish Supabase config
   storage for the same validated rule contract.
4. Compare automated results with the Excel owner over representative runs.
5. Add the small internal config UI for non-technical users.
6. Schedule and monitor the internal job.
7. Add advanced calibration only when it proves useful.

## What is blocked and what can continue

There is no blocker to the next engineering tranche: real KW parity work and
the small parameterized Phase 2 calculation can continue now. The items below
block only the named later outcome.

- The 13 Excel-owner answers block business interpretation and final parity
  sign-off, not continued engineering.
- A real committed KW33/KW34 golden fixture needs the recorded data-handling
  decision; a private/local fixture can still be used.
- Joel's service account, `data-transformation` access, and the target Snowflake
  output schema/write pattern are needed for live integration.
- Ops must identify the actual PO source before complete production netting.
- Supabase ownership/access is needed only when the configuration UI tranche
  begins.

No further required V1-V12 Snowflake verification query remains.

## Engineer handover

| File | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Repository implementation boundaries |
| [`docs/descriptions/phase2_supply_planning_brief.md`](docs/descriptions/phase2_supply_planning_brief.md) | Workbook evidence, target logic, and architecture |
| [`docs/plans/phase2_supply_planning_master_backlog.md`](docs/plans/phase2_supply_planning_master_backlog.md) | Prioritized implementation backlog |
| [`docs/descriptions/data_requirements.md`](docs/descriptions/data_requirements.md) | Phase ownership and source status |
| [`docs/descriptions/canonical_data_contracts.md`](docs/descriptions/canonical_data_contracts.md) | Stable engine contracts and file schemas |
| [`docs/plans/human_action_register.md`](docs/plans/human_action_register.md) | Exact human/access actions and their impact |
| [`docs/scratchpads/snowflake_verification_evidence.md`](docs/scratchpads/snowflake_verification_evidence.md) | Durable V1-V12 evidence without private CSVs |
| [`MEMORY.md`](MEMORY.md) | Durable decisions that survive handovers |

## Quick start

The core targets Python 3.12 and has no third-party runtime dependencies.

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m supply_planning legacy-run `
  --input tests\fixtures\synthetic_legacy\legacy_inputs.csv `
  --output output\synthetic_legacy_audit.json
python -m supply_planning improved-run `
  --input-dir tests\fixtures\synthetic_improved `
  --output output\synthetic_improved_audit.json `
  --planning-as-of 2026-08-25T00:00:00+02:00 `
  --run-mode scenario
```

Or run:

```powershell
.\scripts\check.ps1 -PythonExecutable "C:\path\to\python.exe"
```

## Safeguards

- Keep calculation functions pure; Snowflake, Supabase, files, and UI remain
  adapters.
- Use daily demand, stable IDs, grams internally, and explicit pack units.
- Preserve `Dish → Silo → Ingredient`, including pre-mixes.
- Never silently treat missing data as observed zero.
- Keep KW33/KW34 compatibility separate from corrected Phase 2 policy.
- Persist enough input/config version information to reproduce a result.
- Do not commit credentials, private production extracts, or an unapproved
  workbook fixture.
- Do not add supplier/ERP dispatch to this scope.
