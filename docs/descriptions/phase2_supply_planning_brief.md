# Supply Planning Automation — Phase 2 Engineering Brief

**Scope:** replace the manual weekly Excel supply-planning process with a hosted Python service.
**Status:** discovery complete, build not started.
**Source analysed:** `Supply_Planning_Rewe.xlsx` (Google Drive), tabs `Plan KW34` / `Stock KW34`, cross-checked against KW19–KW35.
**Audience:** the engineer who will build and own the Phase 2 service.

---

## 1. What this document is for

This is the context pack for building Phase 2. It explains what the current manual process does, exactly how its arithmetic works, where it breaks, what the target logic should be, and a proposed architecture. Read sections 3–6 before writing any code — the current spreadsheet contains real domain logic that must be preserved, and several bugs that must not be.

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

Two tabs per week. Both are hand-copied forward from the previous week — there are no cross-tab formulas.

### 4.1 `Plan KWxx` — the bill of materials

Structure is three-level: `Dish → Silo → Ingredient`.

| Column | Meaning |
|---|---|
| `Dish` | Menu item |
| `Silo` | Hopper, or a named pre-mix bag |
| `Ingredients` | The actual purchasable item |
| `Storage - MHD` | Storage class (TK / Kühl / RT / Frisch). Despite the name, **no shelf-life data is recorded here** |
| `Demand/Silo Load` | Portions per day. This is the Phase 1 input |
| `Quantity required/dish` | Grams of this ingredient per portion |
| `Quantity required/day` | `Demand × grams per portion` |
| `Quantity required/week` | `day × 7` — **dead column, see §5.3** |
| `Unit Size` | Grams per purchasable pack |

Example, `Penne Arrabbiata mit Hähnchen`, KW34: demand 30 portions/day, Arrabbiata Sauce at 200 g/portion → 6,000 g/day.

### 4.2 `Stock KWxx` — netting and order proposal

Grouped by storage class. For ingredient *i*:

| Step | Column | Formula |
|---|---|---|
| 1 | *(implicit)* | `grams_per_day_i = Σ over dishes ( demand_d × grams_d,i )` |
| 2 | `Daily` | `grams_per_day_i / pack_size_i × 1.2` |
| 3 | `Need (6d)` | `ceil( Daily × 6 )` |
| 4 | `KW33 (3d)` | `Daily × 2.5` — consumption expected before the new week starts |
| 5 | `After` | `max( 0, Stock − bridge )` |
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

**Verification:** this reconstruction reproduces 24 of the 27 filled order cells in `Stock KW34` exactly. The other 3 differ by exactly 1 unit (rounding). The logic above is a faithful spec of the current process.

### 4.3 Fresh produce — separate path

No stock is held. Each delivery must last until the next one arrives:

| Delivery slot | Days covered | Multiplier |
|---|---|---|
| Saturday | Sat | 1 |
| Monday | Mon, Tue | 2 |
| Wednesday | Wed, Thu | 2 |
| Friday | Fri | 1 |

Order per slot = `Daily × 1.2 × multiplier`. Verified on `Stock KW35`: Paprika 5 mm at 2,340 g/day ÷ 1,500 g pack = 1.56 units/day → Sa 1.87, Mo 3.74, We 3.74, Fr 1.87.

The coverage arithmetic is correct. The weakness is that it multiplies an *average* day, so it assumes Monday and Tuesday have identical demand.

---

## 5. What is broken

Ranked by impact.

### 5.1 The coverage horizon is shorter than the lead time — CRITICAL

The model orders **6 days** of requirement. Actual lead time is reported as up to **4 weeks** (≈3 weeks production + 1 week transport).

| Item | Sheet orders (6 d) | Required to cover a 28-day lead time |
|---|---|---|
| Penne | 130 u | **609 u** |
| Udon Nudeln | 137 u | **640 u** |
| Grana Padano | 45 u | **212 u** |

This is not a tuning error, it is a structural one. You cannot order six days of stock for goods that arrive in twenty-eight. The requirement horizon must be `lead_time + review_period`, per item.

### 5.2 In-transit stock is invisible — CRITICAL, and a regression

`Stock KW29` and `Stock KW32` had a `Delivery` column and computed `Available = Stock + Delivery`. `Stock KW33` and `Stock KW34` **dropped it**. Combined with 5.1, the failure mode is predictable: the planner sees the same shortage in four consecutive weekly runs and re-orders it four times, then all four deliveries land together.

Evidence consistent with exactly this, from `Stock KW34` (days of cover = stock ÷ daily run rate):

| Item | Class | Stock | Daily | Days of cover |
|---|---|---|---|---|
| Trüffel Sauce | Kühl | 110 | 3.60 | **31** |
| Gelbe Thai Curry Sauce | Kühl | 80 | 2.34 | **34** |
| Teriyaki Sauce | Kühl | 25 | 0.94 | **27** |
| Schoko-Kaiserschmarrn | TK | 60 | 1.65 | 36 |
| Balsamico | RT | 26 | 0.65 | 40 |
| Speisesalz | RT | 59 | 0.22 | 268 |

Three chilled items sitting above 26 days of cover is a waste event waiting to be booked.

### 5.3 The flat ×1.2 buffer conflates two different things

One hardcoded factor is standing in for both deterministic loss (yield: spillage, portioning overage, prep waste, trim) and stochastic uncertainty (forecast error, lead-time variance). They behave differently — yield is multiplicative on demand, safety stock is additive and scales with `√(lead time)` — and they need different data to calibrate. A flat 20% simultaneously over-orders stable staples and under-protects volatile ones.

### 5.4 Missed orders

Four rows in `Stock KW34` have a computed gap and a blank order cell:

| Item | Need (6d) | After bridge | Should have ordered |
|---|---|---|---|
| Udon Nudeln | 138 | 33.9 | **105** |
| Roasted Sesame Sauce | 13 | 0.0 (already short mid-week) | **13** |
| Röstzwiebeln | 12 | 6.2 | **6** |
| Gewürze Quinoa (NEW) | 12 | — (row half-filled) | — |

124 units of unordered requirement in a single week, in a spreadsheet with no validation.

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

Case-size rounding could explain over-booking; it cannot explain under-booking. Whatever the reason, it is undocumented and unauditable.

### 5.8 No upper bound

`Order = Need − Available` has a floor at zero but no ceiling. Nothing prevents ordering more than can be consumed before the best-before date, and nothing flags existing over-cover (§5.2).

### 5.9 The bridge constant is wrong twice

`Daily × 2.5` under a header that says `(3d)`, and it applies the *new* week's run rate to the *current* week's menu. `Stock KW33` shows a handful of rows correctly using the old rate — the intent exists, the execution is inconsistent. In a time-phased model this constant disappears: you project inventory forward day by day from the actual count timestamp.

### 5.10 `Quantity required/week` uses 7 days, ordering uses 6

The Plan tab's weekly column is `day × 7`. It is **not used by the ordering path** (verified: `Need(6d)` derives from the daily rate × 6, not from this column). Impact on waste today: none. Risk: anyone using it for supplier forecasting or capacity planning overstates by 16.7%. Delete it rather than fix it.

### 5.11 `Demand/Silo Load` conflates three concepts

Demand forecast, physical silo capacity, and menu availability are one number. The values are suspiciously round (15/20/25/30/35/45/70) and drift downward over time (Penne Arrabbiata: 70 in KW28 → 45 in KW29–31 → 30 from KW32), which reads as manual reaction to waste rather than forecasting. *This is Phase 1's problem to solve* — but Phase 2 must keep demand and capacity as separate fields so the two can be told apart.

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

over a rolling 8–12 week window, clamped to a sane range (e.g. 1.00–1.50) and falling back to a config default when there is insufficient history.

**Step 2 — Coverage horizon**

```
H_i = lead_time_i + review_period_i
lead_time_i = production_lead_days_i + transport_lead_days_i
```

Per item, defaulted per supplier, admin-overridable. This is the fix for §5.1.

**Step 3 — Safety stock**

```
SS_i = max(
    min_safety_days_i × avg_daily_i,              # policy floor, admin-set
    z(service_level_i) × σ_i × √(H_i / review_period_i)
)
```

`σ_i` is the standard deviation of daily consumption, derived from **OOS-corrected** demand history (see §8 — a day where the dish sold out did not have demand of zero, and treating it as such biases the buffer downward exactly for the items that need it most). `service_level_i` comes from ABC/XYZ class in config.

This replaces the additive half of the old ×1.2 and directly answers the "different items need different buffers" requirement: an item feeding three high-variance dishes gets a bigger `σ`; an item with a long lead time gets a bigger `√H`; a chilled item gets the whole thing clipped by Step 5.

**Step 4 — Netting**

```
projected_available_i = on_hand_i(t₀)
                      − Σ demand_i(t) for t in (t₀, arrival_date_i)
                      + Σ open_po_qty_i arriving before end of horizon
raw_order_i = ( Σ demand_i(t) over H_i ) + SS_i − projected_available_i
```

The `open_po` term is the fix for §5.2 and the generalisation of the 2.5-day bridge (§5.9) — the bridge is just the first term of the projection, computed properly from the actual count date.

**Step 5 — Constraints, applied in order**

```
1. floor at zero
2. shelf-life cap:  order_i ≤ (shelf_life_days_i × avg_daily_i) − projected_available_i
3. max-cover cap:   order_i ≤ (max_cover_days_i × avg_daily_i) − projected_available_i
4. MOQ:             if 0 < order_i < moq_i  →  moq_i  (and flag)
5. case rounding:   order_i = ceil_to_multiple(order_i, case_size_i)
```

Steps 2 and 3 are the fix for §5.8 and the mechanism that turns the tool from *"never run out"* into *"never run out and don't throw food away"*. When a cap binds, it must appear in the exception report — a capped order is a signal that lead time and shelf life are incompatible for that item and someone needs to renegotiate with the supplier.

**Step 6 — Schedule to delivery slots**

Assign each order to the latest supplier order date that still lands before stock-out, given the supplier's delivery calendar. Output must be `(item, quantity, order_date, expected_delivery_date, supplier)` — not a bare quantity. Fresh items keep the existing per-slot coverage logic, but with `forecast(Mon) + forecast(Tue)` in place of `2 × average_day`.

**Step 7 — Every number carries its derivation.** Persist the intermediate values for each line (gross requirement, yield factor applied, safety stock, projected available, which cap bound, rounding delta). Without this the planner cannot sanity-check the machine and will go back to Excel.

---

## 8. Data required from SQL

| Data | Grain | Used for | Notes |
|---|---|---|---|
| Dish sales | dish × location × timestamp | demand history, σ, yield denominator | |
| Out-of-stock / unavailability events | dish or silo × location × time window | **uncensoring demand** | Critical. A sold-out dish shows zero sales but had non-zero demand. Table location is known to the business owner |
| Waste / disposal | item or dish × location × date | yield factor, over-order detection | Distinguish expiry waste from prep waste if the data allows — they have different fixes |
| Stock on hand | item × location × timestamp | netting | Need the count timestamp, not just the date |
| Open purchase orders | item × supplier × order date × expected delivery × qty | in-transit | **Currently missing entirely from the process** |
| Goods receipts | item × date × qty | lead-time actuals, σ of lead time | Lets you measure real lead time instead of trusting the config default |
| Recipes / BOM | dish → silo → item, grams | explosion | May live in the kitchen system rather than SQL — confirm |

**Uncensoring note:** the simplest defensible approach is to treat OOS intervals as censored observations and impute demand from comparable unaffected days (same dish, same weekday, adjacent weeks), rather than dropping them. Document whichever method is chosen — it materially moves both the forecast and the safety stock.

---

## 9. Proposed architecture

### 9.1 Principles

1. **The engine is pure.** Core calculation functions take dataframes in and return dataframes out, with no database or filesystem access. This makes the whole thing testable against the KW34 numbers as a golden fixture.
2. **All policy lives in config files, not code.** Anything a non-technical admin might change is a file, never a constant.
3. **Nothing is ordered without a human approving it.** At least until the numbers have been trusted for several cycles.
4. **Every run is reproducible.** Snapshot the inputs; a run can be re-executed months later and produce identical output.

### 9.2 Components

```
┌─ INPUTS ──────────────────────────────────────────────────┐
│  Phase 1 forecast     file today → table/API later        │
│  SQL (read-only)      stock, open POs, sales, waste, OOS  │
│  Master data          items.csv, bom.csv                  │
│  Policy config        policy.yaml, suppliers.csv          │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌─ VALIDATION ──────────────────────────────────────────────┐
│  schema + referential checks, human-readable errors       │
│  hard fail before any calculation runs                    │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌─ ENGINE (pure functions, no I/O) ─────────────────────────┐
│  explode_bom → apply_yield → project_inventory →          │
│  safety_stock → net_requirements → apply_constraints →    │
│  schedule_orders                                          │
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
│  human review → approve → send                            │
│  sinks: ERP (Xentral), email/CSV to supplier, Sheet       │
└───────────────────────────────────────────────────────────┘
```

### 9.3 Repository layout

```
supply-planning/
├── config/
│   ├── policy.yaml           # global policy, commented
│   ├── items.csv             # per-item overrides — the admin's main file
│   ├── suppliers.csv         # lead times, delivery calendars, MOQ defaults
│   └── bom.csv               # dish → silo → item → grams per portion
├── src/
│   ├── io/                   # SQL adapters, file loaders, output sinks
│   ├── validate/             # schema + referential integrity + friendly errors
│   ├── engine/               # pure calculation — no imports from io/
│   │   ├── explode.py
│   │   ├── yield_factor.py
│   │   ├── safety_stock.py
│   │   ├── netting.py
│   │   ├── constraints.py
│   │   └── schedule.py
│   ├── report/               # order proposal, exceptions, audit trail
│   └── run.py                # orchestration + CLI
├── tests/
│   ├── fixtures/kw34/        # the real KW34 inputs and expected outputs
│   └── ...
└── README.md
```

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
| `active` | `TRUE` | soft delete |

**`config/policy.yaml`** — global rules, edited rarely, commented for a non-technical reader.

```yaml
operating_days: [mon, tue, wed, thu, fri, sat]
review_period_days: 7

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
```

Three things that make this safe for a non-technical admin:

- **Validation with human-readable errors.** `"items.csv row 43: shelf_life_days (5) is shorter than lead_time (28) for Roasted Sesame Sauce — this item can never be ordered safely. Set a shorter lead time or flag for supplier renegotiation."` Not a stack trace.
- **Dry-run diff mode.** Change a config value, re-run, see exactly which order lines moved and by how much, before anything is sent.
- **Config is versioned.** Every run records the config hash it used, so an odd order six weeks ago can be explained.

### 9.5 Run cadence

| Run | Frequency | Covers |
|---|---|---|
| Fresh | Daily, ahead of each delivery slot | `Frisch` only |
| Stocked | Weekly | TK / Kühl / RT |
| Long-lead alert | Weekly | Items where `lead_time > review_period` — these need re-checking every cycle, not just at reorder point |

### 9.6 Hosting

Nothing heavy is needed. A scheduled container (Cloud Run job, ECS task, or equivalent) writing to a small Postgres for run history and audit trail. Read-only SQL credentials for the source system. Output to the ERP via API, plus a CSV/Sheet fallback so the process degrades gracefully rather than stopping.

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

---

## 11. Suggested delivery sequence

**Milestone 1 — Reproduce (1–2 weeks).** Port the existing logic exactly as specified in §4, reading from config files with a manually maintained forecast input. Golden test: reproduce `Stock KW34` to within the known ±1 rounding. This proves the BOM and master data are clean before any behaviour changes. Ship nothing to suppliers yet.

**Milestone 2 — Fix the structural bugs (2–3 weeks).** Add lead-time-aware horizons (§5.1), in-transit netting (§5.2), shelf-life and max-cover caps (§5.8), MOQ and case rounding, and the exception report. Run in parallel with the manual process for 3–4 weeks and diff every line. Expect large deviations on long-lead items — that is the bug being fixed, not a regression.

**Milestone 3 — Calibrate the buffer (2–3 weeks, needs SQL).** Replace the flat ×1.2 with a computed yield factor and a variance-based safety stock, using OOS-corrected demand history. Backtest against the last 12 weeks: what would this policy have ordered, and what would waste and stockouts have been?

**Milestone 4 — Automate dispatch.** Approval gate, ERP integration, scheduled runs, monitoring.

**Milestone 5 — Plug in Phase 1.** Swap the manual forecast file for the model output. No engine changes if the interface in §3 was respected.

**Success metrics to instrument from Milestone 1**, so improvement is measurable rather than asserted: service level (portions available ÷ portions demanded), waste as a percentage of goods received split by storage class, average days of cover by class, forecast bias, and planner time per week.

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
