# Supply Planning Automation — Phase 2 Engineering Brief

**Scope:** replace the manual weekly Excel supply-planning process with an internal Python job and editable rule store/UI.
**Status:** discovery and KW34 value-level validation complete; M0/M1 foundation and the first unblocked M2 file-engine tranche are implemented. Canonical CSV validation, daily menu-aware demand, a pure dated inventory/open-PO ledger, time-phased netting, strict source gates, and deterministic improved-run audit output are runnable. Real KW34 fixture acceptance, policy/constraint/scheduling logic, and real source adapters remain open.
**Source analysed:** [`Supply_Planning_Rewe.xlsx`](https://docs.google.com/spreadsheets/d/1W0fwiO_mf7pQ6G0Oqmp6QE92MCljrXQ-/edit?gid=844782362#gid=844782362) (Excel workbook stored in Google Drive), tabs `Plan KW34` / `Stock KW34`, cross-checked against adjacent weeks. Revalidated read-only on 2026-08-22 against the workbook modified on 2026-08-21.
**Audience:** the engineer who will build and own the Phase 2 service.

---

## 1. What this document is for

This is the context pack for building Phase 2. It explains what the current manual process does, exactly how its arithmetic works, where it breaks, what the target logic should be, and a proposed architecture. Read sections 3–6 before writing any code — the current spreadsheet contains real domain logic that must be preserved, and several bugs that must not be.

### Validation conclusion

The overall direction is sound: reproduce the manual process first, isolate a pure engine behind file adapters, then introduce improved planning, real data, shadow testing, and a UI. The original brief was **not implementation-ready** in three places that are corrected here: it mischaracterised the KW34 bridge as using the new week's demand, its target netting equation double-counted pre-arrival demand, and its safety-stock equation was ambiguous about the grain of `σ`.

Confidence is **high** for the displayed KW34 legacy arithmetic and **medium** for the operational meaning of blank/booking cells, lead times, shelf life, and pipeline handling. The source is an Office workbook in Drive; the connector exposed displayed cell values but not a formula AST. The reconstruction was therefore independently reconciled at value level. Preserve this caveat until the raw workbook formulas or an owner walkthrough confirm the exact cell implementation.

The implemented canonical field definitions and source-mapping boundary are maintained in `docs/descriptions/canonical_data_contracts.md`. The engine contracts do not assume physical Snowflake, ERP, or Supabase table names. Current code uses Python 3.12 standard-library dataclasses and `Decimal` with no third-party runtime dependency; source/UI frameworks remain adapter-boundary decisions for later milestones.

The current `improved_file/v1` implementation covers only the policy-free core
of Milestone 2: validated daily forecast/menu/BOM/item/inventory/open-PO CSVs,
dated demand and receipt events, signed daily stock projection, open-PO netting,
stockout/late-receipt exceptions, deterministic audit JSON, and fail-closed
shadow/production source gates. It does not yet calculate purchasable order
proposals because lead-time/review, safety/yield, shelf-life, MOQ/case, supplier
delivery-rule, and fresh-slot policies are intentionally still unapproved or
unimplemented.

---

## 2. Business context

Circus operates autonomous robot kitchens deployed in host locations (the analysed file covers a REWE site). Each kitchen holds a set of **silos** — physical hoppers loaded with either a single ingredient or a pre-portioned **pre-mix** (several ingredients bagged together). A dish is assembled from several silos.

The menu rotates weekly (`KW` = Kalenderwoche / ISO week). The store operates **6 days a week** (Mon–Sat). Ingredient deliveries arrive on **four slots per week: Saturday, Monday, Wednesday, Friday**.

Ingredients fall into four storage classes, which drive completely different ordering behaviour:

| Class | Meaning | Behaviour today |
|---|---|---|
| `TK` | Tiefkühl / frozen | Stocked, long shelf life |
| `Kühl` | Refrigerated | Stocked, short shelf life — **highest waste risk** |
| `RT` | Room temperature | Stocked, long shelf life |
| `Frisch` | Fresh produce | **No stock held**, ordered per delivery slot |

---

## 3. The two-phase model

```
PHASE 1 — FORECAST                    PHASE 2 — DEMAND PLANNING / ORDERING
sales history, waste, OOS    ──────>  BOM explosion → netting → order proposal
        ↓                                        ↓
portions per dish per day             units to order per item per delivery date
```

**No approved/live Phase 1 has been confirmed.** The current workbook interface is a human typing one integer per dish per week into a column called `Demand/Silo Load`. Snowflake contains a five-day, one-location dish forecast whose tested `date × location × PLU` key and basic value checks pass, plus ingredient forecasts and generated recommendations refreshed within the same minute. Joel confirmed on 2026-08-25 that these are abandoned previous-data-team models, despite the observed refresh. They may be replaced in the `data-transformation` repository, but they are not an approved live Phase 1 source or Phase 2 policy. Phase 1 therefore remains a pluggable upstream contract rather than an embedded assumption. Everything downstream of the workbook value is deterministic arithmetic.

**This project is Phase 2 only.** Phase 1 is an independent upstream workstream.
Phase 2 must therefore treat the forecast as a *pluggable input*: today a
manually maintained value/file, later an authoritative Snowflake table, with no
change to the engine.

### Interface contract (design to this now)

Phase 2 consumes a demand signal shaped like:

| field | type | notes |
|---|---|---|
| `location_id` | string | single site today, must scale to N |
| `dish_id` | string | stable key, not display name |
| `service_date` | date | **daily granularity, not weekly**; adapters may map an upstream `date` field explicitly |
| `forecast_portions` | float | expected portions sold |

Building the engine against a *daily* contract from day one is important. The current sheet uses one flat weekly number, and the fresh-produce logic already proves demand is not flat across weekdays. If Phase 2 is built to consume a weekly constant, it will average away Phase 1's output the moment it arrives.

---

## 4. Current logic, reverse-engineered

Two tabs per week. At the displayed-value level, they behave as weekly snapshots that are copied forward manually; no reliable cross-tab linkage is evident. The connector did not expose the workbook formula AST, so exact formula references still require raw-workbook inspection or an owner walkthrough.

### 4.1 `Plan KWxx` — the bill of materials

Structure is three-level: `Dish → Silo → Ingredient`.

| Column | Meaning |
|---|---|
| `Dish` | Menu item |
| `Silo` | Hopper, or a named pre-mix bag |
| `Ingredients` | The actual purchasable item |
| `Storage - MHD` | Storage class (TK / Kühl / RT / Frisch). Despite the name, **no shelf-life data is recorded here** |
| `Demand/Silo Load` | Treated as the daily planning quantity in the legacy arithmetic and expected to become the Phase 1 input; its exact business meaning still needs owner confirmation (see §10 Q1) |
| `Quantity required/dish` | Grams of this ingredient per portion |
| `Quantity required/day` | `Demand × grams per portion` |
| `Quantity required/week` | `day × 7` — **dead column, see §5.10** |
| `Unit Size` | Grams per purchasable pack |

Example, `Penne Arrabbiata mit Hähnchen`, KW34: demand 30 portions/day, Arrabbiata Sauce at 200 g/portion → 6,000 g/day.

Snowflake now provides a strong candidate for the flattened, versioned part of
this contract: 1,193 current PLU-to-ingredient rows have complete keys, positive
grams, no tested revision-key duplicates, and cover all 763 materialized
unit-days/26 menu keys. Raw recipe-slot and pre-mix mappings also exist. The
remaining gap is physical identity: an ingredient-only join to robot stock is
many-to-many, and silo resources can change ingredient over time, so the
effective `unit/menu/recipe slot ↔ resource/dock` mapping is still required.
Corrected V3B reinforces that boundary: 1,636 of 2,576 stock keys find active-
menu ingredient context through `INGREDIENT_KEY`, but none match
`SILO_RESOURCE_ID` to `RECIPE_SLOT_INSERTING_POSITION` and no exact physical
slot is resolved. The direct position-equality hypothesis is therefore rejected;
capacity logic must wait for an authoritative bridge, not another inferred join.

### 4.2 `Stock KWxx` — netting and order proposal

Grouped by storage class. For ingredient *i*:

| Step | Column | Formula |
|---|---|---|
| 1 | *(implicit)* | `grams_per_day_i = Σ over dishes ( demand_d × grams_d,i )` |
| 2 | `Daily` | `round(grams_per_day_i / pack_size_i × 1.2, 2)` |
| 3 | `Need (6d)` | `ceil(Daily × 6)` using the two-decimal `Daily` value |
| 4 | `KW33 (3d)` | `round(previous_week_Daily × 2.5, 2)` — consumption expected before the new week starts |
| 5 | `After` | `round(max(0, Stock − bridge), 1)` |
| 6 | `Order` | `ceil( max( 0, Need − After ) )` |
| 7 | `S / M / W / Fr` | Manual booking per delivery slot. No formula |

Worked example — Penne, KW34:

```
grams/day = 5,970 (Arrabbiata) + 7,410 (Truffle) + 4,740 (Bolognese) = 18,120 g
Daily     = 18,120 / 1,000 × 1.2                    = 21.74 units
Need(6d)  = ceil(21.74 × 6)                         = 131 units
Bridge    = 21.74 × 2.5                             = 54.36 units
After     = max(0, 86 − 54.36)                      = 31.6 units
Order     = ceil(131 − 31.6)                        = 100 units   ✓ matches sheet
```

**Verification:** at displayed-value level, this reconstruction reproduces all **27 of 27 filled** `Order` cells in `Stock KW34`. It also reproduces all **28 of 28** bridge values for stocked items that continue from KW33 when the prior week's demand rate and the rounding above are used. Four additional stocked rows have a positive computed gap and a blank order cell (§5.4). This is the legacy specification that Milestone 1 must reproduce; its rounding is part of that compatibility profile, not the target engine's internal precision policy.

### 4.3 Fresh produce — separate path

No stock is held. Each delivery must last until the next one arrives:

| Delivery slot | Days covered | Multiplier |
|---|---|---|
| Saturday | Sat | 1 |
| Monday | Mon, Tue | 2 |
| Wednesday | Wed, Thu | 2 |
| Friday | Fri | 1 |

`buffered_daily_units = grams_per_day / pack_size × 1.2`, then order per slot = `buffered_daily_units × multiplier`. Verified on `Stock KW34`: Paprika 5 mm at 2,340 g/day ÷ 1,500 g pack = 1.56 units/day → buffered 1.87, then Sa 1.87, Mo 3.74, We 3.74, Fr 1.87.

The coverage arithmetic is directionally correct. The weakness is that it multiplies an *average* day, so it assumes Monday and Tuesday have identical demand. KW34 also exposes two integrity failures: `Paprika - big` and `Mischsalat` are present in `Plan KW34` at 630 g/day each but have no row in `Stock KW34`; each implies about 0.76 buffered packs/day and 5 packs over six days. `Schnittlauch` appears with three different pack sizes (`250`, `500`, and `1000` g), so its stock-row quantity cannot be verified without a canonical item/SKU master.

---

## 5. What is broken or not auditable

Ranked by impact.

### 5.1 The coverage horizon is shorter than the lead time — CRITICAL

The model orders **6 days** of requirement. Actual lead time is reported as up to **4 weeks** (≈3 weeks production + 1 week transport).

| Item | Sheet gross need (6 d) | Gross demand through 28 days |
|---|---|---|
| Penne | 130 u | **609 u** |
| Udon Nudeln | 137 u | **640 u** |
| Grana Padano | 45 u | **212 u** |

This is not a tuning error, it is a structural one. The inventory position must protect demand until the next replenishment can arrive, which is normally `lead_time + review_period`. The 28-day numbers above are **gross protection-period demand, not automatically the new order quantity**: usable on-hand and open POs must be netted from them. Once a pipeline is full, a weekly order can rationally be close to one week's demand; at launch or with no pipeline it can be much larger.

### 5.2 In-transit stock is invisible in the sheet — critical visibility regression

`Stock KW29` and `Stock KW32` had a `Delivery` column and computed `Available = Stock + Delivery`. `Stock KW33` and `Stock KW34` **dropped it**. What happens after that is not yet proven. There are two competing hypotheses:

1. **The pipeline is untracked.** The planner sees the same shortage in consecutive weekly runs, duplicates the order, and the deliveries later land together.
2. **The pipeline is tracked outside the sheet.** The planner remembers or records elsewhere what is already on order, and blank or reduced order cells mean "already in transit."

The following over-cover evidence from `Stock KW34` is consistent with hypothesis 1, but it does not rule out hypothesis 2 (days of cover = stock ÷ daily run rate):

| Item | Class | Stock | Daily | Days of cover |
|---|---|---|---|---|
| Trüffel Sauce | Kühl | 110 | 3.60 | **31** |
| Gelbe Thai Curry Sauce | Kühl | 80 | 2.34 | **34** |
| Teriyaki Sauce | Kühl | 25 | 0.94 | **27** |
| Schoko-Kaiserschmarrn | TK | 60 | 1.65 | 36 |
| Balsamico | RT | 26 | 0.65 | 40 |
| Speisesalz | RT | 59 | 0.22 | 268 |

Three chilled items sitting above 26 days of cover indicates material waste risk. The open-PO location and the meaning of the delivery-slot entries must be confirmed before attributing that over-cover to duplicated orders; questions 5–6 in §10 settle the distinction.

### 5.3 The flat ×1.2 buffer conflates two different things

One hardcoded factor is standing in for both deterministic loss (yield: spillage, portioning overage, prep waste, trim) and stochastic uncertainty (forecast error, lead-time variance). They behave differently — yield is multiplicative on demand, safety stock is additive and scales with `√(lead time)` — and they need different data to calibrate. A flat 20% simultaneously over-orders stable staples and under-protects volatile ones.

### 5.4 Unexplained blank order cells

Four rows in `Stock KW34` have a computed gap and a blank order cell. These may be missed orders, or they may be deliberate suppression because the goods were already in transit and the planner netted them outside the visible calculation:

| Item | Need (6d) | After bridge | Unexplained computed gap |
|---|---|---|---|
| Udon Nudeln | 138 | 33.9 | **105** |
| Roasted Sesame Sauce | 13 | 0.0 (already short mid-week) | **13** |
| Röstzwiebeln | 12 | 6.2 | **6** |
| Gewürze Quinoa (NEW) | 12 | — (row half-filled) | — |

That is 124 units of unexplained requirement in a single week. The sheet has no validation or visible in-transit field that would distinguish an omission from a deliberate suppression.

Separately, two planned fresh ingredients have no `Stock KW34` row at all: `Paprika - big` and `Mischsalat`. At the KW34 plan rate each represents an additional computed six-day need of 5 packs. These may also have been handled outside the visible tab, but the omission is not auditable.

### 5.5 The two tabs are not linked

`Plan KW34` shows 0 g/day for every ingredient of the Quinoa Süßkartoffel Bowl (demand was entered as 15 but the quantity columns were never filled). Yet `Stock KW34` correctly carries that dish's 15 portions/day through Speisesalz (0.22 daily), Süßkartoffel Würfel (1.00) and Gurken (1.48). Someone recalculated by hand outside the sheet. There is no single source of truth.

### 5.6 Master data drifts

Every week's tab is a copy of the last one, so item attributes fork silently.

- Creme Fraiche: pack size `1000` in `Plan KW34`, netted at `5000` in `Stock KW34`.
- `Öl` in the Udon recipe is silently treated as `Sonnenblumenöl` in netting (verified: including it reconciles the 3.01 daily figure; excluding it gives 2.86).
- Name variants coexisting: `Frisch`/`Frish`, `Frühlingszwiebel`/`Frühlingszweibeln`, `Salz`/`Speisesalz`, `Kartoffel wurfel`/`Kartoffel Würfel`, `Grana Padano`/`Grana Padano D.O.P. gehobelt mind. 32%`, `Getrüffelte Kartoffelcremesuppe`/`Getrüffelte Kartoffelecremesuppe`.

### 5.7 Calculated order ≠ placed order

The `S / M / W / Fr` columns are the four delivery slots and hold what was actually booked. They do not reconcile with the `Order` column and there is no formula:

| Item | Calculated | Booked across slots |
|---|---|---|
| Penne | 100 | 20 + 40 = 60 |
| Chicken Flakes | 6 | 10 |
| Grana Padano | 21 | 10 + 10 + 10 = 30 |

Case-size rounding could explain over-booking. Under-booking may be the planner netting against in-transit stock by hand, in which case the booked quantity could be rational rather than erroneous. Whatever the reason, the derivation is undocumented and unauditable in the sheet.

### 5.8 No upper bound

`Order = Need − Available` has a floor at zero but no ceiling. Nothing prevents ordering more than can be consumed before the best-before date, and nothing flags existing over-cover (§5.2).

### 5.9 The bridge duration is unexplained, but the rate transition is consistent

`previous_week_Daily × 2.5` appears under a header that says `(3d)`, so the duration still needs an operational explanation. However, the prior analysis's second criticism was incorrect: `Stock KW34` consistently uses the **KW33** demand rate for the bridge. All 28 continuing stocked items reconcile within the sheet's displayed precision, including items whose rates changed (for example Mini Rösti, Schoko-Kaiserschmarrn, Vanilla-Sauce, Butteröl, and Speisesalz). In the target time-phased model the unexplained constant disappears: inventory is projected from the actual count timestamp using dated daily demand.

### 5.10 `Quantity required/week` uses 7 days, ordering uses 6

The Plan tab's weekly column is `day × 7`. It is **not used by the ordering path** (verified: `Need(6d)` derives from the daily rate × 6, not from this column). Impact on waste today: none. Risk: anyone using it for supplier forecasting or capacity planning overstates by 16.7%. Delete it rather than fix it.

### 5.11 `Demand/Silo Load` conflates three concepts

Demand forecast, physical silo capacity, and menu availability are one number. The values are round (15/20/25/30/35/45/70) and drift downward over time (Penne Arrabbiata: 70 in KW28 → 45 in KW29–31 → 30 from KW32). That could be manual reaction to sales, waste, capacity, or another operational constraint; the workbook does not prove which. *This is Phase 1's problem to solve* — but Phase 2 must keep demand and capacity as separate fields so the concepts can be distinguished.

The corrected Snowflake comparison strengthens the need to separate these
concepts. For 2026-08-17 through 2026-08-22, a zero-inclusive query using only
`CLOSED/SERVED` lines found 622 sold portions, 39 zero-sale dish-unit-days out
of 221, and a maximum of 15 for one dish-unit-day. The earlier provisional 626
total and the former three-location, 82.5-portions/day and 3.2×/9.5× claims are
superseded. The corrected per-unit output and unit/location map are still to be
captured; the Excel owner must still define the workbook field and its scope.

---

## 6. What works and must be preserved

- **The three-level BOM** (`Dish → Silo → Ingredient`) correctly models pre-mixes. Keep it.
- **Storage class as a first-class attribute** driving different ordering behaviour. Correct instinct.
- **Fresh handled on a delivery-to-delivery coverage basis** rather than weekly. Correct.
- **The bridge concept** — projecting stock forward to the start of the coverage window rather than netting against today's count. Correct in principle.
- **Grams as the internal unit, packs as the ordering unit.** Correct separation.
- **The red/green order flag.** A planner needs an at-a-glance exception view; keep that in the output.

---

## 7. Target logic

For item *i*, run date *t₀*:

**Step 1 — Gross requirement (time-phased, daily)**

```
demand_i(t) = Σ over dishes ( forecast_portions_d(t) × grams_d,i ) × yield_factor_i
```

For the first improved release, `yield_factor_i` is a simple configured value
with provenance, normally defaulting by storage class and optionally overridden
per item. The legacy profile alone keeps the exact spreadsheet `1.20`.
Empirical calibration from consumption/waste is a later enhancement and must not
delay the core Phase 2 flow.

**Step 2 — Coverage horizon**

```
lead_time_i = planning_lead_time_days_i
protection_end_i = next feasible replenishment arrival after the candidate arrival
```

For a simple weekly review cadence this is approximately
`lead_time_i + review_period_i`, adjusted only by configured delivery weekdays
when that rule is confirmed. These are ordinary Phase 2 config values, not an
external calendar integration. This is the fix for §5.1.

**Step 3 — Safety stock, simple first**

```
SS_i = configured_safety_days_i × average_daily_demand_i
```

The first release uses a transparent configured number by storage class/item.
Statistical safety stock, service-level optimization, and OOS correction are
explicitly deferred until the simple engine is validated and there is a
trustworthy calibration dataset.

**Step 4 — Netting**

```
gross_protection_need_i = Σ demand_i(t) from t₀ through protection_end_i
inventory_position_i = on_hand_i(t₀)
                     + Σ open_po_qty_i due by protection_end_i
raw_order_i = max(0, gross_protection_need_i + SS_i − inventory_position_i)
```

Do **not** subtract pre-arrival demand from `inventory_position_i` and then subtract the full protection-period demand again; that double-counts demand. After calculating the candidate order, project inventory day by day with dated demand and receipts. If projected stock falls below zero before the candidate order can arrive, emit an `UNAVOIDABLE_PRE_ARRIVAL_STOCKOUT` exception — increasing today's order cannot fix that interval.

Open POs are the fix for §5.2 and the dated generalisation of the spreadsheet bridge (§5.9). During file-only development an empty `open_pos.csv` is allowed, but every run must record `open_po_source = empty_placeholder`. That is acceptable for tests and scenarios, not for a trusted production result.

**Step 5 — Constraints, applied in order**

```
1. floor raw requirement at zero
2. calculate shelf-life and max-cover feasible caps at the receipt date
3. cap the unrounded candidate and record which cap bound
4. apply MOQ and case-size rounding to produce a purchasable candidate
5. re-check the rounded candidate against hard caps
```

MOQ or case rounding can push an order back above a shelf-life or max-cover cap.
Therefore hard caps must be revalidated **after** rounding. If a configured
constraint and a hard cap cannot both be satisfied, do not silently violate
either one: emit an `INFEASIBLE_ORDER_CONSTRAINTS` exception so the rule or
recommendation can be reviewed outside the calculation.

The first file-based implementation can approximate the shelf-life cap using configured days and projected demand. Once lot/expiry data is available, use remaining shelf life and FEFO inventory rather than assuming every on-hand unit is new. Every cap must state whether it used exact lot data or a policy approximation.

**Step 6 — Apply simple delivery rules where needed**

If the output must contain an order/delivery date, use configured lead time and
simple order/delivery weekdays to choose it. Do not build a generic calendar
service. Fresh items keep the existing per-slot coverage logic, but sum the
actual forecast days rather than multiplying an average day.

**Step 7 — Every number carries its derivation.** Persist the intermediate values for each line (gross requirement, yield factor and source, safety stock and source, inventory position, open-PO source, which cap bound, rounding delta, and placeholder flags). Without this the planner cannot sanity-check the machine and will go back to Excel.

**Step 8 — Menu transitions, after the core path.** The engine must always
aggregate only the forecast dishes active for each service date. More advanced
launch/discontinuation optimization, pipeline cancellation, and ramp policies
are later enhancements, not first-release prerequisites. For the first release,
validate forecast/menu coverage and visibly flag open POs arriving after the
last supplied demand date.

---

## 8. Data required now and later

| Data | Grain | Used for | File-only fallback | Phase 2 timing |
|---|---|---|---|---|
| Phase 1 forecast | dish × location × date | gross demand | hardcoded/CSV daily forecast derived from KW34 | required now |
| Recipes / BOM | dish → silo → item, grams | explosion | cleaned KW34 fixture with stable IDs | required now |
| Item/supplier master | item × supplier × location/effective date | units, lead time, delivery weekdays, shelf life, MOQ/case | versioned CSV with explicit defaults/placeholders | required now |
| Stock on hand | item × location × timestamp | netting | KW34 stock fixture plus an explicit assumed count timestamp | required now; timestamp needs owner confirmation |
| Open purchase orders | item × supplier × expected receipt × quantity | inventory position | manually maintained CSV or empty placeholder | not a code blocker; **blocks trusted production results if unknown** |
| Forward menu schedule | dish × location × service date | select the valid dish/BOM for every forecast date | hardcoded KW34 menu window | required for production; committed horizon needs owner confirmation |
| Dish sales | dish × location × timestamp | Phase 1, forecast error, yield denominator | omitted/empty adapter | later SQL calibration |
| OOS/unavailability | dish or silo × location × time window | later forecast/calibration analysis | omitted | later SQL calibration, not an engine-build blocker |
| Waste/disposal | item or dish × location × date | yield calibration, over-order detection | omitted; use labelled yield default | later SQL calibration, not an engine-build blocker |
| Goods receipts | item × supplier × receipt date × quantity | actual lead-time distribution | omitted; use configured lead time | later SQL calibration |
| Lot/expiry inventory | item × lot × location × expiry × quantity | FEFO and exact shelf-life cap | configured shelf-life approximation | later improvement; required for high-confidence chilled planning |

**Placeholder rule:** missing optional data never becomes a silent zero. Each adapter returns both values and provenance (`observed`, `manual`, `policy_default`, `empty_placeholder`, or `unavailable`). Validation decides whether that source is allowed for the selected run mode: fixtures and scenario runs may proceed with warnings; production runs fail when critical inputs such as current stock, pipeline visibility, pack size, or lead time are unknown.

**Later calibration note:** OOS, waste, consumption, and statistical forecast
error require their own definitions and backtests. They are not part of the
minimum Phase 2 implementation and must not delay KW33/KW34 parity, stock/PO
netting, or the basic configurable rules.

---

## 9. Proposed architecture

### 9.1 Principles

1. **The engine is pure.** Core calculation functions take validated typed/tabular inputs and return typed/tabular outputs, with no database or filesystem access. Concrete adapters may use dataframes, CSV, SQL, or API payloads. This makes the whole thing testable against the KW34 numbers as a golden fixture.
2. **All policy is explicit data, not code.** Start with versioned config files as a technical bootstrap and test interface; when operational persistence begins, store the same validated schemas in the database and manage them through the UI/API. Anything a non-technical admin might change is never a scattered constant or dependent on hand-editing repository files.
3. **Storage responsibilities are explicit.** Snowflake owns operational inputs
   and Phase 2 results. Supabase owns application-managed editable rules and
   their change history. A result run records the active config version/hash.
4. **Every run is reproducible.** Snapshot the input references and config
   version; the same values must reproduce the same output.
5. **The internal UI edits configuration only.** The CLI proves the engine; a
   later small API/React UI lets non-technical users maintain validated rules.
   It is not a supplier-ordering, approval, or dispatch workflow.
6. **Missing data is visible.** Placeholder/default provenance is carried into
   line-level audit output, and run mode determines whether it warns or blocks.

### 9.2 Components

There are two interfaces over time; CSV/YAML is not the end-user alternative to
Supabase.

**Bootstrap and engine validation (Milestones 1-2):**

```text
approved KW34 fixture + CSV master/input data + policy.yaml
                              ↓
                  CLI (technical interface)
                              ↓
                    application service
                              ↓
       validation → pure engine → CSV/JSON audit outputs
```

This path exists for golden tests, local development, deterministic batch runs, initial data import, and recovery. A developer or analyst may edit these files; a planner is not expected to maintain the production system this way.

**Internal production path (Milestones 3-5):**

```text
Snowflake forecast/menu/BOM/stock/PO ─┐
                                     ├─→ Python Phase 2 job
Supabase active planning rules ───────┘          │
                                                ▼
                                  Snowflake result tables

internal React UI ↔ thin Python API ↔ Supabase planning rules
```

Snowflake remains the warehouse for operational inputs and calculated outputs.
Supabase is the source of truth only for application-owned editable planning
rules. The UI validates and edits those rules; it does not approve proposals or
send orders. The CLI remains useful for tests, troubleshooting, and recovery.

### 9.3 Repository layout

The layout below remains the target. The implemented subset currently includes `pyproject.toml`, `src/supply_planning/{domain,validation,engine,application,adapters}`, the CLI, synthetic fixtures, and unit/integration-style tests. Config templates, the improved engine modules, web app, and Supabase migrations are not yet present.

```
supply-planning/
├── pyproject.toml
├── config/
│   ├── policy.yaml           # bootstrap/test policy; later maps to policy_versions
│   ├── items.csv             # bootstrap/test item master; not the final planner UI
│   ├── suppliers.csv         # bootstrap/test supplier master
│   └── bom.csv               # bootstrap/test dish → silo → item contract
├── src/supply_planning/
│   ├── adapters/             # Excel/CSV first; SQL and persistence later
│   ├── validation/           # schema, referential integrity, run-mode gates
│   ├── domain/               # typed models and units
│   ├── engine/               # pure calculation — no imports from adapters
│   │   ├── explode.py
│   │   ├── yield_factor.py
│   │   ├── safety_stock.py
│   │   ├── netting.py
│   │   ├── constraints.py
│   │   └── schedule.py
│   ├── application/          # run-planning use case and snapshots
│   ├── reporting/            # recommendations, exceptions, audit outputs
│   └── cli.py                # first runnable interface
├── tests/
│   ├── fixtures/kw34/        # approved/anonymized inputs + expected outputs
│   ├── unit/
│   └── integration/
├── apps/web/                 # internal config UI, added after config schemas stabilize
├── supabase/                 # editable planning-rule migrations only
└── README.md
```

The production workbook itself should not be committed by default. Extract the minimum approved KW34 fixture, preserve a checksum/source note, and confirm whether item/supplier details need anonymization.

### 9.4 Bootstrap configuration schemas

The files below define the first validated schemas and allow the engine to be built before database access and UI work. During Milestones 1-2 they are maintained by a developer or analyst and can be reviewed in Excel/Sheets. They are **not** the intended long-term editing workflow for non-technical planners. At the database milestone, the same fields migrate to versioned Supabase tables and are edited through validated UI/API forms.

**`config/items.csv`** — bootstrap per-item schema, one row per item. It round-trips cleanly, diffs readably in git, and can seed the future database.

| column | example | meaning |
|---|---|---|
| `item_id` | `PENNE_1000` | stable key. **Never** the display name |
| `item_name_de` | `Penne` | display only |
| `storage_class` | `TK` | TK / Kuehl / RT / Frisch |
| `pack_size_g` | `1000` | grams per purchasable pack |
| `supplier_id` | `SUP_003` | FK to suppliers.csv |
| `planning_lead_time_days` | `28` | total Phase 2 lead time; blank → category/supplier default |
| `moq_units` | `50` | minimum order quantity |
| `case_size_units` | `10` | rounding multiple |
| `shelf_life_days` | `180` | drives the shelf-life cap |
| `safety_days` | `3` | simple first-release safety setting |
| `max_cover_days` | `35` | hard ceiling on total cover |
| `yield_factor` | `1.10` | explicit configured value; legacy `1.20` remains separate |
| `value_source` | `manual` | provenance for defaults/overrides until source systems are connected |
| `active` | `TRUE` | soft delete |

**`config/policy.yaml`** — bootstrap global-policy schema, edited rarely during engine development and later represented as versioned database policy records.

```yaml
operating_days: [mon, tue, wed, thu, fri, sat]
review_period_days: 7
forecast_horizon_days: null   # required before production; must cover the calculation

defaults:
  safety_days: 2
  max_cover_days: 30
  yield_factor: 1.10

storage_class_defaults:
  Frisch: { max_cover_days: 2,  min_safety_days: 0 }
  Kuehl:  { max_cover_days: 14 }
  TK:     { max_cover_days: 45 }
  RT:     { max_cover_days: 60 }

rounding: ceil_to_case
run_modes:
  fixture: { allow_placeholders: true }
  scenario: { allow_placeholders: true }
  production: { allow_unknown_stock: false, allow_unknown_open_pos: false }
```

Two properties must survive when these schemas move behind the UI:

- **Validation with human-readable errors.** For example,
  `"item ITEM_43: shelf_life_days must be a positive whole number"`, not a
  stack trace.
- **Config is versioned.** Every run records the config hash it used, so an odd order six weeks ago can be explained.

### 9.5 UI and persistence boundary

The first deliverable is the Python calculation path. A later thin Python API
and React UI should let authorized internal users view/edit only the supported
Phase 2 rules: storage-category defaults, item/supplier overrides, lead time,
shelf life/max cover, MOQ/case, simple delivery rules, and safety/yield values.
It validates changes and shows the active version and basic change history.

The first UI does not include proposal approval, comments/assignment, supplier
send, ERP export, or manual replacement of Snowflake operational inputs.
Snowflake remains authoritative for forecasts, menu/BOM, stock, POs, and result
tables. Supabase contains only application-owned configuration, for example:

- `policy_versions` and one active version per environment;
- `storage_class_defaults`;
- `item_policy_overrides`;
- `supplier_item_rules`;
- `delivery_schedule_rules`;
- configuration change history.

Each Snowflake run records the active Supabase config version/hash. CSV/YAML
remain fixtures, controlled import/export, and recovery artifacts, not a second
production authority.

### 9.6 Run cadence

| Run | Frequency | Covers |
|---|---|---|
| Fresh | Daily, ahead of each delivery slot | `Frisch` only |
| Stocked | Weekly | TK / Kühl / RT |
| Long-lead alert | Weekly | Items where `lead_time > review_period` — these need re-checking every cycle, not just at reorder point |

### 9.7 Hosting

Start locally as a deterministic CLI with CSV/JSON outputs for engineering
validation. Then run the same application service as an internal scheduled job:
read accepted Snowflake sources plus the active Supabase config and write only
to the agreed Snowflake result schema. The React UI reads/writes Supabase config
through the API. Keep the CLI and files as controlled test/recovery tools.

---

## 10. Already-sent questions for the Excel owner

The exact manual actions, owners, fallbacks, and milestone due dates are tracked in `docs/plans/human_action_register.md`; these questions are promotion gates rather than a global development pause.

The original 13 substantive questions have already been sent to the person who
builds and uses the workbook. **No correction or replacement questionnaire is
needed.** Wait for the answers. The list below records the audience and intent
of each question; it is not new wording to resend:

1. **In-transit:** how the Excel owner personally tracks orders already placed and deliveries still expected.
2. **Lead times:** which practical lead-time assumptions they use when planning.
3. **Shelf life:** which shelf-life rule they apply and how it changes order quantities.
4. **`S/M/W/Fr`:** what the manual weekday quantities mean and why they differ from calculated quantities.
5. **`Demand/Silo Load`:** what this workbook input means and whether it applies per unit or across locations.
6. **Stock count:** when stock is counted and why the workbook uses the `2.5`-day bridge.
7. **Menu changes:** where the owner obtains menu plans and how they maintain launches, substitutions, and discontinuations.
8. **20% buffer:** the intended meaning of `1.20` and the operating judgment behind it.
9. **Master data:** which item, pack, storage, recipe, and supplier information the owner actually uses and maintains.
10. **Fresh products:** how fresh delivery windows and quantities are planned in practice.
11. **Weekly process:** the real planning cadence, urgent-order path, overrides, and approvals.
12. **Other data:** which other information or systems the owner knows about or consults while planning.
13. **Planner experience:** what explanations, controls, and workflow would make automated proposals usable and trustworthy.

Questions 1, 7, 9, and 12 may point towards other systems, but the Excel owner
is being asked only to explain their process and identify possible sources—not
to validate Snowflake tables, joins, lineage, grain, or completeness. The blank
Q14 in the sent document is harmless.

### Technical source status from Joel

Confirmed on 2026-08-25:

- `FACT_CG_DISH_DEMAND_FORECASTS`,
  `FACT_CG_INGREDIENT_DEMAND_FORECASTS`, `FACT_CG_PURCHASE_ORDERS`, and
  `BASE_INVENTORY` are abandoned models from the previous data team.
- The data-model repository is
  [`data-transformation`](https://github.com/circus-kitchens/data-transformation),
  and the abandoned models may be updated with the new logic after access is
  granted.
- Joel will create a stable Snowflake service account using RSA authentication,
  with credentials shared through 1Password. No credential material belongs in
  this repository.
- Purchase-order data is not currently ingested into Snowflake to Joel's
  knowledge. Deepali, Dor, and Ilona are the recommended Ops contacts for the
  current process/source, with Deepali likely knowing the details. Fivetran may
  be suitable once that source is identified.

The immediate PO action is therefore no longer a Snowflake search or another
question to Joel. Valentin should ask Ops for a walkthrough of the system,
sheet, or process used to track orders and expected deliveries, its owner,
history, and export/API capability. Once identified, Joel/data platform can
establish ingestion and a normalized source model. The service account solves
stable connectivity, not this missing input. Until that model passes grain,
unit, completeness, history, and freshness checks, production mode must fail
closed on open POs; manual/file PO inputs remain valid for fixture/scenario
development.

After GitHub access, inspect the abandoned definitions and decide explicitly
whether `data-transformation` owns normalized Snowflake inputs/outputs while
this repository keeps the pure planning engine, or whether another boundary is
intended. Do not duplicate the same planning logic in both repositories.

Before waste is shared or used for calibration, ask which field represents
physical disposal and how `WASTE_VALUE_EUR` is calculated. V4 now reproduces
3,750.3 kg and EUR 31,339 as field sums across six units, 63 ingredients, and
2026-06-01 through 2026-08-22—not one dish or one unit—but does not establish
that the quantities are physical disposal. V5, V11, V1, and corrected V2B are
now complete: the item master has usable pack/unit coverage with one blank ID,
the materialized menu has no forward-day coverage as of 2026-08-25, and the
corrected per-unit sales output reconciles to 622 portions across five
production/selling units. Corrected V3B is also complete and rules out the
tested direct `SILO_RESOURCE_ID ↔ RECIPE_SLOT_INSERTING_POSITION` join. Inspect
the data-model/upstream lineage for an authoritative physical-slot bridge after
repository access, then ask Joel or the robot/menu data owner only if it is not
documented there. No required Snowflake verification query remains.

Separate infrastructure decisions—not part of the already-shared 13—remain
for their later milestones: the Snowflake result schema/write pattern and
scheduling owner; whether Supabase is new or shared; and its owner, region,
credentials, backup, retention, and internal authentication approach.

---

## 11. Suggested delivery sequence

**Milestone 0 — Freeze the evidence.** Extract an approved KW34 fixture, map item aliases to stable IDs, document assumptions and source provenance, and encode the 27 filled orders, four unexplained blank gaps, two missing fresh rows, and exact legacy rounding as acceptance evidence.

**Milestone 1 — Reproduce the status quo.** Build the Python package and CLI,
file schemas, validation, BOM explosion, legacy `1.20` buffer, prior-week
bridge, exact rounding, stocked/fresh paths, recommendation/exception/audit
outputs, and real KW33/KW34 golden tests. Acceptance: all 27 filled KW34 order
cells match exactly and unexplained/missing rows are surfaced rather than
silently filled.

**Milestone 2 — Implement the improved engine with file inputs.** The first
tranche is complete: canonical daily file inputs, location/date menu checks,
dated inventory/open-PO netting, stockout and late-receipt exceptions, explicit
placeholder provenance, and deterministic audit output. Next add
lead-time/review protection, simple configured yield/safety, shelf-life/max-cover
where used, MOQ/case feasibility, simple delivery rules, and fresh
delivery-to-delivery coverage. Advanced statistical calibration and transition
optimization remain later work. Use manual/hardcoded files for missing data;
do not call placeholder output production-calibrated.

**Milestone 3 — Connect Snowflake and Supabase.** Implement accepted Snowflake
read adapters, agree and implement the internal Snowflake result writer, and
create Supabase only when approved for application-owned editable rules. Every
result run records the active config version/hash. Waste and OOS remain later
calibration sources.

**Milestone 4 — Validate with the Excel owner.** Run legacy and improved results
beside the manual process for representative weeks, explain differences, and
adjust source mappings or rules. Add calibration only where the evidence is
trustworthy and useful.

**Milestone 5 — Add the internal configuration UI and scheduled job.** Add a
thin Python API, React configuration forms, appropriate internal auth, versioned
Supabase rule editing, validation, and basic change history. Schedule the job to
read Snowflake plus the active config and write internal Snowflake results. Do
not add approval, dispatch, ERP export, comments, or assignment workflows.

**Live Phase 1 integration** is part of the scheduled-job milestone: swap the
manual/file forecast for the authoritative daily Snowflake contract without
changing the engine. Supplier/ERP integration is outside this roadmap.

**Keep first-release acceptance concrete:** exact legacy parity, complete
forecast/menu/BOM coverage, no silent missing inputs, deterministic results,
explainable recommendation differences, and planner time saved. Service-level,
waste, forecast-bias, and other calibrated KPIs are later work once their
definitions and observations are trustworthy.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| KW | Kalenderwoche, ISO week number |
| TK | Tiefkühl, frozen |
| Kühl | Refrigerated |
| RT | Room temperature |
| Frisch | Fresh produce |
| MHD | Mindesthaltbarkeitsdatum, best-before date |
| Silo | Physical hopper in the robot kitchen |
| Pre-Mix | Several ingredients pre-portioned into one bag, loaded as a single silo |
| BOM | Bill of materials — here, dish → silo → ingredient with grams per portion |
| MRP | Material requirements planning — the standard netting pattern this implements |
| MOQ | Minimum order quantity |
| OOS | Out of stock |
| Review period | Interval between planning runs |
| Days of cover | Stock on hand ÷ daily consumption rate |
