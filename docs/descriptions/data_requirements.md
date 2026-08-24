# Phase 2 — Data Requirements and Sourcing

**Sources available:** Snowflake via Google SSO and Lightdash. Connection identifiers belong in local environment variables, not this repository; see `.env.example`.
**Table names below** come from Joel Aftreth's Slack message of 20 Aug 2026. Schemas are not confirmed — discover them before hardcoding anything (see `explore_snowflake.py`).

**Important access caveat from Joel:** Lightdash currently exposes only the high-level models that business users need. `base_*` and `int_*` models are **not** available there — those require Snowflake, and full developer-level access to base/intermediate models needs a separate permission set that Joel still has to create. Since several things we need sit in `base_*`, expect to ask for that.

---

## 1. What the current Excel uses

Everything in the sheet is either the manual demand number or master data. Almost none of it comes from a database today.

| What the sheet uses | Where it comes from now | Where it should come from |
|---|---|---|
| `Demand/Silo Load` — portions per dish per day | Typed by hand | Phase 1 model, trained on `fact_cg_sales_daily` |
| Recipes: dish → silo → ingredient, grams per portion | Hardcoded in each weekly tab | Master data table — **source unknown, see gap G1** |
| Pack size in grams | Hardcoded per tab, drifts between tabs | Item master — likely ERP (Xentral), see G2 |
| Storage class (TK / Kühl / RT / Frisch) | Hardcoded per tab | Item master |
| Stock on hand | Typed in from a manual count | `base_stock_updates` — needs confirming |
| The ×1.2 buffer | Hardcoded constant | Computed: yield factor + safety stock |
| Order quantities | Calculated in-sheet | Output of the new engine |

---

## 2. What Phase 2 needs, mapped to available tables

| # | Data need | Used for | Candidate table | Status |
|---|---|---|---|---|
| D1 | Dishes sold per unit × day × dish (PLU) | Demand history, variance for safety stock, validating the manual demand number | `fact_cg_sales_daily` (also `fact_cg_sales`, `fact_cg_sales_hourly`) | ✅ available |
| D2 | Dishes actually cooked, incl. unsold | Dish-level waste = cooked − sold; distinguishes production loss from demand | `fact_cg_dish_production` | ✅ available |
| D3 | Ingredient leftover per day | Yield factor, over-ordering detection | `fact_cg_waste` | ✅ available |
| D4 | Out-of-stock / unmet demand per ingredient | **Uncensoring demand.** A dish that sold out did not have demand of zero | `fact_cg_oos_ingredient` | ✅ available |
| D5 | Ingredient usage / stock movements per day | Actual consumption, current stock on hand | `base_stock_updates` | ⚠️ Snowflake only, not in Lightdash |
| D6 | Which dishes are deployed per unit per day | Menu calendar — needed for pipeline wind-down and new-dish ramp | `int_unit_day_menu`, `base_ucs_menu` | ⚠️ Snowflake only |
| D7 | Ingredient loaded per day | Joel: *food loaded − leftover = used per day*. No dedicated model yet; derivable from `base_stock_updates` | — | ⚠️ needs building |
| D8 | Recipes / BOM: dish → ingredient, grams | The entire explosion step | **Unknown** | ❌ gap G1 |
| D9 | Item master: pack size, storage class, shelf life, supplier | Unit conversion, shelf-life cap | **Unknown** — probably Xentral ERP | ❌ gap G2 |
| D10 | Supplier terms: lead time, MOQ, case size, delivery calendar | Coverage horizon, lot sizing | **Unknown** — probably Xentral or nowhere | ❌ gap G3 |
| D11 | Open purchase orders / in-transit | **The single highest-value missing input** | **Unknown** | ❌ gap G4 |
| D12 | Goods receipts | Measuring real lead time vs. promised | **Unknown** — probably Xentral | ❌ gap G5 |

---

## 3. The gaps, in priority order

**G4 — Open purchase orders (blocks shadow/operational use, not engine development).** Without this the engine repeats the spreadsheet's worst bug: re-ordering the same shortage every week for the length of the lead time. Joel's list contains nothing resembling a PO table. Ask him directly whether purchasing data lands in Snowflake at all, and ask the planner where orders are recorded. If the answer is "in email", creating an auditable PO source is a prerequisite for operational use, while fixture/scenario development continues with explicit placeholders.

**G1 — Recipes / BOM (blocks real-data coverage, not synthetic development).** Everything starts with grams per portion. The spreadsheet is currently the only machine-readable copy I have seen. It may exist in the kitchen system (the `ucs` prefix in `base_ucs_menu` suggests a unit control system) — worth checking whether recipes live there. Fallback: extract the BOM from the KW34 Plan tab once, clean it, and hold an approved/anonymized version as master data. Synthetic BOM fixtures already allow the engine path to be developed and tested.

**G2 / G3 / G5 — Item and supplier master data.** Pack size, shelf life, lead time, MOQ, case size. Xentral ERP is in your connector list and is the obvious candidate. If it is not there or not complete, this becomes the admin-editable `items.csv` from the architecture — which is where it probably belongs anyway, since a planner can maintain it and a data pipeline cannot invent it.

**D7 — "loaded per day" model.** Joel already flagged he would probably need to add this. Worth requesting explicitly now rather than deriving it yourself from `base_stock_updates`, so the definition is owned by the data team and not reimplemented in your script.

---

## 4. Three things to establish empirically, first

**Test A — Is `Demand/Silo Load` sales or silo loading?**
This is open question #1 in the brief, and the data can answer it without waiting for a human. KW34 ran Mon 17 – Sat 22 Aug 2026. The sheet says Penne Arrabbiata 30/day, Rührei mit Speck 15/day, Brownies 35/day. Pull actual daily sales for those dishes over that window:

- If actual sales ≈ 30, the number is a demand estimate and Phase 1 forecasts demand.
- If actual sales are consistently below 30, the number is a loading level and Phase 1 forecasts refills — and the gap between the two is either capacity-constrained lost sales or overproduction.
- If sales sometimes hit exactly 30 and stop, that is a capacity ceiling and confirms the silo cap is binding.

**Test B — What is the real yield factor?**
`(loaded − leftover)` from `base_stock_updates` and `fact_cg_waste` gives actual ingredient consumption. `dishes_sold × grams_per_portion` from the BOM gives theoretical. The ratio, per ingredient over 8–12 weeks, is what the hardcoded 1.2 is standing in for. If it comes back at 1.03 for frozen staples and 1.4 for fresh herbs, the flat buffer is provably wrong in both directions.

**Test C — How often is demand censored?**
Count OOS events per dish per day in `fact_cg_oos_ingredient`. If a meaningful share of days have OOS, every naive demand statistic — including the variance that feeds safety stock — is biased low, and uncensoring becomes a Milestone 3 requirement rather than a refinement.

---

## 5. Access setup

### Snowflake

```bash
pip install "snowflake-connector-python[pandas]" pandas
```

Connection values are read from the environment; Google SSO opens a browser window:

```python
import os

import snowflake.connector
conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    authenticator="externalbrowser",
    role=os.environ["SNOWFLAKE_ROLE"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
)
```

For the hosted script later, Joel offered a service account with key-pair authentication — request that at Milestone 2, not now.

The Snowsight web UI is faster than Python for browsing schemas. Use it for orientation, then the script for anything repeatable.

### Lightdash

Two routes: the AI chat in the Lightdash UI, and the Lightdash MCP in Claude. Joel's recommendation is to use the AI chat to ask *which model answers a given question* — it has a semantic layer, so it is good at pointing you at the right table. It will not help with `base_*` or `int_*` models, so treat it as a discovery aid and do the real pulls in Snowflake.

---

## 6. Suggested sequence

1. Run `explore_snowflake.py` steps 1–3. Confirm the connection and find the real schema names and row counts for the tables Joel listed.
2. Run step 4 to dump the column list for each key table. This is what tells you the actual grain — whether sales are per PLU or per dish, whether there is a `unit_id`, what the date column is called.
3. Run steps 5–7: the KW34 validation, the OOS frequency check, and the waste profile.
4. Take the findings back to Joel with concrete questions about the four gaps, rather than asking "what data do you have".
