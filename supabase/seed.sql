-- Synthetic UI-only data. Do not use these rows for planning or supplier orders.
-- Supabase runs this file after migrations during local `supabase db reset`.

insert into public.source_imports (
    id,
    dataset_type,
    location_id,
    status,
    source_version,
    source_as_of_at,
    coverage_start_date,
    coverage_end_date,
    file_names,
    file_count,
    total_bytes,
    content_hash,
    parser_version,
    record_count,
    warning_count,
    error_count,
    validation_issues,
    metadata,
    created_at
)
values
    (
        '00000000-0000-0000-0000-000000000101',
        'master_data',
        null,
        'accepted_with_warnings',
        'demo-master-v1',
        null,
        null,
        null,
        array['Phase2_Master_Data_Template_v1.xlsx'],
        1,
        12000,
        'demo-master-content-hash',
        'template_xlsx-v1',
        3,
        1,
        0,
        '[{"severity":"warning","message":"Synthetic proposal values require maintainer approval."}]'::jsonb,
        '{"demo":true}'::jsonb,
        '2026-08-28 07:40:00+00'
    ),
    (
        '00000000-0000-0000-0000-000000000102',
        'planning_input',
        null,
        'accepted',
        'demo-planning-v1',
        null,
        '2026-08-31',
        '2026-10-04',
        array['Phase2_Planning_Input_Template_v1.xlsx'],
        1,
        18000,
        'demo-planning-content-hash',
        'template_xlsx-v1',
        61,
        0,
        0,
        '[]'::jsonb,
        '{"demo":true}'::jsonb,
        '2026-08-28 07:45:00+00'
    ),
    (
        '00000000-0000-0000-0000-000000000103',
        'stock',
        'LOC_DEMO_001',
        'accepted',
        'demo-stock-v1',
        '2026-08-28 06:00:00+00',
        null,
        null,
        array['Apicbase_Stock_Demo.xlsx'],
        1,
        9000,
        'demo-stock-content-hash',
        'apicbase_stock_xlsx-v1',
        1,
        0,
        0,
        '[]'::jsonb,
        '{"demo":true,"source_report_location":"Demo Kitchen"}'::jsonb,
        '2026-08-28 07:50:00+00'
    ),
    (
        '00000000-0000-0000-0000-000000000104',
        'purchase_orders',
        'LOC_DEMO_001',
        'accepted',
        'demo-po-v1',
        '2026-08-27 12:00:00+00',
        '2026-08-27',
        '2026-09-02',
        array['Transgourmet_Demo.pdf'],
        1,
        8000,
        'demo-po-content-hash',
        'transgourmet_pdf-v1',
        1,
        0,
        0,
        '[]'::jsonb,
        '{"demo":true}'::jsonb,
        '2026-08-28 07:55:00+00'
    )
on conflict (id) do nothing;

insert into public.master_data_versions (
    id,
    environment,
    version_label,
    status,
    config_hash,
    source_note,
    created_at,
    activated_at,
    source_import_id
)
values (
    '00000000-0000-0000-0000-000000000201',
    'prototype',
    'demo-master-v1',
    'active',
    'demo-config-hash',
    'Synthetic UI seed; proposal values only.',
    '2026-08-28 07:40:00+00',
    '2026-08-28 07:41:00+00',
    '00000000-0000-0000-0000-000000000101'
)
on conflict (id) do nothing;

insert into public.locations (
    version_id,
    location_id,
    location_name,
    timezone,
    active,
    data_status,
    source_note
)
values (
    '00000000-0000-0000-0000-000000000201',
    'LOC_DEMO_001',
    'Demo Kitchen',
    'Europe/Berlin',
    true,
    'PROPOSAL',
    'Synthetic UI seed.'
)
on conflict (version_id, location_id) do nothing;

insert into public.items (
    version_id,
    item_id,
    item_name,
    storage_class,
    pack_size_g,
    shelf_life_days,
    min_safety_days,
    max_cover_days,
    active,
    data_status,
    source_note
)
values (
    '00000000-0000-0000-0000-000000000201',
    'ITEM_DEMO_PASTA',
    'Demo Pasta',
    'RT',
    1000,
    180,
    2,
    30,
    true,
    'PROPOSAL',
    'Synthetic UI seed.'
)
on conflict (version_id, item_id) do nothing;

insert into public.item_policy_overrides (
    version_id,
    item_id,
    item_type,
    official_supplier,
    ordering_channel,
    supplier_id,
    supplier_article_number,
    supplier_description_match,
    packs_per_order_unit,
    order_unit,
    stock_qty_unit,
    apicbase_uid,
    apicbase_stock_item_name,
    lead_time_calendar_days,
    shelf_life_anchor,
    yield_factor,
    moq_order_units,
    case_multiple_order_units,
    data_status,
    source_note
)
values (
    '00000000-0000-0000-0000-000000000201',
    'ITEM_DEMO_PASTA',
    'INGREDIENT',
    'Transgourmet',
    'Transgourmet',
    'TRANSGOURMET',
    'DEMO-100',
    'Demo Pasta',
    1,
    'PACK',
    'PACK',
    'DEMO-APICBASE-100',
    'Demo Pasta',
    3,
    'RECEIPT_DATE',
    1,
    0,
    1,
    'PROPOSAL',
    'Synthetic UI seed.'
)
on conflict (version_id, item_id) do nothing;

insert into public.delivery_rules (
    version_id,
    delivery_rule_id,
    location_id,
    ordering_channel,
    storage_class,
    delivery_weekday,
    covered_service_weekdays,
    order_weekday,
    order_cutoff_local,
    receipt_available_local,
    review_period_days,
    effective_from,
    effective_to,
    active,
    data_status,
    source_note
)
values (
    '00000000-0000-0000-0000-000000000201',
    'RULE_DEMO_RT',
    'LOC_DEMO_001',
    'Transgourmet',
    'RT',
    0,
    '{}',
    4,
    '10:00',
    '08:00',
    7,
    '2026-01-01',
    null,
    true,
    'PROPOSAL',
    'Synthetic UI seed.'
)
on conflict (version_id, delivery_rule_id) do nothing;

insert into public.forecast_daily (
    import_id,
    location_id,
    service_date,
    dish_id,
    dish_name,
    forecast_portions,
    forecast_version,
    provenance,
    source_note
)
select
    '00000000-0000-0000-0000-000000000102',
    'LOC_DEMO_001',
    day::date,
    'DISH_DEMO_PASTA',
    'Demo Pasta Dish',
    10,
    'demo-planning-v1',
    'manual',
    'Synthetic UI seed.'
from generate_series('2026-08-31'::date, '2026-10-04'::date, interval '1 day') as day
where extract(isodow from day) between 1 and 6
on conflict (import_id, location_id, service_date, dish_id) do nothing;

insert into public.menu_calendar (
    import_id,
    location_id,
    service_date,
    dish_id,
    dish_name,
    menu_version,
    active,
    provenance,
    source_note
)
select
    '00000000-0000-0000-0000-000000000102',
    'LOC_DEMO_001',
    day::date,
    'DISH_DEMO_PASTA',
    'Demo Pasta Dish',
    'demo-menu-v1',
    true,
    'manual',
    'Synthetic UI seed.'
from generate_series('2026-08-31'::date, '2026-10-04'::date, interval '1 day') as day
where extract(isodow from day) between 1 and 6
on conflict (import_id, location_id, service_date, dish_id) do nothing;

insert into public.bom_lines (
    import_id,
    bom_line_id,
    dish_id,
    dish_name,
    silo_id,
    silo_name,
    item_id,
    grams_per_portion,
    effective_from,
    effective_to,
    bom_version,
    active,
    data_status,
    provenance,
    source_note
)
values (
    '00000000-0000-0000-0000-000000000102',
    'BOM_DEMO_001',
    'DISH_DEMO_PASTA',
    'Demo Pasta Dish',
    'SILO_DEMO_PASTA',
    'Demo Pasta Silo',
    'ITEM_DEMO_PASTA',
    100,
    '2026-01-01',
    null,
    'demo-bom-v1',
    true,
    'PROPOSAL',
    'manual',
    'Synthetic UI seed.'
)
on conflict (import_id, bom_line_id) do nothing;

insert into public.inventory_snapshots (
    import_id,
    location_id,
    item_id,
    counted_at,
    usable_on_hand_units,
    partial_pack_g,
    provenance
)
values (
    '00000000-0000-0000-0000-000000000103',
    'LOC_DEMO_001',
    'ITEM_DEMO_PASTA',
    '2026-08-28 06:00:00+00',
    0,
    0,
    'observed'
)
on conflict (import_id, location_id, item_id) do nothing;

insert into public.purchase_order_lines (
    import_id,
    po_line_id,
    po_id,
    location_id,
    supplier_id,
    supplier_article_number,
    supplier_description,
    item_id,
    ordered_at,
    expected_receipt_at,
    ordered_qty_order_units,
    open_qty_units,
    package_content_units,
    source_base_unit_code,
    line_total_eur,
    derived_status,
    mapping_status,
    mapping_message,
    provenance
)
values (
    '00000000-0000-0000-0000-000000000104',
    'PO-DEMO-001-L1',
    'PO-DEMO-001',
    'LOC_DEMO_001',
    'TRANSGOURMET',
    'DEMO-100',
    'Demo Pasta',
    'ITEM_DEMO_PASTA',
    '2026-08-27 10:00:00+00',
    '2026-09-02 06:00:00+00',
    5,
    5,
    1,
    'PACK',
    25,
    'open',
    'mapped',
    null,
    'observed'
)
on conflict (import_id, po_line_id) do nothing;

insert into public.planning_runs (
    run_id,
    schema_version,
    policy_profile,
    policy_version,
    run_mode,
    planning_as_of_at,
    created_at,
    input_hash,
    config_hash,
    code_version,
    status,
    master_data_version_id,
    location_id,
    completed_at,
    failure_summary
)
values (
    'demo-run-20260828',
    1,
    'improved_file/v1',
    'template-recommendation-v1-demo',
    'scenario',
    '2026-08-28 08:00:00+00',
    '2026-08-28 08:00:00+00',
    'demo-input-hash',
    'demo-config-hash',
    'demo-code-version',
    'completed',
    '00000000-0000-0000-0000-000000000201',
    'LOC_DEMO_001',
    '2026-08-28 08:00:02+00',
    null
)
on conflict (run_id) do nothing;

insert into public.planning_run_inputs (
    run_id,
    dataset,
    source_version,
    content_hash,
    provenance,
    record_count,
    source_import_id
)
values
    ('demo-run-20260828', 'forecast_daily', 'demo-planning-v1', 'demo-planning-content-hash', 'manual', 30, '00000000-0000-0000-0000-000000000102'),
    ('demo-run-20260828', 'menu_calendar', 'demo-planning-v1', 'demo-planning-content-hash', 'manual', 30, '00000000-0000-0000-0000-000000000102'),
    ('demo-run-20260828', 'bom_lines', 'demo-planning-v1', 'demo-planning-content-hash', 'manual', 1, '00000000-0000-0000-0000-000000000102'),
    ('demo-run-20260828', 'items', 'demo-master-v1', 'demo-master-content-hash', 'manual', 1, '00000000-0000-0000-0000-000000000101'),
    ('demo-run-20260828', 'inventory_snapshots', 'demo-stock-v1', 'demo-stock-content-hash', 'observed', 1, '00000000-0000-0000-0000-000000000103'),
    ('demo-run-20260828', 'purchase_orders', 'demo-po-v1', 'demo-po-content-hash', 'observed', 1, '00000000-0000-0000-0000-000000000104'),
    ('demo-run-20260828', 'locations', 'demo-master-v1', 'demo-master-content-hash', 'manual', 1, '00000000-0000-0000-0000-000000000101'),
    ('demo-run-20260828', 'item_policies', 'demo-master-v1', 'demo-master-content-hash', 'manual', 1, '00000000-0000-0000-0000-000000000101'),
    ('demo-run-20260828', 'delivery_rules', 'demo-master-v1', 'demo-master-content-hash', 'manual', 1, '00000000-0000-0000-0000-000000000101')
on conflict (run_id, dataset) do nothing;

insert into public.planning_lines (
    planning_line_id,
    run_id,
    location_id,
    item_id,
    supplier_id,
    schedule_rule_id,
    order_date,
    expected_delivery_date,
    coverage_start_date,
    coverage_end_date,
    protection_days,
    gross_requirement_g,
    yield_factor,
    yield_factor_provenance,
    adjusted_requirement_g,
    safety_stock_g,
    safety_stock_provenance,
    usable_on_hand_g,
    open_po_due_g,
    raw_order_g,
    shelf_life_cap_g,
    max_cover_cap_g,
    capped_order_g,
    order_unit_size_g,
    moq_order_units,
    case_multiple_order_units,
    proposed_order_units,
    rounding_delta_g,
    data_status
)
values (
    'LINE-DEMO-001',
    'demo-run-20260828',
    'LOC_DEMO_001',
    'ITEM_DEMO_PASTA',
    'TRANSGOURMET',
    'RULE_DEMO_RT',
    '2026-08-28',
    '2026-09-02',
    '2026-09-02',
    '2026-09-08',
    10,
    35000,
    1,
    'policy_default',
    35000,
    2000,
    'policy_default',
    0,
    5000,
    32000,
    null,
    30000,
    30000,
    1000,
    0,
    1,
    30,
    0,
    'PROPOSAL'
)
on conflict (planning_line_id) do nothing;

insert into public.planning_recommendations (
    recommendation_id,
    planning_line_id,
    run_id,
    location_id,
    supplier_id,
    item_id,
    order_date,
    expected_delivery_date,
    proposed_qty_units
)
values (
    'REC-DEMO-001',
    'LINE-DEMO-001',
    'demo-run-20260828',
    'LOC_DEMO_001',
    'TRANSGOURMET',
    'ITEM_DEMO_PASTA',
    '2026-08-28',
    '2026-09-02',
    30
)
on conflict (recommendation_id) do nothing;

insert into public.planning_netting_results (
    run_id,
    location_id,
    item_id,
    projection_start_date,
    projection_end_date,
    opening_on_hand_g,
    gross_requirement_g,
    open_po_due_g,
    net_requirement_g,
    candidate_receipt_g,
    overdue_open_po_g,
    open_po_after_horizon_g,
    open_po_after_final_demand_g,
    ending_projected_balance_g,
    minimum_projected_balance_g,
    first_stockout_date,
    unavoidable_pre_candidate_stockout_g
)
values (
    'demo-run-20260828',
    'LOC_DEMO_001',
    'ITEM_DEMO_PASTA',
    '2026-08-28',
    '2026-10-04',
    0,
    35000,
    5000,
    30000,
    30000,
    0,
    0,
    0,
    0,
    -2000,
    '2026-08-31',
    2000
)
on conflict (run_id, location_id, item_id) do nothing;

with daily_flows as (
    select
        projection_date::date as projection_date,
        case
            when projection_date::date = date '2026-08-30' then 5000
            when projection_date::date = date '2026-08-31' then 2000
            when projection_date::date = date '2026-09-02' then 10000
            when projection_date::date = date '2026-09-03' then 18000
            else 0
        end::numeric as demand_g,
        case
            when projection_date::date = date '2026-08-29' then 5000
            else 0
        end::numeric as open_po_receipts_g,
        case
            when projection_date::date = date '2026-09-02' then 30000
            else 0
        end::numeric as candidate_receipts_g
    from generate_series(
        date '2026-08-28',
        date '2026-10-04',
        interval '1 day'
    ) as dates(projection_date)
), projected as (
    select
        projection_date,
        demand_g,
        open_po_receipts_g,
        candidate_receipts_g,
        sum(open_po_receipts_g + candidate_receipts_g - demand_g)
            over (order by projection_date rows unbounded preceding) as closing_balance_g
    from daily_flows
)
insert into public.planning_projection_days (
    run_id,
    location_id,
    item_id,
    projection_date,
    opening_balance_g,
    demand_g,
    open_po_receipts_g,
    candidate_receipts_g,
    closing_balance_g,
    stockout_g
)
select
    'demo-run-20260828',
    'LOC_DEMO_001',
    'ITEM_DEMO_PASTA',
    projection_date,
    lag(closing_balance_g, 1, 0::numeric) over (order by projection_date),
    demand_g,
    open_po_receipts_g,
    candidate_receipts_g,
    closing_balance_g,
    greatest(0::numeric, -closing_balance_g)
from projected
on conflict (run_id, location_id, item_id, projection_date) do nothing;

insert into public.planning_exceptions (
    exception_id,
    run_id,
    planning_line_id,
    code,
    severity,
    dataset,
    record_ref,
    message,
    remedy
)
values (
    'EXC-DEMO-001',
    'demo-run-20260828',
    'LINE-DEMO-001',
    'UNAVOIDABLE_PRE_ARRIVAL_STOCKOUT',
    'warning',
    'inventory_projection',
    'location_id=LOC_DEMO_001,item_id=ITEM_DEMO_PASTA',
    'Synthetic demo stockout occurs before the proposed receipt can arrive.',
    'Refresh the source data and review an earlier feasible receipt.'
)
on conflict (exception_id) do nothing;
