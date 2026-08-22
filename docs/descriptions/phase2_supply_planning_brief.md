# Supply Planning Automation — Phase 2 Engineering Brief

**Scope:** replace the manual weekly Excel supply-planning process with a hosted Python service.
**Status:** discovery and KW34 value-level validation complete; build not started.
**Source analysed:** [`Supply_Planning_Rewe.xlsx`](https://docs.google.com/spreadsheets/d/1W0fwiO_mf7pQ6G0Oqmp6QE92MCljrXQ-/edit?gid=844782362#gid=844782362) (Excel workbook stored in Google Drive), tabs `Plan KW34` / `Stock KW34`, cross-checked against adjacent weeks. Revalidated read-only on 2026-08-22 against the workbook modified on 2026-08-21.
**Audience:** the engineer who will build and own the Phase 2 service.

---

## 1. What this document is for

This is the context pack for building Phase 2. It explains what the current manual process does, exactly how its arithmetic works, where it breaks, what the target logic should be, and a proposed architecture. Read sections 3–6 before writing any code — the current spreadsheet contains real domain logic that must be preserved, and several bugs that must not be.

### Validation conclusion

The overall direction is sound: reproduce the manual process first, isolate a pure engine behind file adapters, then introduce improved planning, real data, shadow testing, and a UI. The original brief was **not implementation-ready** in three places that are corrected here: it mischaracterised the KW34 bridge as using the new week's demand, its target netting equation double-counted pre-arrival demand, and its safety-stock equation was ambiguous about the grain of `σ`.

Confidence is **high** for the displayed KW34 legacy arithmetic and **medium** for the operational meaning of blank/booking cells, lead times, shelf life, and pipeline handling. The source is an Office workbook in Drive; the connector exposed displayed cell values but not a formula AST. The reconstruction was therefore independently reconciled at value level. Preserve this caveat until the raw workbook formulas or an owner walkthrough confirm the exact cell implementation.

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

**Phase 1 does not exist yet.** It is currently a human typing one integer per dish per week into a column called `Demand/Silo Load`. That single number is the entire interface between the two phases. Everything downstream of it is deterministic arithmetic.

**This project is Phase 2 only.** Phase 1 will be built afterwards. Phase 2 must therefore be designed so the forecast is a *pluggable input*: today a manually maintained file, later a table or API call, with no change to the engine.

### Interface contract (design to this now)

Phase 2 consumes a demand signal shaped like:

| field | type | notes |
|---|---|---|
| `location_id` | string | single site today, must scale to N |
| `dish_id` | string | stable key, not display name |
| `date` | date | **daily granularity, not weekly** |
| `forecast_portions` | float | expected portions sold |
| `forecast_sigma` | float | optional; std. deviation of the forecast error. Feeds safety stock. Null → fall back to config default |

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

`yield_factor_i` replaces the multiplicative half of the old ×1.2. Derive it empirically:

```
yield_factor_i = rolling_mean( actual_consumption_i / theoretical_consumption_i )
theoretical_consumption_i = Σ ( dishes_sold_d × grams_d,i )
```

over a rolling 8–12 week window, clamped to a sane range (e.g. 1.00–1.50) and falling back to a config default when there is insufficient history. Waste and actual-consumption data are **not blockers for building the engine**: the offline improved-policy fixture uses a clearly labelled default and emits `yield_factor_source = policy_default`. The legacy compatibility profile keeps the sheet's exact `1.20` multiplier. Neither value may be presented as empirically calibrated until real data is connected.

**Step 2 — Coverage horizon**

```
lead_time_i = production_lead_days_i + transport_lead_days_i
protection_end_i = next feasible replenishment arrival after the candidate arrival
```

For a simple weekly review calendar this is approximately `lead_time_i + review_period_i`, adjusted to actual supplier order and delivery days. It is item/supplier-specific, defaulted per supplier, and admin-overridable. This is the fix for §5.1.

**Step 3 — Safety stock**

```
policy_floor_i = min_safety_days_i × avg_daily_i
statistical_ss_i = z(service_level_i) × √(Σ forecast_sigma_i(t)²)
SS_i = max(policy_floor_i, statistical_ss_i)
```

The sum runs over the protection period and assumes `forecast_sigma_i(t)` is a **daily** standard deviation with independent daily errors. If Phase 1 supplies a different grain or correlated errors, the aggregation must be changed explicitly rather than divided by the review period. Ingredient uncertainty is derived from the dish-level forecast errors and BOM; correlation between dishes needs a documented assumption or conservative fallback. `service_level_i` comes from policy or a later ABC/XYZ classification.

Until forecast-error, OOS, and consumption history exist, `statistical_ss_i` is unavailable and the engine uses the policy floor (or another explicit class/item placeholder), records `safety_stock_source = policy_placeholder`, and raises a non-blocking data-quality warning. OOS-corrected history is required for **calibration and production confidence**, not for implementing or exercising the planning path. A sold-out day must not later be treated as zero demand because that would bias safety stock downward.

**Step 4 — Netting**

```
gross_protection_need_i = Σ demand_i(t) from t₀ through protection_end_i
inventory_position_i = on_hand_i(t₀)
                     + Σ open_po_qty_i due by protection_end_i
                     − backorders_or_committed_qty_i
raw_order_i = max(0, gross_protection_need_i + SS_i − inventory_position_i)
```

Do **not** subtract pre-arrival demand from `inventory_position_i` and then subtract the full protection-period demand again; that double-counts demand. After calculating the candidate order, project inventory day by day with dated demand and receipts. If projected stock falls below zero before the candidate order can arrive, emit an `UNAVOIDABLE_PRE_ARRIVAL_STOCKOUT` exception — increasing today's order cannot fix that interval.

Open POs are the fix for §5.2 and the dated generalisation of the spreadsheet bridge (§5.9). During file-only development an empty `open_pos.csv` is allowed, but every run must record `open_po_source = empty_placeholder`. That is acceptable for tests and scenarios, not for approving a real operational order.

**Step 5 — Constraints, applied in order**

```
1. floor raw requirement at zero
2. calculate shelf-life and max-cover feasible caps at the receipt date
3. cap the unrounded candidate and record which cap bound
4. apply MOQ and case-size rounding to produce a purchasable candidate
5. re-check the rounded candidate against hard caps
```

MOQ or case rounding can push an order back above a shelf-life or max-cover cap. Therefore hard caps must be revalidated **after** rounding. If supplier constraints and a hard cap cannot both be satisfied, do not silently violate either one: emit an `INFEASIBLE_ORDER_CONSTRAINTS` exception for manual resolution (split delivery, override, different pack, supplier negotiation, or no order).

The first file-based implementation can approximate the shelf-life cap using configured days and projected demand. Once lot/expiry data is available, use remaining shelf life and FEFO inventory rather than assuming every on-hand unit is new. Every cap must state whether it used exact lot data or a policy approximation.

**Step 6 — Schedule to delivery slots**

Assign each order to the latest supplier order date that still lands before stock-out, given the supplier's delivery calendar. Output must be `(item, quantity, order_date, expected_delivery_date, supplier)` — not a bare quantity. Fresh items keep the existing per-slot coverage logic, but with `forecast(Mon) + forecast(Tue)` in place of `2 × average_day`.

**Step 7 — Every number carries its derivation.** Persist the intermediate values for each line (gross requirement, yield factor and source, safety stock and source, inventory position, open-PO source, which cap bound, rounding delta, and placeholder flags). Without this the planner cannot sanity-check the machine and will go back to Excel.

**Step 8 — Menu transitions.** Steady-state pipeline logic fails at both ends of a dish's life. On launch, the pipeline is empty and the first order must cover lead time *plus* the ramp, not just one review period. On discontinuation, orders already placed keep arriving for `lead_time` days after the dish leaves the menu — so the engine needs the forward menu calendar and must stop ordering the retiring dish's incremental ingredient demand early enough, and flag any open PO that will land after final demand. An ingredient used by other active dishes must continue to be planned from their remaining aggregate demand. This requires the menu to be fixed further ahead than the longest lead time (see §10, question 9); if it is not, that is a business-process constraint, not something the engine can solve.

---

## 8. Data required now and later

| Data | Grain | Used for | File-only fallback | Operational status |
|---|---|---|---|---|
| Phase 1 forecast | dish × location × date | gross demand | hardcoded/CSV daily forecast derived from KW34 | required now |
| Recipes / BOM | dish → silo → item, grams | explosion | cleaned KW34 fixture with stable IDs | required now |
| Item/supplier master | item × supplier × location/effective date | units, lead time, calendars, shelf life, MOQ/case | versioned CSV with explicit defaults/placeholders | required now |
| Stock on hand | item × location × timestamp | netting | KW34 stock fixture plus an explicit assumed count timestamp | required now; timestamp needs owner confirmation |
| Open purchase orders | item × supplier × expected receipt × quantity | inventory position | manually maintained CSV or empty placeholder | not a code blocker; **blocks operational approval if unknown** |
| Forward menu calendar | dish × location × service date | launches/discontinuations | hardcoded KW34 menu window | required for transition scenarios; committed horizon needs owner confirmation |
| Dish sales | dish × location × timestamp | Phase 1, forecast error, yield denominator | omitted/empty adapter | later SQL calibration |
| OOS/unavailability | dish or silo × location × time window | uncensoring demand | omitted; mark sigma uncalibrated | later SQL calibration, not an engine-build blocker |
| Waste/disposal | item or dish × location × date | yield calibration, over-order detection | omitted; use labelled yield default | later SQL calibration, not an engine-build blocker |
| Goods receipts | item × supplier × receipt date × quantity | actual lead-time distribution | omitted; use configured lead time | later SQL calibration |
| Lot/expiry inventory | item × lot × location × expiry × quantity | FEFO and exact shelf-life cap | configured shelf-life approximation | later improvement; required for high-confidence chilled planning |

**Placeholder rule:** missing optional data never becomes a silent zero. Each adapter returns both values and provenance (`observed`, `manual`, `policy_default`, `empty_placeholder`, or `unavailable`). Validation decides whether that source is allowed for the selected run mode: fixtures and scenario runs may proceed with warnings; operational approval hard-fails when safety-critical inputs such as current stock, pipeline visibility, pack size, or lead time are unknown.

**Uncensoring note:** when OOS data becomes available, treat OOS intervals as censored observations and impute demand from comparable unaffected days (same dish, same weekday, adjacent weeks), rather than dropping them. Document and backtest the chosen method — it materially moves both the forecast and the safety stock.

---

## 9. Proposed architecture

### 9.1 Principles

1. **The engine is pure.** Core calculation functions take validated typed/tabular inputs and return typed/tabular outputs, with no database or filesystem access. Concrete adapters may use dataframes, CSV, SQL, or API payloads. This makes the whole thing testable against the KW34 numbers as a golden fixture.
2. **All policy is explicit data, not code.** Start with versioned config files; when the UI exists, persist the same validated schemas in the database. Anything a non-technical admin might change is never a scattered constant.
3. **Nothing is ordered without a human approving it.** At least until the numbers have been trusted for several cycles.
4. **Every run is reproducible.** Snapshot the inputs; a run can be re-executed months later and produce identical output.
5. **CLI and UI call the same application service.** The script is the first interface, not a throwaway implementation. A later API wraps the same validated run use case and pure engine.
6. **Missing data is visible.** Placeholder/default provenance is carried into line-level audit output, and run mode determines whether it warns or blocks.

### 9.2 Components

```
┌─ INPUT ADAPTERS ──────────────────────────────────────────┐
│  File first           KW34 fixture, CSV/config            │
│  SQL later            stock, POs, sales, waste, OOS       │
│  Phase 1              hardcoded/CSV now → table/API later │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌─ VALIDATION ──────────────────────────────────────────────┐
│  schema, units, IDs, joins, provenance, run-mode gates     │
│  human-readable errors and warnings                       │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌─ ENGINE (pure functions, no I/O) ─────────────────────────┐
│  explode_bom → apply_yield → project_inventory →          │
│  safety_stock → net_requirements → apply_constraints →    │
│  schedule_orders                                          │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌─ APPLICATION SERVICE ─────────────────────────────────────┐
│  snapshot inputs → validate → run → persist/export        │
│  one use case called by CLI now and API later             │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌─ OUTPUTS ─────────────────────────────────────────────────┐
│  order proposal (per supplier, per order date)            │
│  exception report (capped / MOQ-inflated / unavoidable    │
│    stockout / config gaps)                                │
│  audit trail (every intermediate value, persisted)        │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌─ APPROVAL & DISPATCH ─────────────────────────────────────┐
│  CLI export first → React/Tailwind review UI later        │
│  approve → export; supplier/ERP dispatch remains gated    │
└───────────────────────────────────────────────────────────┘
```

### 9.3 Repository layout

```
supply-planning/
├── pyproject.toml
├── config/
│   ├── policy.yaml           # global policy, commented
│   ├── items.csv             # per-item overrides — the admin's main file
│   ├── suppliers.csv         # lead times, delivery calendars, MOQ defaults
│   └── bom.csv               # dish → silo → item → grams per portion
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
│   ├── reporting/            # proposal, exceptions, audit exports
│   └── cli.py                # first runnable interface
├── tests/
│   ├── fixtures/kw34/        # approved/anonymized inputs + expected outputs
│   ├── unit/
│   └── integration/
├── apps/web/                 # React + Tailwind, added after engine/API proof
├── supabase/                 # migrations added only when persistence starts
└── README.md
```

The production workbook itself should not be committed by default. Extract the minimum approved KW34 fixture, preserve a checksum/source note, and confirm whether item/supplier details need anonymization.

### 9.4 Config design — the part the admin touches

Two files, deliberately split by who edits them and how often.

**`config/items.csv`** — per-item, edited in Excel or Sheets, one row per item. Round-trips cleanly, diffs readably in git.

| column | example | meaning |
|---|---|---|
| `item_id` | `PENNE_1000` | stable key. **Never** the display name |
| `item_name_de` | `Penne` | display only |
| `storage_class` | `TK` | TK / Kuehl / RT / Frisch |
| `pack_size_g` | `1000` | grams per purchasable pack |
| `supplier_id` | `SUP_003` | FK to suppliers.csv |
| `production_lead_days` | `21` | blank → supplier default |
| `transport_lead_days` | `7` | blank → supplier default |
| `moq_units` | `50` | minimum order quantity |
| `case_size_units` | `10` | rounding multiple |
| `shelf_life_days` | `180` | drives the shelf-life cap |
| `min_safety_days` | `3` | policy floor on safety stock |
| `max_cover_days` | `35` | hard ceiling on total cover |
| `service_level` | `0.95` | blank → class default from policy.yaml |
| `yield_factor_override` | *(blank)* | blank → computed from history |
| `last_order_date_offset_days` | `28` | how far before a dish's final service day to stop ordering this item |
| `pipeline_cancellable` | `FALSE` | whether an open PO for this item can be cancelled or pulled |
| `value_source` | `manual` | provenance for defaults/overrides until source systems are connected |
| `active` | `TRUE` | soft delete |

**`config/policy.yaml`** — global rules, edited rarely, commented for a non-technical reader.

```yaml
operating_days: [mon, tue, wed, thu, fri, sat]
review_period_days: 7
menu_horizon_weeks: null      # required; validator checks it covers the longest lead time

defaults:
  service_level: 0.95
  min_safety_days: 2
  max_cover_days: 30
  yield_factor: 1.10          # used only where history is insufficient
  yield_factor_bounds: [1.00, 1.50]

storage_class_defaults:
  Frisch: { max_cover_days: 2,  min_safety_days: 0 }
  Kuehl:  { max_cover_days: 14 }
  TK:     { max_cover_days: 45 }
  RT:     { max_cover_days: 60 }

history:
  lookback_weeks: 12
  min_observations: 20        # below this, fall back to defaults
  uncensor_oos: true

rounding: ceil_to_case
run_modes:
  fixture: { allow_placeholders: true }
  scenario: { allow_placeholders: true }
  operational: { allow_unknown_stock: false, allow_unknown_open_pos: false }
```

Three things that make this safe for a non-technical admin:

- **Validation with human-readable errors.** `"items.csv row 43: shelf_life_days (5) is shorter than lead_time (28) for Roasted Sesame Sauce — this item can never be ordered safely. Set a shorter lead time or flag for supplier renegotiation."` Not a stack trace.
- **Dry-run diff mode.** Change a config value, re-run, see exactly which order lines moved and by how much, before anything is sent.
- **Config is versioned.** Every run records the config hash it used, so an odd order six weeks ago can be explained.

### 9.5 UI and persistence boundary

The first deliverable is a Python CLI/script. Design the application service now so a later FastAPI endpoint can call the same run path without moving business logic. The React + Tailwind UI should provide:

- **Run planning:** select location/date/policy, load the Phase 1 forecast, validate inputs, preview warnings, and run a dry proposal.
- **Proposal review:** filter by supplier/date/storage class, see derivations and placeholder badges, resolve exceptions, approve, and export. No direct supplier send in the first UI.
- **Master data:** manage item/SKU pack size, storage class, shelf life, supplier, production/transport lead time, delivery calendar, MOQ/case, safety policy, and value provenance. Support defaults plus explicit item overrides.
- **Pipeline and stock:** view or manually maintain open POs and timestamped inventory until integrations replace manual entry.
- **Run history:** immutable input/config snapshots, result comparison, approval status, and audit trail.

CSV/YAML is sufficient while only the script edits configuration. Once multiple users edit config or run history must be durable, Supabase Postgres is appropriate. Keep file and database adapters behind the same schemas. A minimal persistent model is:

- master/config: `locations`, `items`, `suppliers`, `supplier_items`, `bom_lines`, `policy_versions`;
- operational inputs: `menu_calendar`, `forecast_daily`, `inventory_snapshots`, `purchase_orders`;
- audit/output: `planning_runs`, `planning_run_inputs`, `planning_lines`, `order_proposals`, `exceptions`, `approvals`.

Create the Supabase project and migrations only at the database milestone; access, project ownership, region, auth policy, and environment variables are explicit human-input blockers in the backlog.

### 9.6 Run cadence

| Run | Frequency | Covers |
|---|---|---|
| Fresh | Daily, ahead of each delivery slot | `Frisch` only |
| Stocked | Weekly | TK / Kühl / RT |
| Long-lead alert | Weekly | Items where `lead_time > review_period` — these need re-checking every cycle, not just at reorder point |

### 9.7 Hosting

Start locally as a deterministic CLI with CSV/JSON outputs. After database integration, expose the same application service through FastAPI and run it in a scheduled container or job. The React/Tailwind UI reads through the API; Supabase can provide Postgres, auth, and storage. Read-only SQL credentials are used for source systems. Keep CSV export as a fallback so planning can continue during UI or integration outages.

---

## 10. Open questions for the business

1. **Is `Demand/Silo Load` portions sold per day, or silo fill level per day?** The arithmetic works either way, but it determines whether Phase 1 forecasts demand or forecasts refills. Blocking for the Phase 1 interface.
2. **When exactly is the stock count taken, and by whom?** Needed to replace the hardcoded 2.5-day bridge with a real timestamp.
3. **Why 2.5 rather than 3?** Half-day Saturday, or a typo that has been copied forward for months?
4. **Is the 4-week lead time uniform, or per supplier / per item?** Config assumes the latter; needs real values to seed `items.csv`.
5. **Where do open purchase orders live?** If nowhere queryable, that is a prerequisite, not a nice-to-have.
6. **Do the `S/M/W/Fr` numbers reflect supplier constraints, partial orders, or errors?** Determines whether case-size and MOQ config can reproduce them.
7. **Is silo capacity a real binding constraint?** If yes it belongs in `items.csv` as a per-dish `max_silo_load` and gets applied as an explicit, visible cap.
8. **Which shelf life matters — sealed or opened?** For chilled sauces this changes the cap materially.
9. **How many weeks ahead is the menu fixed and committed?** The committed horizon must extend beyond the longest item lead time so launches and discontinuations can be planned safely. If it does not, the process must change or the engine must raise a blocking exception.
10. **What is the canonical purchasable SKU and pack size for every ingredient?** KW34 has conflicting pack sizes for Schnittlauch and Creme Fraiche, so names alone cannot define an order line.
11. **Are `Paprika - big` and `Mischsalat` intentionally handled outside `Stock KW34`?** They are present in the plan but missing from the order tab.
12. **What supplier order calendars, cut-off times, MOQ, case-size, and split-delivery rules apply?** Lead days alone are not enough to schedule a dated order.
13. **Which system will provide current stock, open POs, receipts, sales, waste, OOS, BOM, and menu data, and what read-only SQL/API access is available?** Needed before the integration milestone, not before the file-based engine.
14. **Who may edit policy, run planning, approve a proposal, and export/dispatch it?** Needed before Supabase auth/RLS and the UI approval workflow are designed.
15. **Should the available Supabase project be new or shared, and who owns its region, billing, credentials, backup, and retention policy?** Blocking only when durable persistence starts.

---

## 11. Suggested delivery sequence

**Milestone 0 — Freeze the evidence.** Extract an approved KW34 fixture, map item aliases to stable IDs, document assumptions and source provenance, and encode the 27 filled orders, four unexplained blank gaps, two missing fresh rows, and exact legacy rounding as acceptance evidence.

**Milestone 1 — Reproduce the status quo.** Build the Python package and CLI, file schemas, validation, BOM explosion, legacy `1.20` buffer, prior-week bridge, exact rounding, stocked/fresh paths, proposal/exception/audit exports, and golden tests. Acceptance: all 27 filled KW34 order cells match exactly and unexplained/missing rows are surfaced rather than silently filled. Ship nothing to suppliers.

**Milestone 2 — Implement the improved engine with file inputs.** Add daily time-phased demand, lead-time/review protection, open-PO netting, pre-arrival stockout detection, shelf-life/max-cover constraints, MOQ/case feasibility, delivery scheduling, menu transitions, and explicit placeholder provenance. Use manual/hardcoded files for missing data; do not call placeholder output production-calibrated.

**Milestone 3 — Connect SQL and durable storage.** Confirm source schemas and credentials, implement read-only adapters, create Supabase only if approved, persist versioned config/run snapshots, and replace placeholders source by source. Waste and OOS can arrive after stock/open-PO integration because they calibrate rather than enable core netting.

**Milestone 4 — Backtest and shadow-run with real data.** Backtest the improved policy, compare legacy versus improved outputs, calibrate yield/safety stock when data permits, and run beside the planner for multiple cycles. Define signed acceptance thresholds before any operational approval/export.

**Milestone 5 — Build the user interface.** Add FastAPI, React, Tailwind, Supabase auth/RLS if used, configuration forms, proposal review, exceptions, history, approval, and CSV export. Keep supplier dispatch disabled.

**Milestone 6 — Integrate Phase 1 and operational outputs.** Swap the hardcoded forecast for the Phase 1 daily contract, add scheduling/monitoring, then separately approve any ERP/supplier dispatch integration. No engine changes should be required if the interface in §3 is respected.

**Define the success-metric fields from Milestone 1**, so improvement is measurable rather than asserted: service level (portions available ÷ portions demanded), waste as a percentage of goods received split by storage class, average days of cover by class, forecast bias, and planner time per week. Until the underlying observations exist, outputs must mark those metrics `unavailable` rather than inventing values; populate and trend them once the real inputs are connected.

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
