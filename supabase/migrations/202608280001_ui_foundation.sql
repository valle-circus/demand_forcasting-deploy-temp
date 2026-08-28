-- Prototype persistence foundation for Phase 2 supply planning.
-- These tables mirror portable application contracts; Snowflake remains the
-- intended long-term result store unless a later architecture decision changes it.

create table public.master_data_versions (
    id uuid primary key default gen_random_uuid(),
    environment text not null default 'prototype',
    version_label text not null,
    status text not null default 'draft'
        check (status in ('draft', 'active', 'archived')),
    config_hash text,
    source_note text,
    created_at timestamptz not null default now(),
    created_by uuid references auth.users(id) on delete set null,
    activated_at timestamptz,
    activated_by uuid references auth.users(id) on delete set null,
    unique (environment, version_label)
);

create unique index master_data_versions_one_active_per_environment
    on public.master_data_versions (environment)
    where status = 'active';

create table public.locations (
    version_id uuid not null references public.master_data_versions(id) on delete cascade,
    location_id text not null,
    location_name text not null,
    timezone text not null,
    active boolean not null default true,
    data_status text not null,
    source_note text,
    primary key (version_id, location_id)
);

create table public.items (
    version_id uuid not null references public.master_data_versions(id) on delete cascade,
    item_id text not null,
    item_name text not null,
    storage_class text not null check (storage_class in ('TK', 'Kuehl', 'RT', 'Frisch')),
    pack_size_g numeric not null check (pack_size_g > 0),
    shelf_life_days integer check (shelf_life_days > 0),
    min_safety_days numeric check (min_safety_days >= 0),
    max_cover_days numeric check (max_cover_days > 0),
    active boolean not null default true,
    data_status text not null,
    source_note text,
    primary key (version_id, item_id)
);

create table public.item_policy_overrides (
    version_id uuid not null,
    item_id text not null,
    item_type text not null check (item_type in ('POD', 'INGREDIENT')),
    official_supplier text not null,
    ordering_channel text not null,
    supplier_id text not null,
    supplier_article_number text,
    supplier_description_match text,
    packs_per_order_unit numeric not null check (packs_per_order_unit > 0),
    order_unit text not null check (order_unit in ('PACK', 'CARTON')),
    stock_qty_unit text not null check (stock_qty_unit in ('PACK', 'ORDER_UNIT')),
    apicbase_uid text,
    apicbase_stock_item_name text,
    lead_time_calendar_days integer not null check (lead_time_calendar_days >= 0),
    shelf_life_anchor text
        check (shelf_life_anchor in ('ORDER_DATE', 'RECEIPT_DATE', 'LOT_EXPIRY')),
    yield_factor numeric not null check (yield_factor > 0),
    moq_order_units numeric not null check (moq_order_units >= 0),
    case_multiple_order_units numeric not null check (case_multiple_order_units > 0),
    data_status text not null,
    source_note text,
    primary key (version_id, item_id),
    foreign key (version_id, item_id)
        references public.items(version_id, item_id) on delete cascade
);

create table public.delivery_rules (
    version_id uuid not null,
    delivery_rule_id text not null,
    location_id text not null,
    ordering_channel text not null,
    storage_class text not null check (storage_class in ('TK', 'Kuehl', 'RT', 'Frisch')),
    delivery_weekday smallint check (delivery_weekday between 0 and 6),
    covered_service_weekdays smallint[] not null default '{}',
    order_weekday smallint check (order_weekday between 0 and 6),
    order_cutoff_local time,
    receipt_available_local time,
    review_period_days integer not null check (review_period_days > 0),
    effective_from date not null,
    effective_to date,
    active boolean not null default true,
    data_status text not null,
    source_note text,
    primary key (version_id, delivery_rule_id),
    foreign key (version_id, location_id)
        references public.locations(version_id, location_id) on delete cascade,
    check (effective_to is null or effective_to >= effective_from)
);

create table public.planning_runs (
    run_id text primary key,
    schema_version integer not null check (schema_version > 0),
    policy_profile text not null,
    policy_version text not null,
    run_mode text not null check (run_mode in ('fixture', 'scenario', 'shadow', 'production')),
    planning_as_of_at timestamptz not null,
    created_at timestamptz not null,
    input_hash text not null,
    config_hash text not null,
    code_version text not null,
    status text not null check (status in ('started', 'completed', 'blocked', 'failed')),
    master_data_version_id uuid references public.master_data_versions(id),
    created_by uuid references auth.users(id) on delete set null
);

create table public.planning_run_inputs (
    run_id text not null references public.planning_runs(run_id) on delete cascade,
    dataset text not null,
    source_version text not null,
    content_hash text not null,
    provenance text not null
        check (provenance in ('observed', 'manual', 'policy_default', 'empty_placeholder', 'unavailable')),
    record_count integer not null check (record_count >= 0),
    primary key (run_id, dataset)
);

create table public.planning_lines (
    planning_line_id text primary key,
    run_id text not null references public.planning_runs(run_id) on delete cascade,
    location_id text not null,
    item_id text not null,
    supplier_id text,
    schedule_rule_id text,
    order_date date not null,
    expected_delivery_date date not null,
    coverage_start_date date,
    coverage_end_date date,
    protection_days integer check (protection_days > 0),
    gross_requirement_g numeric not null check (gross_requirement_g >= 0),
    yield_factor numeric not null check (yield_factor > 0),
    yield_factor_provenance text not null,
    adjusted_requirement_g numeric not null check (adjusted_requirement_g >= 0),
    safety_stock_g numeric not null check (safety_stock_g >= 0),
    safety_stock_provenance text not null,
    usable_on_hand_g numeric not null check (usable_on_hand_g >= 0),
    open_po_due_g numeric not null check (open_po_due_g >= 0),
    raw_order_g numeric not null check (raw_order_g >= 0),
    shelf_life_cap_g numeric check (shelf_life_cap_g >= 0),
    max_cover_cap_g numeric check (max_cover_cap_g >= 0),
    capped_order_g numeric not null check (capped_order_g >= 0),
    order_unit_size_g numeric not null check (order_unit_size_g > 0),
    moq_order_units numeric not null check (moq_order_units >= 0),
    case_multiple_order_units numeric not null check (case_multiple_order_units > 0),
    proposed_order_units numeric not null check (proposed_order_units >= 0),
    rounding_delta_g numeric not null check (rounding_delta_g >= 0),
    data_status text not null,
    check (expected_delivery_date >= order_date),
    check (
        coverage_start_date is null
        or coverage_end_date is null
        or coverage_end_date >= coverage_start_date
    )
);

create index planning_lines_run_id_idx on public.planning_lines (run_id);
create index planning_lines_location_item_idx
    on public.planning_lines (location_id, item_id);

create table public.planning_recommendations (
    recommendation_id text primary key,
    planning_line_id text not null references public.planning_lines(planning_line_id) on delete cascade,
    run_id text not null references public.planning_runs(run_id) on delete cascade,
    location_id text not null,
    supplier_id text not null,
    item_id text not null,
    order_date date not null,
    expected_delivery_date date not null,
    proposed_qty_units numeric not null check (proposed_qty_units >= 0),
    check (expected_delivery_date >= order_date)
);

create index planning_recommendations_run_id_idx
    on public.planning_recommendations (run_id);

create table public.planning_exceptions (
    exception_id text primary key,
    run_id text not null references public.planning_runs(run_id) on delete cascade,
    planning_line_id text references public.planning_lines(planning_line_id) on delete set null,
    code text not null,
    severity text not null check (severity in ('info', 'warning', 'blocker')),
    dataset text,
    record_ref text,
    message text not null,
    remedy text not null
);

create index planning_exceptions_run_id_idx on public.planning_exceptions (run_id);

alter table public.master_data_versions enable row level security;
alter table public.locations enable row level security;
alter table public.items enable row level security;
alter table public.item_policy_overrides enable row level security;
alter table public.delivery_rules enable row level security;
alter table public.planning_runs enable row level security;
alter table public.planning_run_inputs enable row level security;
alter table public.planning_lines enable row level security;
alter table public.planning_recommendations enable row level security;
alter table public.planning_exceptions enable row level security;

revoke all on public.master_data_versions from anon, authenticated;
revoke all on public.locations from anon, authenticated;
revoke all on public.items from anon, authenticated;
revoke all on public.item_policy_overrides from anon, authenticated;
revoke all on public.delivery_rules from anon, authenticated;
revoke all on public.planning_runs from anon, authenticated;
revoke all on public.planning_run_inputs from anon, authenticated;
revoke all on public.planning_lines from anon, authenticated;
revoke all on public.planning_recommendations from anon, authenticated;
revoke all on public.planning_exceptions from anon, authenticated;

comment on table public.master_data_versions is
    'Version headers for application-maintained Phase 2 master data and rules.';
comment on table public.planning_recommendations is
    'Internal calculated proposals; never evidence of a placed supplier order.';
