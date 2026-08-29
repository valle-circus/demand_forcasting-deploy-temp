# Phase 2 Supply Planning

This repository automates the ingredient and purchasing-demand calculation
currently maintained in `Supply_Planning_Rewe.xlsx`.

> **Current status (2026-08-29):** the displayed KW33/KW34 stocked-item arithmetic is
> independently reconciled and implemented as `legacy_kw34/v1`. The real
> workbook rows are not yet an automated golden fixture; current tests use safe
> synthetic data. The first improved file path can validate daily forecast,
> menu, BOM, item, inventory, and open-PO inputs, explode demand, and project
> inventory through time. The interim Transgourmet PDF adapter is implemented
> and locally validated. Two project-owned Excel templates are now prefilled
> for a six-week, one-location pod/ingredient demonstration. The recurring V1
> no longer adapts arbitrary maintainer workbook layouts and requires no current
> Snowflake input. The strict template readers, Apicbase stock normalizer,
> reviewed Transgourmet mapping bridge, purchase-recommendation policy, and
> table-ready outputs are implemented. A complete scenario run for
> `LOC_DEMO_001` is byte-stable, has zero blockers, and produces 23 dated
> recommendation lines across 11 items. The local technical V1 is complete;
> maintainer approval of highlighted policy/mapping fields is the gate before
> operational/shadow use. The monorepo UI foundation is now implemented: a
> React/TypeScript/Vite/Tailwind status shell plus an authenticated FastAPI/
> Supabase backend for controlled imports, immutable versions, synchronous
> planning runs, atomic result persistence, Overview/location reads, and
> downloads. Migration 003 and live cloud/Auth configuration remain external
> setup steps; the three React domain pages are the next implementation slice.

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
bridge values at displayed precision. The owner thinks the four positive-gap
blank orders were missed; two planned fresh ingredients are handled outside the
stocked path; and selected item/pack conflicts are now resolved. Historical
cells remain explicit evidence, not values to silently repair.

Improved V1 preserves the intent of the old 20% extra-demand buffer—to reduce
OOS risk—but separates it from recipe yield. Proposed safety is 7 days for
pods, 2 days for ordinary stocked items
and 0.5 day for fresh; `yield_factor=1.00` unless deterministic loss is known.
The fixed six-day target becomes item-specific `lead + review` coverage (35
days for pods and 10 for ordinary stocked items under the proposed seven-day
weekly review). The `×2.5` bridge becomes day-by-day projection from the stock
timestamp with dated demand and open POs.

Fresh products use the owner-confirmed service windows `Sat→Mon`,
`Mon→Tue+Wed`, `Wed→Thu+Fri`, and `Fri→Sat`. The weekday columns are delivery
allocations, but whether their cells mean intended, placed, confirmed, or
delivered packs still needs focused confirmation.

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

For prototype simplicity, normalized immutable input versions plus the same
canonical master/run/output records may be stored temporarily in Supabase
before the Snowflake paths are ready. This is an explicit persistence-adapter
exception, not a new calculation model or a reason to store raw file bytes in
Postgres. See `docs/descriptions/ui_api_and_persistence_foundation.md`.

## Phase 2 calculation scope

The intended calculation is:

1. Read daily dish forecast by service location and map/aggregate it once to the
   inventory/planning location. The manual three-unit forecast is already
   combined at the central prep kitchen and must not be tripled.
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
- a local Transgourmet PDF-to-CSV helper with content deduplication, delivery-total
  reconciliation, full history output, canonical dated `open_pos.csv`, and an
  explicit undated-open review output;
- timestamped inventory and dated open-PO event ledger;
- daily projected balance and late/stale/stockout exceptions;
- deterministic audit JSON and strict shadow/production source gates;
- strict project-owned Excel-template readers and actionable schema validation;
- Apicbase stock XLSX normalization with export timestamp, fractional stock,
  UID/exact-name mapping review, and explicit scenario-only zero assumptions;
- location-aware Transgourmet PDF normalization with dated-PO quarantine and
  carton-to-pack conversion;
- item-specific lead/review coverage, explicit safety/yield, fresh service
  windows, shelf/max-cover, MOQ/case and final order-unit rounding;
- table-ready recommendations, derivations, exceptions, mapping-review files,
  a concise maintainer summary, and byte-stable replay; and
- synthetic legacy/multi-location scenarios plus the complete local demo run;
- an authenticated FastAPI boundary with schema-aware readiness, controlled
  import/run/master-activation routes, portable Supabase repositories, read
  models, downloads, CORS, and tests;
- a basic React/TypeScript/Vite/Tailwind status shell with browser/server
  environment separation; and
- additive Supabase master/run/output, import/input/netting/daily-projection,
  transaction/immutability migrations, a synthetic UI seed, and Render/Vercel
  deployment configuration.

The three React domain pages and field-level master/menu editors are not yet
implemented. Workbook upload plus validated draft activation is the first
master-data workflow. The high-level Overview, Location planning, and Data &
settings journey is defined in
`docs/descriptions/ui_maintainer_journey_and_page_plan.md`; detailed visual
design and frontend implementation remain open.

## Delivery order

1. Send the completed local V1 packet to the maintainer and collect approved or
   corrected template/policy/mapping rows. Rerun before operational use.
2. Apply migration 003, configure the cloud/Auth environment, and verify one
   safe backend workflow through FastAPI.
3. Build Data & settings, Location planning, and Overview against the
   implemented API; keep demo/unapproved values visibly labelled.
4. Add field-level master/menu maintenance, then move each input/result repository
   to Snowflake when its accepted operational contract exists.
5. Shadow-validate representative runs and then schedule/monitor the job.
6. Keep KW33/KW34 parity as a separate compatibility track and add advanced
   calibration only when it proves useful.

## What is blocked and what can continue

There is no remaining local V1 implementation tranche. The items below block
only operational approval or the named later outcome.

- The original 13 Excel-owner answers are received. Local V1 now keeps the
  current menu effective until superseded and repeats it for six dummy weeks,
  uses an upload-selected location and stock export time as `counted_at`,
  and pod expiry as order date + 365 days. Ordinary, fresh and pod lead
  durations are confirmed as 3 days, 5 days and 28 calendar days respectively.
  Only the
  focused stock/order-unit, article-mapping, delivery cut-off/receipt timing,
  and policy values block production sign-off.
- A real committed KW33/KW34 golden fixture needs the recorded data-handling
  decision; a private/local fixture can still be used.
- Joel's service account, `data-transformation` access, and the target Snowflake
  output schema/write pattern are needed for live integration.
- Transgourmet pending-order history is the current PO process, but an approved
  normalized export/API and Snowflake ingestion are still needed for complete
  production netting.
- Migration 003, Supabase/API/browser credentials, and a safe Auth user are
  needed for live connected testing; the unconfigured API still runs locally
  and reports that state explicitly.

No further required V1-V12 Snowflake verification query remains.

## Engineer handover

| File | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Repository implementation boundaries |
| [`docs/descriptions/phase2_supply_planning_brief.md`](docs/descriptions/phase2_supply_planning_brief.md) | Workbook evidence, target logic, and architecture |
| [`docs/plans/phase2_supply_planning_master_backlog.md`](docs/plans/phase2_supply_planning_master_backlog.md) | Prioritized implementation backlog |
| [`docs/plans/v1_template_first_delivery_plan.md`](docs/plans/v1_template_first_delivery_plan.md) | Active local V1 checklist and acceptance criteria |
| [`docs/plans/legacy_and_deprecation_register.md`](docs/plans/legacy_and_deprecation_register.md) | Classified runtime, compatibility, cleanup and archive candidates |
| [`docs/descriptions/data_requirements.md`](docs/descriptions/data_requirements.md) | Phase ownership and source status |
| [`docs/descriptions/canonical_data_contracts.md`](docs/descriptions/canonical_data_contracts.md) | Stable engine contracts and file schemas |
| [`docs/descriptions/ui_api_and_persistence_foundation.md`](docs/descriptions/ui_api_and_persistence_foundation.md) | Monorepo, API, frontend, Supabase, environment, and deployment boundaries |
| [`docs/descriptions/ui_maintainer_journey_and_page_plan.md`](docs/descriptions/ui_maintainer_journey_and_page_plan.md) | Three-page customer journey, KPI/page/component plan, code/API mapping, and source-persistence handover |
| [`docs/claude_code_first_ui_pages_brief.md`](docs/claude_code_first_ui_pages_brief.md) | Copy-paste Claude Code instruction for the first honest, navigable UI page slice |
| [`docs/descriptions/v1_assumptions_and_admin_validation.md`](docs/descriptions/v1_assumptions_and_admin_validation.md) | Concise maintainer review of active values, assumptions, legacy factors, and questions |
| [`docs/plans/human_action_register.md`](docs/plans/human_action_register.md) | Exact human/access actions and their impact |
| [`docs/reports/planner-questionnaire-review/report.html`](docs/reports/planner-questionnaire-review/report.html) | Sanitized Q1-Q13 clarification and follow-up report |
| [`docs/scratchpads/snowflake_verification_evidence.md`](docs/scratchpads/snowflake_verification_evidence.md) | Durable V1-V12 evidence without private CSVs |
| [`docs/scratchpads/ui_and_supabase_foundation.md`](docs/scratchpads/ui_and_supabase_foundation.md) | Living notes for the UI/API/Supabase implementation |
| [`MEMORY.md`](MEMORY.md) | Durable decisions that survive handovers |

## Quick start

The project targets Python 3.12. `openpyxl` is the small base dependency for
read-only XLSX normalization; `pdfplumber` is optional for Transgourmet PDFs.

The normal planner-facing local path is `v1-run` under “Complete local
template-driven V1” below. `improved-run` is the direct canonical-file
developer path, and `legacy-run` is only the isolated KW34 compatibility tool;
neither means that the old workbook is a recurring V1 input.

### API and UI foundation

Create the local Python environment and install the API/PDF extras:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[api,pdf-import]"
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn apps.api.supply_planning_api.main:app --reload
```

In another terminal, start the web app:

```powershell
Set-Location apps\web
Copy-Item .env.example .env.local
pnpm install
pnpm dev
```

Open `http://localhost:5173`. The API health endpoint is
`http://localhost:8000/api/v1/health`; readiness is
`http://localhost:8000/api/v1/readiness`. Without Supabase values, readiness
correctly reports `degraded/not_configured` while process health remains `ok`.

Before cloud setup, read `apps/api/README.md`, `apps/web/README.md`, and
`supabase/README.md`. Vercel should use `apps/web` as project root. Render uses
the repository-root `render.yaml` because the API imports `src/supply_planning`.

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

### Complete local template-driven V1

Use the two fixed templates, one current Apicbase stock report, the cumulative
Transgourmet PDF folder, and an explicit planning location:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m supply_planning v1-run `
  --master-workbook "C:\path\Phase2_Master_Data_Template_v1.xlsx" `
  --planning-workbook "C:\path\Phase2_Planning_Input_Template_v1.xlsx" `
  --stock-workbook "C:\path\current-stock-report.xlsx" `
  --po-pdf-dir "C:\path\transgourmet-pdfs" `
  --output-dir "C:\path\private-v1-output" `
  --location-id "LOC_DEMO_001" `
  --run-mode scenario
```

The planning cutoff defaults to the stock export timestamp. The output folder
contains normalized table rows, recommendations, derivations, exceptions,
mapping reviews, a deterministic audit, and `maintainer_review_summary.md`.
Keep it private because normalized stock and PO rows can contain operational
data. Use `shadow` or `production` only after the maintainer approval gate.

### Manual Transgourmet PO import

Install the optional PDF dependency once:

```powershell
python -m pip install -e ".[pdf-import]"
```

Then run the Windows helper. It scans the top level of Downloads, ignores
unrelated PDFs, deduplicates repeated downloads by normalized document content,
and writes only to the ignored private-data directory:

```powershell
.\scripts\extract_transgourmet_pos.ps1 `
  -LocationId "REWE_CENTRAL_PREP" `
  -AsOfDate "2026-08-26"
```

Outputs under `data/private/transgourmet/` are:

- `transgourmet_po_history.csv`: every extracted line with source hashes,
  supplier article metadata, ordered quantity, scheduled delivery date, and
  status derived for the selected as-of date;
- `transgourmet_supplier_items.csv`: one mapping-review row per supplier article;
- `open_pos.csv`: canonical purchase-order rows whose `Liefertag` is strictly
  after the explicit as-of date;
- `undated_open_pos.csv`: open rows with no `Liefertag`, kept visible but not
  passed into dated inventory netting; and
- `import_summary.json`: counts, a deterministic source version, and the
  assumptions that require review.

Status follows the confirmed portal rule for the explicit as-of date: no
`Liefertag` or a future `Liefertag` means `open`; a `Liefertag` on that date or
in the past means `closed`/received. The PDF still has no remaining quantity,
so open rows use displayed ordered quantity as `open_qty_units`. An undated row
cannot safely enter the current dated netting contract without inventing a
receipt date, so it is quarantined in `undated_open_pos.csv`. With no
`-ItemMap`, the helper uses visibly provisional `TG-<article number>` item IDs;
pass a reviewed two-column CSV with `supplier_article_number,item_id` once the
canonical mapping is available. Raw PDFs and generated private CSVs are ignored
by Git.

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
