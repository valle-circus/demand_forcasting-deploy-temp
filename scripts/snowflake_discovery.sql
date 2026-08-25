-- =====================================================================
-- HISTORICAL FIRST-PASS DISCOVERY — SUPERSEDED 2026-08-24
-- Do not use this file for current conclusions or new analysis. It records the
-- restricted Lightdash-role pass that produced several overclaims. Use
-- scripts/snowflake_verification.sql with CIRCUS_MODELS_READER instead.
-- Statements remain read-only for auditability.
--
-- Anything that still needs a name you do not have yet is inside a
-- /* block comment */ with instructions. Nothing outside a comment
-- contains a placeholder, so the whole sheet parses.
--
-- PART A  metadata discovery                 — run with YOUR role
-- PART B  historical Lightdash queries; results are not current conclusions
-- PART C  templates for tables not yet reachable
--
--   use warehouse COMPUTE_WH;   -- whatever yours is called
--   use database ANALYTICS;
-- =====================================================================


-- #####################################################################
-- PART A — METADATA DISCOVERY
-- #####################################################################

-- ---------------------------------------------------------------- A0
-- Who am I? Your personal role sees more than the Lightdash service
-- role does, so run this yourself — the answer determines whether
-- anything in PART C is reachable at all.
select current_user()      as "USER",
       current_role()      as "ROLE",
       current_warehouse() as "WAREHOUSE",
       current_database()  as "DATABASE";


-- ---------------------------------------------------------------- A1
-- Which schemas can your role actually see, and how fresh is each?
-- For reference: the LIGHTDASH_ROLE service account sees exactly ONE
-- schema (LOOKER_STUDIO_CIRCUS, 46 views). If you see BASE,
-- INTERMEDIATE and the FACT_* schema here, your access is wider.
select table_schema,
       count(*)                        as objects,
       count_if(table_type = 'VIEW')   as views,
       count_if(table_type = 'BASE TABLE') as tables,
       max(last_altered)               as most_recent_refresh
from analytics.information_schema.tables
where table_schema <> 'INFORMATION_SCHEMA'
group by 1
order by 1;


-- ---------------------------------------------------------------- A2
-- FULL INVENTORY. The whole discovery exercise in one query.
--   row_count    IS ALWAYS NULL FOR VIEWS. Null means "view", never
--                "empty". Use PART B-style counts to measure volume.
--   last_altered A dbt model that stopped refreshing is the most
--                expensive trap here — it answers confidently, wrongly.
select table_schema, table_name, table_type, row_count, bytes, last_altered
from analytics.information_schema.tables
where table_schema <> 'INFORMATION_SCHEMA'
order by table_schema, table_name;


-- ---------------------------------------------------------------- A3
-- GAP G4 — open purchase orders. FACT_CG_PURCHASE_ORDERS is visible in
-- the object browser, so the question is whether it is USABLE, not
-- whether it exists. Netting needs four things from it:
--   an order date, an EXPECTED DELIVERY date, a quantity, and a status
--   separating still-open from already-received.
-- Without the expected-delivery date and the open/closed flag, a PO
-- table only describes history and cannot prevent the re-ordering bug.
select table_schema, table_name, ordinal_position, column_name, data_type
from analytics.information_schema.columns
where table_name ilike any (
        '%PURCHASE%', '%PROCUREMENT%', '%SUPPLIER%', '%VENDOR%',
        '%GOODS%', '%RECEIPT%', '%SHIPMENT%', '%INBOUND%', '%XENTRAL%'
      )
  and table_schema <> 'INFORMATION_SCHEMA'
order by table_schema, table_name, ordinal_position;


-- ---------------------------------------------------------------- A4
-- GAP G1 — the Dish -> Silo -> Ingredient BOM.
-- Already part-confirmed: LS_FACT_CG_OOS_INGREDIENT exposes
-- RECIPE_PRODUCT_KEY, RECIPE_SLOT_MIN_PER_SLOT,
-- RECIPE_SLOT_INGREDIENT_AMOUNT and PORTION_AMOUNT, which means "slot"
-- really is the silo level and gram amounts per slot-ingredient exist.
-- This block finds the authoritative BASE_RECIPE_* source of that.
select table_schema, table_name, ordinal_position, column_name, data_type
from analytics.information_schema.columns
where table_name ilike any (
        '%RECIPE%', '%SLOT%', '%SILO%', '%PORTION%',
        '%INGREDIENT%', '%MIXED%', '%BOM%'
      )
  and table_schema <> 'INFORMATION_SCHEMA'
order by table_schema, table_name, ordinal_position;


-- ---------------------------------------------------------------- A5
-- HISTORICAL restricted-role search for item/supplier fields.
-- because these are usually columns on an item table, not tables.
-- An empty result here cannot prove absence outside the active role. The wider
-- role later catalogued expiry observations and supplier-name fields.
--
-- If this errors with "Information schema query returned too much data",
-- add:  and table_schema = 'BASE'   and repeat per schema.
select table_schema, table_name, column_name, data_type
from analytics.information_schema.columns
where column_name ilike any (
        '%SHELF%', '%MHD%', '%BEST_BEFORE%', '%EXPIR%', '%DURABILITY%',
        '%LEAD_TIME%', '%LEADTIME%', '%MOQ%', '%CASE%',
        '%SUPPLIER%', '%VENDOR%',
        '%PACK%', '%GRAM%', '%WEIGHT%',
        '%SKU%', '%EAN%', '%GTIN%', '%ARTICLE%',
        '%STORAGE%', '%TEMPERATURE%', '%UOM%'
      )
  and table_schema <> 'INFORMATION_SCHEMA'
order by table_schema, table_name, column_name;


-- ---------------------------------------------------------------- A6
-- Columns for the tables Joel named plus the stock/menu candidates.
-- This reveals the TRUE GRAIN. Watch for a location/unit id: the demand
-- contract is location-aware, so a table without one cannot feed it.
select table_schema, table_name, ordinal_position, column_name, data_type
from analytics.information_schema.columns
where table_name in (
        'FACT_CG_SALES', 'FACT_CG_SALES_DAILY', 'FACT_CG_SALES_HOURLY',
        'FACT_CG_DISH_PRODUCTION', 'FACT_CG_WASTE',
        'FACT_CG_OOS', 'FACT_CG_OOS_INGREDIENT', 'FACT_CG_OOS_SILO',
        'FACT_CG_PURCHASE_ORDERS', 'FACT_CG_MENU_INGREDIENTS_MIN',
        'BASE_STOCK_UPDATES', 'BASE_STOCKS', 'BASE_INVENTORY',
        'BASE_UCS_MENU', 'BASE_MENU', 'BASE_COOKING_JOBS',
        'BASE_INGREDIENTS', 'BASE_INGREDIENT_PORTION_SIZES',
        'INT_UNIT_DAY_MENU'
      )
order by table_schema, table_name, ordinal_position;


-- #####################################################################
-- PART B — HISTORICAL LIGHTDASH RESULTS. Queries ran successfully, but later
-- review found denominator and inference defects. Do not quote their comments.
-- #####################################################################

-- ---------------------------------------------------------------- B1
-- Where dish-level sales actually live.
-- IMPORTANT CORRECTION: FACT_CG_SALES_DAILY has NO dish dimension. Its
-- grain is DAY x LOCATION_NAME x CUSTOMER_ID x REVENUE_SOURCE with only
-- aggregate measures (TOTAL_DISHES_SOLD, UNIQUE_DISHES_SOLD). Requirement
-- D1 ("dishes sold per unit x day x dish") is NOT met by that table.
-- Dish grain lives in FACT_CG_SALES: one row per line item, with PLU
-- and DISH_NAME. Use it, not sales_daily, for demand history.
select day, location_name, unit_serial, plu, dish_name,
       payment_status, is_refunded, cooking_job_status
from analytics.looker_studio_circus.ls_fact_cg_sales
where day between '2026-08-17' and '2026-08-22'
limit 20;


-- ---------------------------------------------------------------- B2
-- FIRST-PASS TEST A. Directionally suggests a loading/capacity target, but the
-- definition remains open. The query excluded zero-sale unit-days, grouped by
-- location rather than unit, and did not establish the workbook's scope.
-- Sheet says Penne Arrabbiata 30/day;
-- measured 3.8 per unit-day, max 8 in any single unit-day. Across all
-- three Rewe units the sheet's 260/day plan met 82.5 actual sales/day
-- (3.2x). Per unit it is 9.5x. Udon Bowl was planned at 30/day and has
-- zero sales rows all week.
with d as (
    select location_name, dish_name, day, count(*) as portions
    from analytics.looker_studio_circus.ls_fact_cg_sales
    where day between '2026-08-17' and '2026-08-22'
      and location_name ilike 'Rewe%'
      and coalesce(is_refunded, false) = false
    group by 1, 2, 3
)
select dish_name,
       count(distinct location_name) as units,
       sum(portions)                 as total_portions,
       round(avg(portions), 1)       as avg_per_unit_day,
       min(portions)                 as min_day,
       max(portions)                 as max_day,
       round(stddev(portions), 2)    as sd_day
from d
group by 1
order by total_portions desc;


-- ---------------------------------------------------------------- B3
-- Was KW34 representative, or a broken week? Run this before trusting
-- any single-week conclusion. Measured: KW34 = 82.5 items/day against a
-- 14-week range of 65-117. Typical. The comparison in B2 holds.
select date_trunc('week', day) as week_start,
       count(*)                as line_items,
       count(distinct day)     as service_days,
       count(distinct location_name) as units,
       round(count(*) / nullif(count(distinct day), 0), 1) as items_per_day
from analytics.looker_studio_circus.ls_fact_cg_sales
where day >= dateadd(week, -14, '2026-08-24')
  and day <  '2026-08-24'
  and location_name ilike 'Rewe%'
  and coalesce(is_refunded, false) = false
group by 1
order by 1;


-- ---------------------------------------------------------------- B4
-- GAP G2, PART closed. The waste model carries PACKAGE_QUANTITY_G (pack
-- size in grams) and EAN. Measured over 12 weeks: 5,699 rows, 72 days,
-- 63 ingredients, 6 units; pack size on 99% of rows, EAN on 96%.
--
-- FIRST-PASS OBSERVATION: no ingredient had more than one non-null pack size
-- in this mirror. COUNT(DISTINCT) ignores nulls, the mirror was incomplete,
-- and some reconciliation used names. It did not prove one canonical pack per
-- ingredient or resolve the spreadsheet cases.
--   Creme Fraiche I TGE  -> 5,000 g single value. The KW34 sheet planned
--     it at 1,000 g and netted at 5,000 g; the NETTING value was right.
--   Kartoffel Schnittlauch Mix -> 1,000 g single value.
--   Paprika Wuerfel -> 1,000 g; PreMix I Paprika Granatapfel -> 1,530 g.
--     "Paprika - big" is a naming mismatch, not a missing item.
--
-- LIMIT: INGREDIENT_TYPE was only 'fresh' or null in the restricted mirror.
-- That did not prove other storage classes were absent from Snowflake.
select ingredient_key,
       ingredient,
       ingredient_type,
       ingredient_unit,
       count(*)                             as rows_seen,
       count(distinct package_quantity_g)   as distinct_pack_sizes,
       max(package_quantity_g)              as pack_g,
       max(ean)                             as ean
from analytics.looker_studio_circus.ls_fact_cg_waste
where day >= dateadd(week, -12, '2026-08-24')
group by 1, 2, 3, 4
order by rows_seen desc;


-- ---------------------------------------------------------------- B5
-- TEST B input — waste profile for the yield factor that the flat x1.2
-- is standing in for.
-- CAUTION: three different quantity columns exist —
--   SILO_END_OF_DAY_QTY_G, STRANDED_QTY_G, WASTE_QTY_G
-- The first pass compared aggregates and suggested an ~80% relationship. That
-- did not establish row-level behavior or measurement lineage.
-- STRANDED_QTY_G is near zero almost everywhere.
-- Confirm with Joel which one is actual disposal BEFORE calibrating.
--
-- HISTORICAL UNVERIFIED HEADLINE: 3,749 kg / EUR 31,340. The saved query did
-- not reproduce the total and the mirror differed from REPORTING. Do not use
-- or quote this figure; run V4 in snowflake_verification.sql instead.
select ingredient,
       count(distinct day)               as days_with_rows,
       round(sum(waste_qty_g))           as waste_g,
       round(sum(stranded_qty_g))        as stranded_g,
       round(sum(silo_end_of_day_qty_g)) as eod_silo_g,
       round(sum(waste_value_eur), 2)    as waste_eur
from analytics.looker_studio_circus.ls_fact_cg_waste
where day >= dateadd(week, -12, '2026-08-24')
group by 1
order by waste_g desc nulls last
limit 25;


-- ---------------------------------------------------------------- B6
-- TEST C — how often is demand censored by a stockout? If a meaningful
-- share of unit-days carry an OOS event, every naive demand statistic is
-- biased low, INCLUDING the variance that feeds safety stock. That makes
-- uncensoring a requirement, not a refinement.
-- LS_FACT_CG_OOS_INGREDIENT also exposes the BOM: RECIPE_PRODUCT_KEY,
-- INGREDIENT_KEY, RECIPE_SLOT_INGREDIENT_AMOUNT, PORTION_AMOUNT.
select date_trunc('week', day)              as week_start,
       count(*)                             as oos_rows,
       count(distinct day)                  as days_with_oos,
       count(distinct ingredient_key)       as ingredients_affected,
       count(distinct recipe_product_key)   as products_affected,
       round(sum(duration_hours), 1)        as oos_hours
from analytics.looker_studio_circus.ls_fact_cg_oos_ingredient
where day >= dateadd(week, -12, '2026-08-24')
group by 1
order by 1;


-- ---------------------------------------------------------------- B7
-- D2 — dishes actually cooked, incl. unsold. Dish-level waste is
-- cooked minus sold, which separates production loss from lost demand.
-- Grain is one row per cooking job, with DISH_NAME, RECIPE_KEY,
-- COOK_TYPE, UNIT_PRODUCTION_STATUS, REASON_CODE and IS_RECOOK.
select day, location_name, dish_name,
       count(*)                                as cooking_jobs,
       count_if(is_recook)                     as recooks,
       count(distinct unit_production_status)  as distinct_statuses
from analytics.looker_studio_circus.ls_fact_cg_dish_production
where day between '2026-08-17' and '2026-08-22'
group by 1, 2, 3
order by 1, 2, cooking_jobs desc;


-- #####################################################################
-- PART C — TEMPLATES
-- Not runnable until PART A tells you the schema and column names.
-- Deliberately inside a block comment so Run All never trips on them.
-- Copy one out, fill in the CAPITALISED names, then run it.
-- #####################################################################

/*
-- C1: grain, span and freshness for any one table.
--     Distinguishes "exists" from "usable": 4 weeks of history cannot
--     calibrate a yield factor, and a model that stopped updating in
--     June cannot drive operations.
select count(*)                                  as rows_total,
       min(DATE_COLUMN)                          as first_date,
       max(DATE_COLUMN)                          as last_date,
       count(distinct DATE_COLUMN)               as distinct_days,
       datediff(day, min(DATE_COLUMN), max(DATE_COLUMN)) as span_days
from analytics.SCHEMA_NAME.TABLE_NAME;

-- C2: open PO pipeline. The query that decides whether G4 is closed.
--     If EXPECTED_DELIVERY_DATE or the open/closed status is missing,
--     the table cannot feed netting.
select STATUS_COLUMN,
       count(*)                                as po_lines,
       min(EXPECTED_DELIVERY_DATE)             as earliest_due,
       max(EXPECTED_DELIVERY_DATE)             as latest_due,
       count_if(EXPECTED_DELIVERY_DATE >= current_date()) as still_inbound
from analytics.SCHEMA_NAME.FACT_CG_PURCHASE_ORDERS
group by 1
order by po_lines desc;

-- C3: the BOM, three levels, from the authoritative BASE source.
--     Confirm one dish resolves to silos and then to gram amounts.
select r.RECIPE_KEY,
       s.SLOT_KEY,
       i.INGREDIENT_KEY,
       i.AMOUNT_G
from analytics.BASE.BASE_RECIPES              r
join analytics.BASE.BASE_RECIPE_SLOTS         s on s.RECIPE_KEY = r.RECIPE_KEY
join analytics.BASE.BASE_RECIPE_SLOT_INGREDIENTS i on i.SLOT_KEY = s.SLOT_KEY
limit 100;

-- C4: current stock on hand, to replace the manual count.
select LOCATION_COLUMN, INGREDIENT_COLUMN,
       max(UPDATED_AT_COLUMN) as as_of,
       sum(QUANTITY_COLUMN)   as on_hand_g
from analytics.BASE.BASE_STOCK_UPDATES
group by 1, 2
order by 1, 2;
*/
