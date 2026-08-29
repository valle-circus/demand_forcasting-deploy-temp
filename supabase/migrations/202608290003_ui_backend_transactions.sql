-- Transaction and immutability helpers for the connected FastAPI backend.
-- Run this once in the Supabase SQL Editor after migrations 001 and 002.
-- Browser roles remain denied; only the server-side service role may call the RPCs.

begin;

do $$
begin
    if to_regclass('public.planning_projection_days') is null
        or to_regclass('public.source_imports') is null
    then
        raise exception
            'Missing workflow tables. Apply migrations 001 and 002 before this migration.';
    end if;
end
$$;

create function public.reject_active_master_child_mutation_v1()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    affected_version_id uuid;
begin
    if tg_op = 'DELETE' then
        affected_version_id := old.version_id;
    else
        affected_version_id := new.version_id;
    end if;

    if exists (
        select 1
        from public.master_data_versions
        where id = affected_version_id
          and status = 'active'
    ) then
        raise exception 'Active master-data versions are immutable; create a new draft version.';
    end if;

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end
$$;

create trigger locations_reject_active_mutation
before insert or update or delete on public.locations
for each row execute function public.reject_active_master_child_mutation_v1();

create trigger items_reject_active_mutation
before insert or update or delete on public.items
for each row execute function public.reject_active_master_child_mutation_v1();

create trigger item_policy_overrides_reject_active_mutation
before insert or update or delete on public.item_policy_overrides
for each row execute function public.reject_active_master_child_mutation_v1();

create trigger delivery_rules_reject_active_mutation
before insert or update or delete on public.delivery_rules
for each row execute function public.reject_active_master_child_mutation_v1();

create function public.reject_accepted_source_import_mutation_v1()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    if old.status in ('accepted', 'accepted_with_warnings', 'rejected') then
        raise exception 'Finalized source imports are immutable; upload a new version.';
    end if;
    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end
$$;

create trigger source_imports_reject_finalized_mutation
before update or delete on public.source_imports
for each row execute function public.reject_accepted_source_import_mutation_v1();

create function public.reject_accepted_source_child_mutation_v1()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    affected_import_id uuid;
begin
    if tg_op = 'DELETE' then
        affected_import_id := old.import_id;
    else
        affected_import_id := new.import_id;
    end if;

    if exists (
        select 1
        from public.source_imports
        where id = affected_import_id
          and status in ('accepted', 'accepted_with_warnings', 'rejected')
    ) then
        raise exception 'Finalized normalized source rows are immutable; upload a new version.';
    end if;

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end
$$;

create trigger forecast_daily_reject_finalized_mutation
before insert or update or delete on public.forecast_daily
for each row execute function public.reject_accepted_source_child_mutation_v1();

create trigger menu_calendar_reject_finalized_mutation
before insert or update or delete on public.menu_calendar
for each row execute function public.reject_accepted_source_child_mutation_v1();

create trigger bom_lines_reject_finalized_mutation
before insert or update or delete on public.bom_lines
for each row execute function public.reject_accepted_source_child_mutation_v1();

create trigger inventory_snapshots_reject_finalized_mutation
before insert or update or delete on public.inventory_snapshots
for each row execute function public.reject_accepted_source_child_mutation_v1();

create trigger purchase_order_lines_reject_finalized_mutation
before insert or update or delete on public.purchase_order_lines
for each row execute function public.reject_accepted_source_child_mutation_v1();

create function public.persist_master_import_v1(p_payload jsonb)
returns public.source_imports
language plpgsql
set search_path = public
as $$
declare
    source_payload jsonb;
    version_payload jsonb;
    persisted_source public.source_imports;
    final_status text;
begin
    source_payload := p_payload -> 'source_import';
    version_payload := p_payload -> 'master_data_version';
    final_status := p_payload ->> 'final_status';
    if jsonb_typeof(source_payload) <> 'object'
        or jsonb_typeof(version_payload) <> 'object'
        or source_payload ->> 'dataset_type' <> 'master_data'
        or source_payload ->> 'status' <> 'validating'
        or final_status is null
        or final_status not in ('accepted', 'accepted_with_warnings')
    then
        raise exception 'Invalid master-data import transaction payload.';
    end if;

    insert into public.source_imports
    select * from jsonb_populate_record(null::public.source_imports, source_payload);

    insert into public.master_data_versions
    select * from jsonb_populate_record(
        null::public.master_data_versions,
        version_payload
    );

    insert into public.locations
    select * from jsonb_populate_recordset(
        null::public.locations,
        coalesce(p_payload -> 'locations', '[]'::jsonb)
    );
    insert into public.items
    select * from jsonb_populate_recordset(
        null::public.items,
        coalesce(p_payload -> 'items', '[]'::jsonb)
    );
    insert into public.item_policy_overrides
    select * from jsonb_populate_recordset(
        null::public.item_policy_overrides,
        coalesce(p_payload -> 'item_policy_overrides', '[]'::jsonb)
    );
    insert into public.delivery_rules
    select * from jsonb_populate_recordset(
        null::public.delivery_rules,
        coalesce(p_payload -> 'delivery_rules', '[]'::jsonb)
    );

    update public.source_imports
    set status = final_status
    where id = (source_payload ->> 'id')::uuid
    returning * into persisted_source;
    return persisted_source;
end
$$;

create function public.persist_source_import_v1(p_payload jsonb)
returns public.source_imports
language plpgsql
set search_path = public
as $$
declare
    source_payload jsonb;
    dataset_type text;
    final_status text;
    persisted_source public.source_imports;
begin
    source_payload := p_payload -> 'source_import';
    dataset_type := source_payload ->> 'dataset_type';
    final_status := p_payload ->> 'final_status';
    if jsonb_typeof(source_payload) <> 'object'
        or source_payload ->> 'status' <> 'validating'
        or dataset_type is null
        or dataset_type not in ('planning_input', 'stock', 'purchase_orders')
        or final_status is null
        or final_status not in ('accepted', 'accepted_with_warnings')
    then
        raise exception 'Invalid source-import transaction payload.';
    end if;

    insert into public.source_imports
    select * from jsonb_populate_record(null::public.source_imports, source_payload);

    if dataset_type = 'planning_input' then
        insert into public.forecast_daily
        select * from jsonb_populate_recordset(
            null::public.forecast_daily,
            coalesce(p_payload -> 'forecast_daily', '[]'::jsonb)
        );
        insert into public.menu_calendar
        select * from jsonb_populate_recordset(
            null::public.menu_calendar,
            coalesce(p_payload -> 'menu_calendar', '[]'::jsonb)
        );
        insert into public.bom_lines
        select * from jsonb_populate_recordset(
            null::public.bom_lines,
            coalesce(p_payload -> 'bom_lines', '[]'::jsonb)
        );
    elsif dataset_type = 'stock' then
        insert into public.inventory_snapshots
        select * from jsonb_populate_recordset(
            null::public.inventory_snapshots,
            coalesce(p_payload -> 'inventory_snapshots', '[]'::jsonb)
        );
    elsif dataset_type = 'purchase_orders' then
        insert into public.purchase_order_lines
        select * from jsonb_populate_recordset(
            null::public.purchase_order_lines,
            coalesce(p_payload -> 'purchase_order_lines', '[]'::jsonb)
        );
    end if;

    update public.source_imports
    set status = final_status
    where id = (source_payload ->> 'id')::uuid
    returning * into persisted_source;
    return persisted_source;
end
$$;

create function public.activate_master_data_version_v1(
    p_version_id uuid,
    p_actor_id uuid,
    p_environment text default 'prototype'
)
returns public.master_data_versions
language plpgsql
set search_path = public
as $$
declare
    target_version public.master_data_versions;
begin
    select *
    into target_version
    from public.master_data_versions
    where id = p_version_id
    for update;

    if not found then
        raise exception 'Master-data version % was not found.', p_version_id;
    end if;
    if target_version.environment <> p_environment then
        raise exception 'Master-data version belongs to a different environment.';
    end if;
    if target_version.status = 'archived' then
        raise exception 'Archived master-data versions cannot be activated.';
    end if;
    if target_version.status = 'active' then
        return target_version;
    end if;

    update public.master_data_versions
    set status = 'archived'
    where environment = p_environment
      and status = 'active'
      and id <> p_version_id;

    update public.master_data_versions
    set status = 'active',
        activated_at = now(),
        activated_by = p_actor_id
    where id = p_version_id
    returning * into target_version;

    return target_version;
end
$$;

create function public.persist_planning_run_v1(p_payload jsonb)
returns text
language plpgsql
set search_path = public
as $$
declare
    run_payload jsonb;
    requested_run_id text;
    requested_input_hash text;
    existing_input_hash text;
begin
    if jsonb_typeof(p_payload) <> 'object' then
        raise exception 'Planning persistence payload must be a JSON object.';
    end if;

    run_payload := p_payload -> 'run';
    if jsonb_typeof(run_payload) <> 'object' then
        raise exception 'Planning persistence payload is missing run metadata.';
    end if;

    requested_run_id := run_payload ->> 'run_id';
    requested_input_hash := run_payload ->> 'input_hash';
    if requested_run_id is null or requested_input_hash is null then
        raise exception 'Planning run_id and input_hash are required.';
    end if;

    select input_hash
    into existing_input_hash
    from public.planning_runs
    where run_id = requested_run_id;

    if found then
        if existing_input_hash <> requested_input_hash then
            raise exception 'Existing run_id has a different input hash.';
        end if;
        return requested_run_id;
    end if;

    insert into public.planning_runs
    select *
    from jsonb_populate_record(null::public.planning_runs, run_payload);

    insert into public.planning_run_inputs
    select *
    from jsonb_populate_recordset(
        null::public.planning_run_inputs,
        coalesce(p_payload -> 'run_inputs', '[]'::jsonb)
    );

    insert into public.planning_lines
    select *
    from jsonb_populate_recordset(
        null::public.planning_lines,
        coalesce(p_payload -> 'planning_lines', '[]'::jsonb)
    );

    insert into public.planning_recommendations
    select *
    from jsonb_populate_recordset(
        null::public.planning_recommendations,
        coalesce(p_payload -> 'recommendations', '[]'::jsonb)
    );

    insert into public.planning_exceptions
    select *
    from jsonb_populate_recordset(
        null::public.planning_exceptions,
        coalesce(p_payload -> 'exceptions', '[]'::jsonb)
    );

    insert into public.planning_netting_results
    select *
    from jsonb_populate_recordset(
        null::public.planning_netting_results,
        coalesce(p_payload -> 'netting_results', '[]'::jsonb)
    );

    insert into public.planning_projection_days
    select *
    from jsonb_populate_recordset(
        null::public.planning_projection_days,
        coalesce(p_payload -> 'projection_days', '[]'::jsonb)
    );

    return requested_run_id;
end
$$;

revoke all on function public.reject_active_master_child_mutation_v1() from public;
revoke all on function public.reject_accepted_source_import_mutation_v1() from public;
revoke all on function public.reject_accepted_source_child_mutation_v1() from public;
revoke all on function public.activate_master_data_version_v1(uuid, uuid, text)
    from public, anon, authenticated;
revoke all on function public.persist_master_import_v1(jsonb)
    from public, anon, authenticated;
revoke all on function public.persist_planning_run_v1(jsonb)
    from public, anon, authenticated;
revoke all on function public.persist_source_import_v1(jsonb)
    from public, anon, authenticated;

grant execute on function public.activate_master_data_version_v1(uuid, uuid, text)
    to service_role;
grant execute on function public.persist_master_import_v1(jsonb)
    to service_role;
grant execute on function public.persist_planning_run_v1(jsonb)
    to service_role;
grant execute on function public.persist_source_import_v1(jsonb)
    to service_role;

comment on function public.activate_master_data_version_v1(uuid, uuid, text) is
    'Atomically archives the previous active master version and activates one validated draft.';
comment on function public.persist_planning_run_v1(jsonb) is
    'Atomically persists one deterministic planning run and every canonical result row.';
comment on function public.persist_master_import_v1(jsonb) is
    'Atomically persists one immutable draft master-data source version and normalized rows.';
comment on function public.persist_source_import_v1(jsonb) is
    'Atomically persists one immutable accepted planning, stock, or purchase-order source version.';

commit;
