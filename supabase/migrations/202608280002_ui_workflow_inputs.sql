-- Workflow input and result persistence for the three-page maintainer UI.
-- Run this once in the Supabase SQL Editor after 202608280001_ui_foundation.sql.
-- The transaction prevents a partially applied schema when any statement fails.
-- Keep this portable: Supabase is the prototype adapter and Snowflake remains
-- the intended future operational/result store.

begin;

do $$
begin
    if to_regclass('public.master_data_versions') is null
        or to_regclass('public.planning_runs') is null
        or to_regclass('public.planning_run_inputs') is null
        or to_regclass('public.locations') is null
    then
        raise exception
            'Missing UI foundation tables. Apply 202608280001_ui_foundation.sql before this migration.';
    end if;

    if exists (select 1 from public.planning_runs) then
        raise exception
            'planning_runs already contains rows. Assign and validate a location_id migration before applying this prototype extension.';
    end if;
end
$$;

create table public.source_imports (
    id uuid primary key default gen_random_uuid(),
    dataset_type text not null
        check (dataset_type in ('master_data', 'planning_input', 'stock', 'purchase_orders')),
    location_id text,
    status text not null default 'received'
        check (
            status in (
                'received',
                'validating',
                'accepted',
                'accepted_with_warnings',
                'rejected'
            )
        ),
    source_version text not null,
    source_as_of_at timestamptz,
    coverage_start_date date,
    coverage_end_date date,
    file_names text[] not null default '{}',
    file_count integer not null default 1 check (file_count > 0),
    total_bytes bigint not null default 0 check (total_bytes >= 0),
    content_hash text not null,
    parser_version text not null,
    record_count integer not null default 0 check (record_count >= 0),
    warning_count integer not null default 0 check (warning_count >= 0),
    error_count integer not null default 0 check (error_count >= 0),
    validation_issues jsonb not null default '[]'::jsonb
        check (jsonb_typeof(validation_issues) = 'array'),
    metadata jsonb not null default '{}'::jsonb
        check (jsonb_typeof(metadata) = 'object'),
    supersedes_import_id uuid references public.source_imports(id) on delete set null,
    created_at timestamptz not null default now(),
    created_by uuid references auth.users(id) on delete set null,
    check (coverage_end_date is null or coverage_start_date is null or coverage_end_date >= coverage_start_date),
    check (dataset_type not in ('stock', 'purchase_orders') or location_id is not null)
);

create index source_imports_dataset_location_created_idx
    on public.source_imports (dataset_type, location_id, created_at desc);

create index source_imports_status_idx on public.source_imports (status);

alter table public.master_data_versions
    add column source_import_id uuid references public.source_imports(id) on delete set null;

alter table public.planning_runs
    add column location_id text not null,
    add column completed_at timestamptz,
    add column failure_summary text;

alter table public.planning_runs
    add constraint planning_runs_completed_after_created
    check (completed_at is null or completed_at >= created_at);

alter table public.planning_runs
    add constraint planning_runs_master_location_fk
    foreign key (master_data_version_id, location_id)
        references public.locations(version_id, location_id);

create index planning_runs_location_created_idx
    on public.planning_runs (location_id, created_at desc);

alter table public.planning_run_inputs
    add column source_import_id uuid references public.source_imports(id) on delete set null;

create table public.forecast_daily (
    import_id uuid not null references public.source_imports(id) on delete cascade,
    location_id text not null,
    service_date date not null,
    dish_id text not null,
    dish_name text not null,
    forecast_portions numeric not null check (forecast_portions >= 0),
    forecast_version text not null,
    provenance text not null
        check (provenance in ('observed', 'manual', 'policy_default', 'empty_placeholder', 'unavailable')),
    source_note text,
    primary key (import_id, location_id, service_date, dish_id)
);

create index forecast_daily_location_date_idx
    on public.forecast_daily (location_id, service_date);

create table public.menu_calendar (
    import_id uuid not null references public.source_imports(id) on delete cascade,
    location_id text not null,
    service_date date not null,
    dish_id text not null,
    dish_name text not null,
    menu_version text not null,
    active boolean not null default true,
    provenance text not null
        check (provenance in ('observed', 'manual', 'policy_default', 'empty_placeholder', 'unavailable')),
    source_note text,
    primary key (import_id, location_id, service_date, dish_id)
);

create index menu_calendar_location_date_idx
    on public.menu_calendar (location_id, service_date);

create table public.bom_lines (
    import_id uuid not null references public.source_imports(id) on delete cascade,
    bom_line_id text not null,
    dish_id text not null,
    dish_name text not null,
    silo_id text not null,
    silo_name text not null,
    item_id text not null,
    grams_per_portion numeric not null check (grams_per_portion > 0),
    effective_from date not null,
    effective_to date,
    bom_version text not null,
    active boolean not null default true,
    data_status text not null,
    provenance text not null
        check (provenance in ('observed', 'manual', 'policy_default', 'empty_placeholder', 'unavailable')),
    source_note text,
    primary key (import_id, bom_line_id),
    check (effective_to is null or effective_to >= effective_from)
);

create index bom_lines_dish_effective_idx
    on public.bom_lines (dish_id, effective_from, effective_to);

create table public.inventory_snapshots (
    import_id uuid not null references public.source_imports(id) on delete cascade,
    location_id text not null,
    item_id text not null,
    counted_at timestamptz not null,
    usable_on_hand_units numeric not null check (usable_on_hand_units >= 0),
    partial_pack_g numeric not null default 0 check (partial_pack_g >= 0),
    provenance text not null
        check (provenance in ('observed', 'manual', 'policy_default', 'empty_placeholder', 'unavailable')),
    primary key (import_id, location_id, item_id)
);

create index inventory_snapshots_location_counted_idx
    on public.inventory_snapshots (location_id, counted_at desc);

create table public.purchase_order_lines (
    import_id uuid not null references public.source_imports(id) on delete cascade,
    po_line_id text not null,
    po_id text not null,
    location_id text not null,
    supplier_id text not null,
    supplier_article_number text not null,
    supplier_description text not null,
    item_id text,
    ordered_at timestamptz not null,
    expected_receipt_at timestamptz,
    ordered_qty_order_units numeric not null check (ordered_qty_order_units >= 0),
    open_qty_units numeric check (open_qty_units >= 0),
    package_content_units numeric check (package_content_units > 0),
    source_base_unit_code text,
    line_total_eur numeric check (line_total_eur >= 0),
    derived_status text not null
        check (derived_status in ('open', 'closed', 'undated')),
    mapping_status text not null
        check (
            mapping_status in (
                'mapped',
                'unmapped',
                'description_mismatch',
                'ambiguous'
            )
        ),
    mapping_message text,
    provenance text not null
        check (provenance in ('observed', 'manual', 'policy_default', 'empty_placeholder', 'unavailable')),
    primary key (import_id, po_line_id),
    check (expected_receipt_at is null or expected_receipt_at >= ordered_at),
    check (mapping_status <> 'mapped' or item_id is not null)
);

create index purchase_order_lines_location_ordered_idx
    on public.purchase_order_lines (location_id, ordered_at desc);

create index purchase_order_lines_location_status_idx
    on public.purchase_order_lines (location_id, derived_status, expected_receipt_at);

create table public.planning_netting_results (
    run_id text not null references public.planning_runs(run_id) on delete cascade,
    location_id text not null,
    item_id text not null,
    projection_start_date date not null,
    projection_end_date date not null,
    opening_on_hand_g numeric not null check (opening_on_hand_g >= 0),
    gross_requirement_g numeric not null check (gross_requirement_g >= 0),
    open_po_due_g numeric not null check (open_po_due_g >= 0),
    net_requirement_g numeric not null check (net_requirement_g >= 0),
    candidate_receipt_g numeric not null check (candidate_receipt_g >= 0),
    overdue_open_po_g numeric not null check (overdue_open_po_g >= 0),
    open_po_after_horizon_g numeric not null check (open_po_after_horizon_g >= 0),
    open_po_after_final_demand_g numeric not null check (open_po_after_final_demand_g >= 0),
    ending_projected_balance_g numeric not null,
    minimum_projected_balance_g numeric not null,
    first_stockout_date date,
    unavoidable_pre_candidate_stockout_g numeric not null
        check (unavoidable_pre_candidate_stockout_g >= 0),
    primary key (run_id, location_id, item_id),
    check (projection_end_date >= projection_start_date)
);

create index planning_netting_results_location_stockout_idx
    on public.planning_netting_results (location_id, first_stockout_date);

create table public.planning_projection_days (
    run_id text not null,
    location_id text not null,
    item_id text not null,
    projection_date date not null,
    opening_balance_g numeric not null,
    demand_g numeric not null check (demand_g >= 0),
    open_po_receipts_g numeric not null check (open_po_receipts_g >= 0),
    candidate_receipts_g numeric not null check (candidate_receipts_g >= 0),
    closing_balance_g numeric not null,
    stockout_g numeric not null check (stockout_g >= 0),
    primary key (run_id, location_id, item_id, projection_date),
    foreign key (run_id, location_id, item_id)
        references public.planning_netting_results(run_id, location_id, item_id)
        on delete cascade
);

create index planning_projection_days_run_location_date_idx
    on public.planning_projection_days (run_id, location_id, projection_date, item_id);

alter table public.source_imports enable row level security;
alter table public.forecast_daily enable row level security;
alter table public.menu_calendar enable row level security;
alter table public.bom_lines enable row level security;
alter table public.inventory_snapshots enable row level security;
alter table public.purchase_order_lines enable row level security;
alter table public.planning_netting_results enable row level security;
alter table public.planning_projection_days enable row level security;

revoke all on public.source_imports from anon, authenticated;
revoke all on public.forecast_daily from anon, authenticated;
revoke all on public.menu_calendar from anon, authenticated;
revoke all on public.bom_lines from anon, authenticated;
revoke all on public.inventory_snapshots from anon, authenticated;
revoke all on public.purchase_order_lines from anon, authenticated;
revoke all on public.planning_netting_results from anon, authenticated;
revoke all on public.planning_projection_days from anon, authenticated;

comment on table public.source_imports is
    'Immutable metadata and compact validation summary for one UI source upload.';
comment on column public.source_imports.validation_issues is
    'Small UI-facing validation/mapping issue list; split into a table only if scale requires it.';
comment on table public.purchase_order_lines is
    'Observed Transgourmet PDF history and derived V1 status; not live supplier confirmation.';
comment on table public.planning_netting_results is
    'Persisted NettingResult summaries used by location risk and overview.';
comment on table public.planning_projection_days is
    'Daily typed inventory projection output used for stock-risk timelines and explanation; balances may be negative.';

commit;
