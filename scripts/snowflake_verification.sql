-- =====================================================================
-- PHASE 2 SOURCE VERIFICATION — CURRENT
-- Read-only. Every statement uses catalogued table/column names and can be
-- run independently in Snowsight with role CIRCUS_MODELS_READER.
-- In Snowsight, set the database context to ANALYTICS before running a block.
-- This file intentionally does not issue USE ROLE or change warehouse state.
--
-- All required V1-V12 verification blocks, including corrected V3B, were
-- reviewed on 2026-08-25; measured results are preserved in
-- docs/scratchpads/snowflake_verification_evidence.md. A same-ingredient V12
-- rerun is optional calibration work; no required verification rerun remains.
-- Joel confirmed on 2026-08-25 that the three generated models and
-- BASE_INVENTORY are abandoned previous-data-team models and that no purchase-
-- order data is currently ingested into Snowflake to his knowledge. Ops source
-- discovery and a new ingestion/modeling workstream are required.
-- Ask for waste definitions only before sharing or calibrating from V4.
--
-- Keep exported results private. Do not commit raw operational data.
-- Fixed historical windows are bounded above so re-running later does not
-- silently change a result.
-- =====================================================================


-- #####################################################################
-- COMPLETED SCOPE EVIDENCE — RERUN ONLY IF A FRESH SNAPSHOT IS NEEDED
-- #####################################################################

-- ---------------------------------------------------------------- V6
-- GENERATED ORDER RECOMMENDATIONS, NOT CONFIRMED PURCHASE-ORDER RECORDS.
-- Joel confirmed this is an abandoned previous-data-team model. Preserve the
-- query for lineage/reference checks; never use its rows as actual open POs or
-- assume its measured 1.05 uplift is approved Phase 2 policy.
select location_name, ingredient_id, ingredient_name, storage_type, unit,
       package_qty, package_price, order_date, arrival_date,
       demand_in_window, on_hand_qty, demand_plus_safety, net_qty_needed,
       packages_to_order, est_order_cost, order_status,
       generated_at_utc, generated_at_berlin
from reporting.fact_cg_purchase_orders
order by generated_at_berlin desc, ingredient_name
limit 100;

select order_status,
       count(*)                              as lines,
       count(distinct location_name)         as locations,
       count(distinct ingredient_id)         as ingredients,
       min(order_date)                       as first_order_date,
       max(order_date)                       as last_order_date,
       min(arrival_date)                     as first_arrival,
       max(arrival_date)                     as last_arrival,
       count(distinct generated_at_berlin)   as generation_runs,
       min(generated_at_berlin)              as first_generation,
       max(generated_at_berlin)              as latest_generation,
       count_if(arrival_date is null)        as missing_arrival_lines,
       count_if(packages_to_order > 0)       as positive_recommendations
from reporting.fact_cg_purchase_orders
group by 1
order by lines desc;


-- ---------------------------------------------------------------- V8
-- ABANDONED FORECAST MODELS. Their measured grain/quality remains useful
-- reference evidence, but they are not an approved/live Phase 1. Inspect their
-- definitions in data-transformation after repository access is granted.
select table_name, ordinal_position, column_name, data_type
from analytics.information_schema.columns
where table_schema = 'REPORTING'
  and table_name in (
      'FACT_CG_DISH_DEMAND_FORECASTS',
      'FACT_CG_INGREDIENT_DEMAND_FORECASTS'
  )
order by table_name, ordinal_position;

select forecast_date,
       count(*)                              as rows_seen,
       count(distinct location_name)         as locations,
       count(distinct ingredient_id)         as ingredients,
       round(sum(forecasted_quantity))       as total_forecast_qty
from reporting.fact_cg_ingredient_demand_forecasts
group by 1
order by forecast_date;

-- V8 FOLLOW-UP AFTER THE 2026-08-25 EXPORT: the aggregate returned 38 rows
-- but only 31 ingredient IDs per day. Establish the actual key and validity.
select forecast_date, location_name,
       count(*)                                           as rows_seen,
       count(distinct ingredient_id)                     as ingredient_ids,
       count(distinct unit)                              as units,
       count_if(ingredient_id is null
                or trim(ingredient_id) = '')             as missing_ingredient_id,
       count_if(unit is null or trim(unit) = '')         as missing_unit,
       count_if(forecasted_quantity is null)             as missing_quantity,
       count_if(forecasted_quantity < 0)                 as negative_quantity,
       count_if(forecasted_quantity = 0)                 as zero_quantity,
       sum(forecasted_quantity)                          as total_forecast_qty
from reporting.fact_cg_ingredient_demand_forecasts
group by 1, 2
order by 1, 2;

select forecast_date, location_name, ingredient_id, unit,
       count(*)                                           as rows_at_candidate_key,
       count(distinct ingredient_name)                   as ingredient_names,
       sum(forecasted_quantity)                          as total_forecast_qty
from reporting.fact_cg_ingredient_demand_forecasts
group by 1, 2, 3, 4
having count(*) > 1
    or count(distinct ingredient_name) > 1
order by rows_at_candidate_key desc, forecast_date, ingredient_id;

-- V8 RESULT 2026-08-25: 19 ingredients were returned. Twelve have only null/
-- zero placeholder rows; six have one real unit plus a null/zero placeholder;
-- one ingredient (`Rotes Thai Curry`) has both g and ml. No null-unit row has
-- nonzero quantity. Retained for reproducibility; the model is abandoned.
select ingredient_id,
       max(ingredient_name)                               as ingredient_name,
       count(*)                                           as rows_seen,
       count(distinct unit)                               as nonnull_units,
       listagg(distinct coalesce(unit, '(null)'), ', ')
           within group (order by coalesce(unit, '(null)')) as unit_values,
       count_if(unit is null or trim(unit) = '')          as missing_unit_rows,
       count_if(forecasted_quantity = 0)                  as zero_quantity_rows,
       count_if((unit is null or trim(unit) = '')
                and forecasted_quantity <> 0)             as nonzero_without_unit
from reporting.fact_cg_ingredient_demand_forecasts
group by 1
having count(distinct unit) > 1
    or count_if(unit is null or trim(unit) = '') > 0
order by missing_unit_rows desc, ingredient_id;

select date as forecast_date, location_name,
       count(*)                                           as rows_seen,
       count(distinct plu)                               as dishes,
       count(distinct category)                          as categories,
       count_if(plu is null or trim(plu) = '')           as missing_plu,
       count_if(forecast_units is null)                  as missing_forecast,
       count_if(forecast_units < 0)                      as negative_forecast,
       count_if(forecast_units = 0)                      as zero_forecast,
       sum(forecast_units)                               as total_forecast_units
from reporting.fact_cg_dish_demand_forecasts
group by 1, 2
order by 1, 2;

select date as forecast_date, location_name, plu,
       count(*)                                           as rows_at_candidate_key,
       count(distinct dish)                              as dish_names,
       count(distinct category)                          as categories,
       sum(forecast_units)                               as total_forecast_units
from reporting.fact_cg_dish_demand_forecasts
group by 1, 2, 3
having count(*) > 1
    or count(distinct dish) > 1
    or count(distinct category) > 1
order by rows_at_candidate_key desc, forecast_date, plu;

select *
from reporting.fact_cg_dish_demand_forecasts
limit 50;

select table_name, row_count, last_altered
from analytics.information_schema.tables
where table_schema = 'REPORTING'
  and table_name in (
      'FACT_CG_PURCHASE_ORDERS',
      'FACT_CG_DISH_DEMAND_FORECASTS',
      'FACT_CG_INGREDIENT_DEMAND_FORECASTS'
  )
order by table_name;


-- ---------------------------------------------------------------- V7
-- PURCHASE/RECEIPT EXTRACT FITNESS.
-- BASE_INVENTORY has PO number/status and ordered/delivered quantities. Its
-- catalogued schema has no order timestamp and no expected-receipt timestamp,
-- so it cannot by itself provide lead time or dated open-PO netting. Joel
-- confirmed it is abandoned and that no PO data is currently ingested into
-- Snowflake to his knowledge. Do not keep searching this model for live POs.
select po_status,
       count(*)                                           as lines,
       count(distinct po_no_)                             as purchase_orders,
       count(distinct supplier_name)                      as suppliers,
       count(distinct ingredient)                         as ingredients,
       sum(quantity_ordered)                              as qty_ordered,
       sum(quantity_delivered)                            as qty_delivered,
       count_if(quantity_delivered is null
                or quantity_delivered = 0)                as undelivered_lines,
       count_if(delivered_on is null
                or trim(delivered_on) = '')               as missing_delivery_date,
       min(_fivetran_synced)                              as first_sync_seen,
       max(_fivetran_synced)                              as latest_sync_seen
from base.base_inventory
group by 1
order by lines desc;

-- DELIVERED_ON is TEXT. This measures parseability and history span only; it
-- does not create a missing order date or expected receipt date.
select supplier_name,
       count(*)                                           as lines,
       count(try_to_date(delivered_on))                   as parseable_dates,
       count(*) - count(try_to_date(delivered_on))        as unparseable_or_null,
       min(try_to_date(delivered_on))                     as first_delivery,
       max(try_to_date(delivered_on))                     as last_delivery,
       count(distinct ingredient)                         as ingredients
from base.base_inventory
group by 1
order by lines desc;

select po_no_, po_status, supplier_name, stock_item, uid, ingredient,
       quantity_ordered, quantity_delivered, delivered_on, intake_reason,
       _fivetran_synced
from base.base_inventory
order by _fivetran_synced desc
limit 50;

select stock_item_name, uid, location_name, par, current_stock_qty_,
       diff_with_par, supplier_article_numbers, _fivetran_synced
from base.base_stocks
order by stock_item_name;


-- #####################################################################
-- SOURCE FITNESS — CANDIDATES ARE NOT ADAPTER-READY UNTIL THESE PASS
-- #####################################################################

-- ---------------------------------------------------------------- V9
-- BOM COVERAGE AND TOPOLOGY.
-- The reporting model supplies flattened PLU -> ingredient grams. The engine
-- still requires Dish -> Silo -> Ingredient and first-class pre-mix topology.
select count(*)                                                   as rows_seen,
       count(distinct menu_key)                                  as menus,
       count(distinct plu)                                       as dishes,
       count(distinct ingredient_key)                            as ingredients,
       count_if(total_amount_g is null or total_amount_g <= 0)   as bad_gram_rows,
       count_if(menu_key is null or plu is null
                or ingredient_key is null)                       as missing_key_rows
from reporting.fact_cg_menu_dish_ingredients;

-- A current flattened key should not unexpectedly repeat.
select menu_key, menu_revision, plu, plu_revision,
       ingredient_key, ingredient_revision,
       count(*) as duplicate_rows
from reporting.fact_cg_menu_dish_ingredients
group by 1, 2, 3, 4, 5, 6
having count(*) > 1
order by duplicate_rows desc;

-- Does every materialised unit-day menu resolve to a reporting BOM?
select count(*)                                           as unit_days,
       count_if(b.menu_key is null)                       as unit_days_without_bom,
       count(distinct m.menu_key)                         as menu_keys,
       count(distinct case when b.menu_key is null
                           then m.menu_key end)            as menu_keys_without_bom
from intermediate.int_unit_day_menu m
left join (
    select distinct menu_key
    from reporting.fact_cg_menu_dish_ingredients
) b on b.menu_key = m.menu_key;

-- Effective-dating sanity for the historical flattened BOM.
select count(*)                                           as history_rows,
       count_if(valid_from is null)                       as missing_valid_from,
       count_if(valid_to is not null
                and valid_to <= valid_from)               as invalid_intervals,
       min(valid_from)                                    as first_valid_from,
       max(coalesce(valid_to, '9999-12-31'::timestamp_ntz)) as latest_valid_to
from reporting.dim_menu_dish_ingredients_history;

-- Raw three-level sample. This proves keys/topology only; it does not yet map
-- robot dock/resource IDs or prove that AMOUNT is the final grams per portion.
select r.key                          as recipe_key,
       p.key                          as recipe_product_key,
       ps.id                          as product_slot_id,
       s.id                           as recipe_slot_id,
       s.min_per_slot,
       s.max_per_slot,
       si.id                          as slot_ingredient_id,
       si.ingredient_id,
       si.ingredient_revision,
       si.amount,
       si.portion_size_id
from base.base_recipes r
join base.base_recipe_products p
  on p.recipe_id = r.id
 and p.recipe_revision = r.revision
join base.base_recipe_product_slots ps
  on ps.recipe_product_id = p.id
 and ps.recipe_product_revision = p.revision
join base.base_recipe_slots s
  on s.id = ps.recipe_slot_id
join base.base_recipe_slot_ingredients si
  on si.slot_id = s.id
where coalesce(r._fivetran_deleted, false) = false
  and coalesce(p._fivetran_deleted, false) = false
  and coalesce(ps._fivetran_deleted, false) = false
  and coalesce(s._fivetran_deleted, false) = false
  and coalesce(si._fivetran_deleted, false) = false
limit 200;

-- A decomposition mapping exists. It does not establish whether the pre-mix
-- is purchased, assembled on site, or both.
select ingredient_id, ingredient_name, mixed_ingredient_id,
       mixed_ingredient_name, gr, factor
from base.base_mixed_ingredient_mappings
order by mixed_ingredient_name, ingredient_name;


-- ---------------------------------------------------------------- V3
-- SILO CAPACITY INPUTS AND JOIN AMBIGUITY.
-- Do NOT divide MAXIMUM_AMOUNT by an average BOM amount joined only on
-- ingredient. One ingredient can occur in multiple dishes/menus/revisions,
-- which produces a many-to-many result rather than dish capacity.
select s.ingredient_uid,
       count(distinct i.menu_key || '|' || i.plu)         as menu_dish_uses,
       count(distinct i.total_amount_g)                   as portion_g_values,
       min(i.total_amount_g)                              as min_portion_g,
       max(i.total_amount_g)                              as max_portion_g,
       count(distinct s.resource_id)                      as silo_resources,
       count(distinct s.dock_id)                          as docks
from reporting.fact_unit_silo_stock_daily s
join reporting.fact_cg_menu_dish_ingredients i
  on i.ingredient_key = s.ingredient_uid
where s.day >= '2026-06-01'
  and s.day <  '2026-08-24'
  and s.maximum_amount > 0
group by 1
having count(distinct i.menu_key || '|' || i.plu) > 1
    or count(distinct i.total_amount_g) > 1
order by menu_dish_uses desc, portion_g_values desc;

-- Inspect the silo-side keys needed for an exact effective menu/recipe/slot
-- mapping. Ask Joel about RESOURCE_ID/DOCK_ID only if SQL cannot resolve the
-- relationship or its authoritative lineage.
select unit_serial, day, resource_id, dock_id, ingredient_uid,
       maximum_amount, refill_threshold, start_of_day_amount,
       end_of_day_amount
from reporting.fact_unit_silo_stock_daily
where day between '2026-08-17' and '2026-08-22'
  and maximum_amount > 0
order by unit_serial, day, dock_id
limit 200;

-- V3 FIRST PATH RESULT 2026-08-25: 2,576 stock keys; 1,099 had no same-day
-- menu context, 1,477 had menu context but no INGREDIENT_KEY match, and zero
-- slots resolved. The raw sample shows CHAMBER_ALIAS is the constant text
-- 'Chamber Alias', while SILO_RESOURCE_ID carries values such as 1/7/51.
-- Therefore that first query tested the wrong physical-position field and is
-- superseded by the diagnostic below.

-- V3B RESULT 2026-08-25: 2,576 stock keys; 610 without active-menu/detailed-
-- menu context; zero ambiguous active menus; 489 whose menu exists only outside
-- the event day; 1,636 matching via INGREDIENT_KEY; zero via the other tested
-- ingredient IDs; zero SILO_RESOURCE_ID-to-RECIPE_SLOT_INSERTING_POSITION
-- matches; and zero uniquely or ambiguously resolved exact physical slots.
-- The direct resource-position equality is rejected. Physical capacity now
-- requires authoritative model/upstream lineage, not another inferred join.
with stock_keys as (
    select distinct to_date(s.original_timestamp) as day,
           s.active_menu_public_id,
           s.silo_resource_id,
           s.chamber_alias,
           s.ingredient_key
    from base.base_stock_updates s
    where s.original_timestamp >= '2026-08-03'::timestamp_ntz
      and s.original_timestamp <  '2026-08-24'::timestamp_ntz
), candidate_slots as (
    select s.*,
           count(distinct m.menu_key) as active_menu_keys,
           count(distinct iff(m.day = s.day, m.menu_key, null))
                                                        as same_day_menu_keys,
           count(distinct i.recipe_slot_id)            as detailed_menu_slots,
           count(distinct iff(
               i.ingredient_key = s.ingredient_key,
               i.recipe_slot_id,
               null
           ))                                           as via_ingredient_key,
           count(distinct iff(
               i.ingredient_id = s.ingredient_key,
               i.recipe_slot_id,
               null
           ))                                           as via_ingredient_id,
           count(distinct iff(
               i.recipe_slot_ingredient_ingredient_id = s.ingredient_key,
               i.recipe_slot_id,
               null
           ))                                           as via_slot_ingredient_id,
           count(distinct iff(
               lower(trim(to_varchar(i.recipe_slot_inserting_position)))
                   = lower(trim(to_varchar(s.silo_resource_id))),
               i.recipe_slot_id,
               null
           ))                                           as via_resource_position,
           count(distinct iff(
               (i.ingredient_key = s.ingredient_key
                or i.ingredient_id = s.ingredient_key
                or i.recipe_slot_ingredient_ingredient_id = s.ingredient_key)
               and lower(trim(to_varchar(i.recipe_slot_inserting_position)))
                   = lower(trim(to_varchar(s.silo_resource_id))),
               i.recipe_slot_id,
               null
           ))                                           as exact_slot_candidates
    from stock_keys s
    left join intermediate.int_unit_day_menu m
      on m.active_menu_public_id = s.active_menu_public_id
    left join reporting.fact_cg_menu_ingredients i
      on i.menu_key = m.menu_key
    group by 1, 2, 3, 4, 5
)
select count(*)                                          as stock_keys,
       count(distinct chamber_alias)                    as chamber_alias_values,
       count_if(active_menu_keys = 0)                   as without_active_menu,
       count_if(active_menu_keys > 1)                   as ambiguous_active_menu,
       count_if(active_menu_keys > 0
                and same_day_menu_keys = 0)             as menu_only_outside_event_day,
       count_if(detailed_menu_slots = 0)                as without_detailed_menu,
       count_if(via_ingredient_key > 0)                 as matches_via_ingredient_key,
       count_if(via_ingredient_id > 0)                  as matches_via_ingredient_id,
       count_if(via_slot_ingredient_id > 0)             as matches_via_slot_ingredient_id,
       count_if(via_resource_position > 0)              as matches_resource_position,
       count_if(exact_slot_candidates = 1)              as uniquely_resolved_slots,
       count_if(exact_slot_candidates > 1)              as ambiguous_exact_slots
from candidate_slots;


-- ---------------------------------------------------------------- V5
-- ITEM MASTER, PACK SIZE, EAN, AND STORAGE CANDIDATE QUALITY.
-- V5 RESULT 2026-08-25: 76 rows, 75 non-null IDs, one missing ID, zero bad
-- pack quantities, zero missing units, seven missing EANs, and ten missing
-- APICBASE_IDs. The exception query returned only the blank ID; the storage
-- query likewise returned only the blank-ID FRESH recommendation row.
select count(*)                                           as rows_seen,
       count(distinct ingredient_id)                     as ingredient_ids,
       count_if(ingredient_id is null)                   as missing_id,
       count_if(quantity is null or quantity <= 0)       as bad_pack_quantity,
       count_if(unit is null or trim(unit) = '')         as missing_unit,
       count_if(ean is null)                             as missing_ean,
       count_if(apicbase_id is null)                     as missing_apicbase_id
from base.base_ingredient_list;

select ingredient_id, count(*) as rows_per_id,
       count(distinct quantity) as pack_quantities,
       count(distinct unit) as units,
       count(distinct ean) as eans
from base.base_ingredient_list
group by 1
having ingredient_id is null
    or count(*) > 1
    or count(distinct quantity) > 1
    or count(distinct unit) > 1
    or count(distinct ean) > 1
order by rows_per_id desc;

-- STORAGE_TYPE is currently observed on generated recommendations. Check
-- consistency, but do not adopt it as master data until its lineage is known.
select p.ingredient_id,
       max(l.name)                                       as ingredient_name,
       count(distinct p.storage_type)                    as storage_types,
       listagg(distinct p.storage_type, ', ')
           within group (order by p.storage_type)        as storage_type_values,
       max(l.ingredient_type)                            as item_master_type
from reporting.fact_cg_purchase_orders p
left join base.base_ingredient_list l
  on l.ingredient_id = p.ingredient_id
group by 1
having count(distinct p.storage_type) <> 1
    or max(l.ingredient_id) is null
order by p.ingredient_id;


-- ---------------------------------------------------------------- V10
-- EXPIRY OBSERVATIONS, NOT SHELF-LIFE POLICY.
-- DAYS_UNTIL_EXPIRATION is remaining life on a silo-day. It does not reveal
-- sealed vs opened shelf life or the approved planning safety margin.
select count(*)                                           as silo_days,
       count(expiration_date)                             as with_expiry,
       round(100.0 * count(expiration_date)
             / nullif(count(*), 0), 1)                   as pct_with_expiry,
       count_if(expiration_warning)                       as warning_rows,
       min(days_until_expiration)                         as min_days_left,
       round(avg(days_until_expiration), 1)               as avg_days_left,
       max(days_until_expiration)                         as max_days_left
from reporting.fact_unit_silo_stock_daily
where day >= '2026-06-01'
  and day <  '2026-08-24';

select ingredient_uid,
       count(*)                                           as silo_days,
       count(expiration_date)                             as with_expiry,
       min(days_until_expiration)                         as min_days_left,
       round(avg(days_until_expiration), 1)               as avg_days_left,
       max(days_until_expiration)                         as max_days_left
from reporting.fact_unit_silo_stock_daily
where day >= '2026-06-01'
  and day <  '2026-08-24'
group by 1
order by with_expiry desc, ingredient_uid;


-- ---------------------------------------------------------------- V11
-- FORWARD MENU HORIZON. Data availability does not define the business
-- commitment point; operations must confirm when future menus are firm.
-- V11 RESULT 2026-08-25: INT_UNIT_DAY_MENU spans 2025-10-21 through
-- 2026-08-24 across six units and 26 menus; DAYS_AHEAD_OF_TODAY = -1. It is not
-- currently a forward-menu feed. The base query returns later records but mixes
-- operational-looking menus with pilot/demo/training/far-future/terminated rows.
select min(day) as first_day,
       max(day) as last_day,
       datediff(day, current_date(), max(day)) as days_ahead_of_today,
       count(distinct unit_serial) as units,
       count(distinct menu_key) as menus
from intermediate.int_unit_day_menu;

-- Base records include pilot/far-future and terminated rows. Keep explicit
-- diagnostic flags rather than treating MAX(ENDS_AT) as a committed horizon.
select unit_serial, menu_template_name,
       min(starts_at) as starts_at,
       max(ends_at) as ends_at,
       max(terminated_at) as terminated_at,
       iff(max(terminated_at) is not null, true, false) as has_termination,
       iff(lower(menu_template_name) like '%pilot%'
           or lower(menu_template_name) like '%test%'
           or lower(menu_template_name) like '%training%'
           or lower(menu_template_name) like '%demo%', true, false)
                                                        as nonproduction_name_hint
from base.base_ucs_menu
where ends_at >= current_date() or ends_at is null
group by 1, 2
order by starts_at desc;


-- ---------------------------------------------------------------- V12
-- STOCK ACTIVITY AND REFILL/CONSUMPTION SEMANTICS.
-- NET_DEPLETION and REFILL_COUNT can describe activity; REFILL_COUNT is not a
-- gram quantity, and NET_DEPLETION may combine consumption with refills.
select day,
       count(distinct unit_serial)               as units,
       count(*)                                  as silo_days,
       round(sum(net_depletion) / 1000, 1)       as net_depletion_kg,
       sum(refill_count)                         as refill_events,
       sum(stock_update_count)                   as stock_updates,
       count_if(below_refill_threshold)          as below_threshold_silo_days
from reporting.fact_unit_silo_stock_daily
where day >= '2026-08-03'
  and day <  '2026-08-24'
group by 1
order by 1;

-- Which raw events may carry the quantities needed to derive refills and
-- consumption? First inspect the returned event populations and deltas; ask a
-- targeted lineage question only if the data cannot establish the semantics.
select event,
       count(*)                                  as rows_seen,
       count(distinct silo_resource_id)          as silos,
       count(original_amount)                    as rows_with_original_amount,
       count(orderable_amount_left)              as rows_with_orderable_amount,
       min(original_timestamp)                   as first_event,
       max(original_timestamp)                   as latest_event
from base.base_stock_updates
where original_timestamp >= '2026-08-03'::timestamp_ntz
  and original_timestamp <  '2026-08-24'::timestamp_ntz
group by 1
order by rows_seen desc;

select event, original_timestamp, context_instance_id,
       active_menu_public_id, chamber_alias,
       silo_resource_id, ingredient_key,
       original_amount, orderable_amount_left, reserved_amount,
       maximum_amount, threshold_amount, expires_at
from base.base_stock_updates
where original_timestamp >= '2026-08-17'::timestamp_ntz
  and original_timestamp <  '2026-08-24'::timestamp_ntz
order by original_timestamp desc
limit 100;

-- V12 RESULT 2026-08-25: 147,980 transitions; 17,691 ingredient changes;
-- 25,332 positive, 30,817 negative and 91,831 unchanged transitions. Gross
-- changes were +15,275.5 kg and -15,317.9 kg, including jumps above 7 kg.
-- This confirms a state stream with resets/corrections, not physical usage.
-- Retained for reproducibility; rerun with same-ingredient filtering only if
-- consumption/refill calibration becomes current work.
with ordered_updates as (
    select id, event, original_timestamp, context_instance_id,
           silo_resource_id, ingredient_key,
           orderable_amount_left,
           lag(orderable_amount_left) over (
               partition by context_instance_id, silo_resource_id
               order by original_timestamp, id
           ) as previous_orderable_amount,
           lag(ingredient_key) over (
               partition by context_instance_id, silo_resource_id
               order by original_timestamp, id
           ) as previous_ingredient_key
    from base.base_stock_updates
    where original_timestamp >= '2026-08-03'::timestamp_ntz
      and original_timestamp <  '2026-08-24'::timestamp_ntz
), transitions as (
    select *, orderable_amount_left - previous_orderable_amount as delta_amount
    from ordered_updates
    where previous_orderable_amount is not null
)
select count(*)                                             as transitions,
       count_if(not equal_null(ingredient_key,
                               previous_ingredient_key))    as ingredient_changes,
       count_if(delta_amount > 0)                          as positive_changes,
       count_if(delta_amount < 0)                          as negative_changes,
       count_if(delta_amount = 0)                          as unchanged,
       round(sum(iff(delta_amount > 0, delta_amount, 0)) / 1000, 1)
                                                            as positive_change_kg,
       round(-sum(iff(delta_amount < 0, delta_amount, 0)) / 1000, 1)
                                                             as negative_change_kg,
       count_if(equal_null(ingredient_key, previous_ingredient_key)
                and delta_amount > 0)                       as same_ingredient_positive,
       count_if(equal_null(ingredient_key, previous_ingredient_key)
                and delta_amount < 0)                       as same_ingredient_negative,
       round(sum(iff(equal_null(ingredient_key, previous_ingredient_key)
                     and delta_amount > 0, delta_amount, 0)) / 1000, 1)
                                                             as same_ingredient_positive_kg,
       round(-sum(iff(equal_null(ingredient_key, previous_ingredient_key)
                      and delta_amount < 0, delta_amount, 0)) / 1000, 1)
                                                             as same_ingredient_negative_kg,
       min(delta_amount)                                   as largest_negative_change,
       max(delta_amount)                                   as largest_positive_change
from transitions;


-- #####################################################################
-- REPAIR EARLIER MEASUREMENTS — RUN BEFORE QUOTING DEMAND OR WASTE
-- #####################################################################

-- ---------------------------------------------------------------- V1
-- Unit/location mapping, sales-row uniqueness, and status populations.
-- V1 RESULT 2026-08-25: six observed location names, each mapping to one unit
-- serial. The status population below is retained for reproducibility.
select location_name,
       count(distinct unit_serial) as units_at_location,
       min(unit_serial) as example_unit
from reporting.fact_cg_sales
where day >= '2026-05-18'
  and day <  '2026-08-24'
group by 1
order by units_at_location desc, location_name;

select payment_status, cooking_job_status,
       count(*) as rows_seen,
       count(distinct line_item_id) as line_items,
       count_if(is_refunded) as refunded_rows
from reporting.fact_cg_sales
where day between '2026-08-17' and '2026-08-22'
group by 1, 2
order by rows_seen desc;


-- ---------------------------------------------------------------- V2
-- Demand comparison with zero-sale deployed unit-days included. V1 found
-- refunded and failed/null cooking states, so only CLOSED/SERVED lines count.
-- Counting one valid line item as one portion remains a source-contract check.
-- V2 DISH RESULT 2026-08-25: corrected output has 20 dishes, 221 deployed
-- dish-unit-days, 39 zero-sale days, 622 portions, and max unit-day 15.
with deployed as (
    select distinct m.unit_serial, m.day, i.plu, i.product_name_de as dish
    from intermediate.int_unit_day_menu m
    join reporting.fact_cg_menu_dish_ingredients i
      on i.menu_key = m.menu_key
    where m.day between '2026-08-17' and '2026-08-22'
),
sold as (
    select unit_serial, day, plu, count(distinct line_item_id) as portions
    from reporting.fact_cg_sales
    where day between '2026-08-17' and '2026-08-22'
      and payment_status = 'CLOSED'
      and cooking_job_status = 'SERVED'
    group by 1, 2, 3
)
select d.dish,
       count(*)                                  as deployed_unit_days,
       count_if(coalesce(s.portions, 0) = 0)     as zero_sale_unit_days,
       sum(coalesce(s.portions, 0))              as total_portions,
       round(avg(coalesce(s.portions, 0)), 2)    as avg_per_deployed_unit_day,
       max(coalesce(s.portions, 0))              as max_unit_day,
       round(stddev(coalesce(s.portions, 0)), 2) as sd
from deployed d
left join sold s
  on s.unit_serial = d.unit_serial
 and s.day = d.day
 and s.plu = d.plu
group by 1
order by total_portions desc;

-- Whether the workbook number is per unit or network-wide remains a planner
-- question; this output only supplies the measured per-unit denominator.
-- V2B RESULT 2026-08-25: five selling/production units reconcile to 622
-- portions: 191, 157, 126, 106, and 42; portions/service-day are 31.8, 26.2,
-- 31.5, 17.7, and 8.4 respectively.
with deployed as (
    select distinct m.unit_serial, m.day, i.plu
    from intermediate.int_unit_day_menu m
    join reporting.fact_cg_menu_dish_ingredients i
      on i.menu_key = m.menu_key
    where m.day between '2026-08-17' and '2026-08-22'
),
sold as (
    select unit_serial, day, plu, count(distinct line_item_id) as portions
    from reporting.fact_cg_sales
    where day between '2026-08-17' and '2026-08-22'
      and payment_status = 'CLOSED'
      and cooking_job_status = 'SERVED'
    group by 1, 2, 3
)
select d.unit_serial,
       count(distinct d.day) as service_days,
       count(distinct d.plu) as dishes_deployed,
       sum(coalesce(s.portions, 0)) as portions_sold,
       round(sum(coalesce(s.portions, 0))
             / nullif(count(distinct d.day), 0), 1) as portions_per_day
from deployed d
left join sold s
  on s.unit_serial = d.unit_serial
 and s.day = d.day
 and s.plu = d.plu
group by 1
order by portions_sold desc;


-- ---------------------------------------------------------------- V4
-- WASTE REPRODUCTION. Do not call WASTE_QTY_G physical disposal and do not
-- share the EUR result until Joel confirms definitions and valuation lineage.
select count(*)                                           as rows_total,
       count(distinct unit_serial || '|' || day)          as unit_days,
       count(distinct unit_serial)                        as units,
       count(distinct ingredient_key)                     as ingredients,
       min(day)                                           as first_day,
       max(day)                                           as last_day,
       count(*) - count(waste_qty_g)                      as null_waste_rows,
       count(*) - count(package_quantity_g)               as null_pack_rows,
       round(sum(waste_qty_g) / 1000, 1)                  as reported_waste_kg,
       round(sum(waste_value_eur))                        as reported_waste_eur,
       round(sum(silo_end_of_day_qty_g) / 1000, 1)        as eod_silo_kg,
       round(sum(waste_value_eur)
             / nullif(count(distinct unit_serial || '|' || day), 0), 2)
                                                           as eur_per_unit_day
from reporting.fact_cg_waste
where day >= '2026-06-01'
  and day <  '2026-08-24';

-- A ratio distribution is a diagnostic, not lineage proof. Tight ratios can
-- still reflect a business process; wide ratios can still be derived.
select count(*)                                as rows_scored,
       round(min(r), 3)                        as ratio_min,
       round(approx_percentile(r, 0.10), 3)    as p10,
       round(approx_percentile(r, 0.50), 3)    as median,
       round(approx_percentile(r, 0.90), 3)    as p90,
       round(max(r), 3)                        as ratio_max,
       round(stddev(r), 4)                     as ratio_sd
from (
    select waste_qty_g / nullif(silo_end_of_day_qty_g, 0) as r
    from reporting.fact_cg_waste
    where day >= '2026-06-01'
      and day <  '2026-08-24'
      and silo_end_of_day_qty_g > 0
      and waste_qty_g is not null
);

select coalesce(ingredient_type, '(null)') as ingredient_type,
       coalesce(ingredient_texture, '(null)') as texture,
       count(distinct ingredient_key) as ingredients,
       count(*) as rows_seen
from reporting.fact_cg_waste
where day >= '2026-06-01'
  and day <  '2026-08-24'
group by 1, 2
order by ingredients desc;
