-- Private-by-default user workspaces and end-to-end planning-data isolation.
--
-- Apply after migration 007. Existing planning rows are assigned from their
-- audit actor; the migration aborts instead of guessing when a populated root
-- row has no attributable user. Browser roles remain denied. The FastAPI
-- workspace-scoped repository adds the same boundary to every server-authority
-- read and write.

begin;

create table public.workspaces (
    id uuid primary key default gen_random_uuid(),
    workspace_name text not null,
    workspace_kind text not null default 'private'
        check (workspace_kind in ('private', 'shared', 'seed')),
    created_at timestamptz not null default now(),
    created_by uuid references auth.users(id) on delete set null
);

create table public.app_user_profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    system_role text not null default 'user'
        check (system_role in ('user', 'system_admin')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.workspace_memberships (
    workspace_id uuid not null references public.workspaces(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null check (role in ('owner', 'admin', 'planner', 'viewer')),
    status text not null default 'active'
        check (status in ('active', 'revoked')),
    is_default boolean not null default false,
    created_at timestamptz not null default now(),
    created_by uuid references auth.users(id) on delete set null,
    primary key (workspace_id, user_id)
);

create unique index workspace_memberships_one_default_per_user
    on public.workspace_memberships (user_id)
    where is_default and status = 'active';

create table public.user_location_access (
    workspace_id uuid not null,
    user_id uuid not null,
    location_id text not null,
    access_level text not null check (access_level in ('viewer', 'planner')),
    created_at timestamptz not null default now(),
    created_by uuid references auth.users(id) on delete set null,
    primary key (workspace_id, user_id, location_id),
    foreign key (workspace_id, user_id)
        references public.workspace_memberships(workspace_id, user_id)
        on delete cascade
);

create function public.provision_private_workspace_for_user_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    private_workspace_id uuid := gen_random_uuid();
begin
    insert into public.workspaces (
        id,
        workspace_name,
        workspace_kind,
        created_by
    ) values (
        private_workspace_id,
        'Private planning workspace',
        'private',
        new.id
    );
    insert into public.app_user_profiles (user_id)
    values (new.id);
    insert into public.workspace_memberships (
        workspace_id,
        user_id,
        role,
        status,
        is_default,
        created_by
    ) values (
        private_workspace_id,
        new.id,
        'owner',
        'active',
        true,
        new.id
    );
    return new;
end
$$;

-- Prevent an account from being inserted between the existing-user backfill
-- and trigger installation. Sign-up resumes when this migration commits.
lock table auth.users in share row exclusive mode;

-- Provision every existing Auth account before assigning legacy rows.
do $$
declare
    existing_user record;
    private_workspace_id uuid;
begin
    for existing_user in
        select id from auth.users order by created_at, id
    loop
        if not exists (
            select 1
            from public.app_user_profiles
            where user_id = existing_user.id
        ) then
            private_workspace_id := gen_random_uuid();
            insert into public.workspaces (
                id,
                workspace_name,
                workspace_kind,
                created_by
            ) values (
                private_workspace_id,
                'Private planning workspace',
                'private',
                existing_user.id
            );
            insert into public.app_user_profiles (user_id)
            values (existing_user.id);
            insert into public.workspace_memberships (
                workspace_id,
                user_id,
                role,
                status,
                is_default,
                created_by
            ) values (
                private_workspace_id,
                existing_user.id,
                'owner',
                'active',
                true,
                existing_user.id
            );
        end if;
    end loop;
end
$$;

drop trigger if exists provision_private_workspace_for_user on auth.users;
create trigger provision_private_workspace_for_user
after insert on auth.users
for each row execute function public.provision_private_workspace_for_user_v1();

-- Add a workspace discriminator to every persisted planning relation. Keeping
-- it on child rows makes both PostgREST filters and same-workspace FKs explicit.
alter table public.master_data_versions add column workspace_id uuid;
alter table public.locations add column workspace_id uuid;
alter table public.items add column workspace_id uuid;
alter table public.item_policy_overrides add column workspace_id uuid;
alter table public.delivery_rules add column workspace_id uuid;
alter table public.source_imports add column workspace_id uuid;
alter table public.forecast_daily add column workspace_id uuid;
alter table public.menu_calendar add column workspace_id uuid;
alter table public.bom_lines add column workspace_id uuid;
alter table public.inventory_snapshots add column workspace_id uuid;
alter table public.purchase_order_lines add column workspace_id uuid;
alter table public.planning_runs add column workspace_id uuid;
alter table public.planning_run_inputs add column workspace_id uuid;
alter table public.planning_lines add column workspace_id uuid;
alter table public.planning_recommendations add column workspace_id uuid;
alter table public.planning_exceptions add column workspace_id uuid;
alter table public.planning_netting_results add column workspace_id uuid;
alter table public.planning_projection_days add column workspace_id uuid;

update public.master_data_versions target
set workspace_id = membership.workspace_id
from public.workspace_memberships membership
where membership.user_id = target.created_by
  and membership.is_default
  and membership.status = 'active';

update public.source_imports target
set workspace_id = membership.workspace_id
from public.workspace_memberships membership
where membership.user_id = target.created_by
  and membership.is_default
  and membership.status = 'active';

update public.planning_runs target
set workspace_id = membership.workspace_id
from public.workspace_memberships membership
where membership.user_id = target.created_by
  and membership.is_default
  and membership.status = 'active';

do $$
begin
    if exists (select 1 from public.master_data_versions where workspace_id is null)
        or exists (select 1 from public.source_imports where workspace_id is null)
        or exists (select 1 from public.planning_runs where workspace_id is null)
    then
        raise exception
            'Workspace backfill cannot attribute every existing master, import and run. Repair audit actors before applying migration 008.';
    end if;
end
$$;

update public.locations child
set workspace_id = parent.workspace_id
from public.master_data_versions parent
where parent.id = child.version_id;
update public.items child
set workspace_id = parent.workspace_id
from public.master_data_versions parent
where parent.id = child.version_id;
update public.item_policy_overrides child
set workspace_id = parent.workspace_id
from public.master_data_versions parent
where parent.id = child.version_id;
update public.delivery_rules child
set workspace_id = parent.workspace_id
from public.master_data_versions parent
where parent.id = child.version_id;

update public.forecast_daily child
set workspace_id = parent.workspace_id
from public.source_imports parent
where parent.id = child.import_id;
update public.menu_calendar child
set workspace_id = parent.workspace_id
from public.source_imports parent
where parent.id = child.import_id;
update public.bom_lines child
set workspace_id = parent.workspace_id
from public.source_imports parent
where parent.id = child.import_id;
update public.inventory_snapshots child
set workspace_id = parent.workspace_id
from public.source_imports parent
where parent.id = child.import_id;
update public.purchase_order_lines child
set workspace_id = parent.workspace_id
from public.source_imports parent
where parent.id = child.import_id;

update public.planning_run_inputs child
set workspace_id = parent.workspace_id
from public.planning_runs parent
where parent.run_id = child.run_id;
update public.planning_lines child
set workspace_id = parent.workspace_id
from public.planning_runs parent
where parent.run_id = child.run_id;
update public.planning_recommendations child
set workspace_id = parent.workspace_id
from public.planning_runs parent
where parent.run_id = child.run_id;
update public.planning_exceptions child
set workspace_id = parent.workspace_id
from public.planning_runs parent
where parent.run_id = child.run_id;
update public.planning_netting_results child
set workspace_id = parent.workspace_id
from public.planning_runs parent
where parent.run_id = child.run_id;
update public.planning_projection_days child
set workspace_id = parent.workspace_id
from public.planning_runs parent
where parent.run_id = child.run_id;

alter table public.master_data_versions alter column workspace_id set not null;
alter table public.locations alter column workspace_id set not null;
alter table public.items alter column workspace_id set not null;
alter table public.item_policy_overrides alter column workspace_id set not null;
alter table public.delivery_rules alter column workspace_id set not null;
alter table public.source_imports alter column workspace_id set not null;
alter table public.forecast_daily alter column workspace_id set not null;
alter table public.menu_calendar alter column workspace_id set not null;
alter table public.bom_lines alter column workspace_id set not null;
alter table public.inventory_snapshots alter column workspace_id set not null;
alter table public.purchase_order_lines alter column workspace_id set not null;
alter table public.planning_runs alter column workspace_id set not null;
alter table public.planning_run_inputs alter column workspace_id set not null;
alter table public.planning_lines alter column workspace_id set not null;
alter table public.planning_recommendations alter column workspace_id set not null;
alter table public.planning_exceptions alter column workspace_id set not null;
alter table public.planning_netting_results alter column workspace_id set not null;
alter table public.planning_projection_days alter column workspace_id set not null;

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'master_data_versions', 'locations', 'items', 'item_policy_overrides',
        'delivery_rules', 'source_imports', 'forecast_daily', 'menu_calendar',
        'bom_lines', 'inventory_snapshots', 'purchase_order_lines',
        'planning_runs', 'planning_run_inputs', 'planning_lines',
        'planning_recommendations', 'planning_exceptions',
        'planning_netting_results', 'planning_projection_days'
    ]
    loop
        execute format(
            'alter table public.%I add constraint %I foreign key (workspace_id) references public.workspaces(id)',
            table_name,
            table_name || '_workspace_id_fkey'
        );
        execute format(
            'create index %I on public.%I (workspace_id)',
            table_name || '_workspace_id_idx',
            table_name
        );
    end loop;
end
$$;

-- Existing identifiers remain globally unique, while these additional keys let
-- child FKs prove that parent and child belong to the same workspace.
alter table public.master_data_versions
    add unique (workspace_id, id);
alter table public.source_imports
    add unique (workspace_id, id);
alter table public.planning_runs
    add unique (workspace_id, run_id);
alter table public.planning_lines
    add unique (workspace_id, planning_line_id);
alter table public.locations
    add unique (workspace_id, version_id, location_id);
alter table public.planning_netting_results
    add unique (workspace_id, run_id, location_id, item_id);

alter table public.source_imports
    add foreign key (workspace_id, supersedes_import_id)
        references public.source_imports(workspace_id, id);
alter table public.master_data_versions
    add foreign key (workspace_id, source_import_id)
        references public.source_imports(workspace_id, id);
alter table public.planning_runs
    add foreign key (workspace_id, master_data_version_id)
        references public.master_data_versions(workspace_id, id);
alter table public.planning_run_inputs
    add foreign key (workspace_id, source_import_id)
        references public.source_imports(workspace_id, id);

alter table public.locations
    add foreign key (workspace_id, version_id)
        references public.master_data_versions(workspace_id, id);
alter table public.items
    add foreign key (workspace_id, version_id)
        references public.master_data_versions(workspace_id, id);
alter table public.item_policy_overrides
    add foreign key (workspace_id, version_id)
        references public.master_data_versions(workspace_id, id);
alter table public.delivery_rules
    add foreign key (workspace_id, version_id, location_id)
        references public.locations(workspace_id, version_id, location_id);

alter table public.forecast_daily
    add foreign key (workspace_id, import_id)
        references public.source_imports(workspace_id, id);
alter table public.menu_calendar
    add foreign key (workspace_id, import_id)
        references public.source_imports(workspace_id, id);
alter table public.bom_lines
    add foreign key (workspace_id, import_id)
        references public.source_imports(workspace_id, id);
alter table public.inventory_snapshots
    add foreign key (workspace_id, import_id)
        references public.source_imports(workspace_id, id);
alter table public.purchase_order_lines
    add foreign key (workspace_id, import_id)
        references public.source_imports(workspace_id, id);

alter table public.planning_run_inputs
    add foreign key (workspace_id, run_id)
        references public.planning_runs(workspace_id, run_id);
alter table public.planning_lines
    add foreign key (workspace_id, run_id)
        references public.planning_runs(workspace_id, run_id);
alter table public.planning_recommendations
    add foreign key (workspace_id, run_id)
        references public.planning_runs(workspace_id, run_id);
alter table public.planning_recommendations
    add foreign key (workspace_id, planning_line_id)
        references public.planning_lines(workspace_id, planning_line_id);
alter table public.planning_exceptions
    add foreign key (workspace_id, run_id)
        references public.planning_runs(workspace_id, run_id);
alter table public.planning_netting_results
    add foreign key (workspace_id, run_id)
        references public.planning_runs(workspace_id, run_id);
alter table public.planning_projection_days
    add foreign key (workspace_id, run_id, location_id, item_id)
        references public.planning_netting_results(
            workspace_id,
            run_id,
            location_id,
            item_id
        );

-- Existing rows must also satisfy the location half of the new boundary.
-- Triggers below protect future transaction payloads; this check prevents a
-- migration from silently preserving an already-inconsistent relationship.
do $$
begin
    if exists (
        select 1
        from public.inventory_snapshots child
        join public.source_imports source on source.id = child.import_id
        where child.workspace_id <> source.workspace_id
           or child.location_id <> source.location_id
           or source.dataset_type <> 'stock'
    ) or exists (
        select 1
        from public.purchase_order_lines child
        join public.source_imports source on source.id = child.import_id
        where child.workspace_id <> source.workspace_id
           or child.location_id <> source.location_id
           or source.dataset_type <> 'purchase_orders'
    ) or exists (
        select 1
        from public.planning_lines child
        join public.planning_runs run on run.run_id = child.run_id
        where child.workspace_id <> run.workspace_id
           or child.location_id <> run.location_id
    ) or exists (
        select 1
        from public.planning_recommendations child
        join public.planning_runs run on run.run_id = child.run_id
        where child.workspace_id <> run.workspace_id
           or child.location_id <> run.location_id
    ) or exists (
        select 1
        from public.planning_netting_results child
        join public.planning_runs run on run.run_id = child.run_id
        where child.workspace_id <> run.workspace_id
           or child.location_id <> run.location_id
    ) or exists (
        select 1
        from public.planning_projection_days child
        join public.planning_runs run on run.run_id = child.run_id
        where child.workspace_id <> run.workspace_id
           or child.location_id <> run.location_id
    ) then
        raise exception
            'Existing location-scoped rows do not match their import or run. Repair them before applying migration 008.';
    end if;
end
$$;

alter table public.master_data_versions
    drop constraint master_data_versions_environment_version_label_key;
alter table public.master_data_versions
    add unique (workspace_id, environment, version_label);
drop index public.master_data_versions_one_active_per_environment;
create unique index master_data_versions_one_active_per_workspace_environment
    on public.master_data_versions (workspace_id, environment)
    where status = 'active';

create function public.user_can_admin_workspace_v1(
    p_user_id uuid,
    p_workspace_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.app_user_profiles profile
        join public.workspace_memberships membership
          on membership.user_id = profile.user_id
        where profile.user_id = p_user_id
          and membership.workspace_id = p_workspace_id
          and membership.status = 'active'
          and (
              profile.system_role = 'system_admin'
              or membership.role in ('owner', 'admin')
          )
    );
$$;

create function public.user_can_access_location_v1(
    p_user_id uuid,
    p_workspace_id uuid,
    p_location_id text,
    p_require_write boolean default false
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.app_user_profiles profile
        join public.workspace_memberships membership
          on membership.user_id = profile.user_id
         and membership.workspace_id = p_workspace_id
        where profile.user_id = p_user_id
          and membership.status = 'active'
          and exists (
              select 1
              from public.locations location
              join public.master_data_versions version
                on version.id = location.version_id
               and version.workspace_id = location.workspace_id
              where location.workspace_id = p_workspace_id
                and location.location_id = p_location_id
                and location.active
                and version.status = 'active'
          )
          and (
              profile.system_role = 'system_admin'
              or membership.role in ('owner', 'admin')
              or exists (
                  select 1
                  from public.user_location_access location_access
                  where location_access.workspace_id = p_workspace_id
                    and location_access.user_id = p_user_id
                    and location_access.location_id = p_location_id
                    and (
                        not p_require_write
                        or location_access.access_level = 'planner'
                    )
              )
          )
          and (
              not p_require_write
              or profile.system_role = 'system_admin'
              or membership.role <> 'viewer'
          )
    );
$$;

create function public.validate_master_workspace_actor_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if exists (
        select 1 from public.workspaces
        where id = new.workspace_id and workspace_kind = 'seed'
    ) and new.created_by is null then
        return new;
    end if;
    if new.created_by is null
        or not public.user_can_admin_workspace_v1(
            new.created_by,
            new.workspace_id
        )
    then
        raise exception 'Actor cannot manage master data in this workspace.'
            using errcode = 'insufficient_privilege';
    end if;
    return new;
end
$$;

create function public.validate_source_import_workspace_actor_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if exists (
        select 1 from public.workspaces
        where id = new.workspace_id and workspace_kind = 'seed'
    ) and new.created_by is null then
        return new;
    end if;
    if new.created_by is null then
        raise exception 'Source import requires an audit actor.'
            using errcode = 'insufficient_privilege';
    end if;
    if new.dataset_type in ('master_data', 'planning_input') then
        if not public.user_can_admin_workspace_v1(new.created_by, new.workspace_id) then
            raise exception 'Actor cannot manage workspace-wide planning inputs.'
                using errcode = 'insufficient_privilege';
        end if;
    elsif new.location_id is null
        or not public.user_can_access_location_v1(
            new.created_by,
            new.workspace_id,
            new.location_id,
            true
        )
    then
        raise exception 'Actor cannot import data for this location.'
            using errcode = 'insufficient_privilege';
    end if;
    return new;
end
$$;

create function public.validate_planning_run_workspace_actor_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if exists (
        select 1 from public.workspaces
        where id = new.workspace_id and workspace_kind = 'seed'
    ) and new.created_by is null then
        return new;
    end if;
    if new.created_by is null
        or not public.user_can_access_location_v1(
            new.created_by,
            new.workspace_id,
            new.location_id,
            true
        )
    then
        raise exception 'Actor cannot run planning for this location.'
            using errcode = 'insufficient_privilege';
    end if;
    return new;
end
$$;

create trigger master_data_versions_validate_workspace_actor
before insert on public.master_data_versions
for each row execute function public.validate_master_workspace_actor_v1();
create trigger source_imports_validate_workspace_actor
before insert on public.source_imports
for each row execute function public.validate_source_import_workspace_actor_v1();
create trigger planning_runs_validate_workspace_actor
before insert on public.planning_runs
for each row execute function public.validate_planning_run_workspace_actor_v1();

create function public.validate_location_scoped_import_child_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if not exists (
        select 1
        from public.source_imports source
        where source.id = new.import_id
          and source.workspace_id = new.workspace_id
          and source.location_id = new.location_id
          and source.dataset_type in ('stock', 'purchase_orders')
    ) then
        raise exception 'Imported row does not match its workspace and source location.'
            using errcode = 'insufficient_privilege';
    end if;
    return new;
end
$$;

create trigger inventory_snapshots_validate_source_location
before insert on public.inventory_snapshots
for each row execute function public.validate_location_scoped_import_child_v1();
create trigger purchase_order_lines_validate_source_location
before insert on public.purchase_order_lines
for each row execute function public.validate_location_scoped_import_child_v1();

create function public.validate_planning_run_child_location_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if not exists (
        select 1
        from public.planning_runs run
        where run.run_id = new.run_id
          and run.workspace_id = new.workspace_id
          and run.location_id = new.location_id
    ) then
        raise exception 'Planning result row does not match its workspace and run location.'
            using errcode = 'insufficient_privilege';
    end if;
    return new;
end
$$;

create trigger planning_lines_validate_run_location
before insert on public.planning_lines
for each row execute function public.validate_planning_run_child_location_v1();
create trigger planning_recommendations_validate_run_location
before insert on public.planning_recommendations
for each row execute function public.validate_planning_run_child_location_v1();
create trigger planning_netting_results_validate_run_location
before insert on public.planning_netting_results
for each row execute function public.validate_planning_run_child_location_v1();
create trigger planning_projection_days_validate_run_location
before insert on public.planning_projection_days
for each row execute function public.validate_planning_run_child_location_v1();

-- Replace the already-applied activation helper so activation and archival are
-- workspace-local and the actor is checked again inside the database.
create or replace function public.activate_master_data_version_v1(
    p_version_id uuid,
    p_actor_id uuid,
    p_environment text default 'prototype'
)
returns public.master_data_versions
language plpgsql
security definer
set search_path = ''
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
    if not public.user_can_admin_workspace_v1(
        p_actor_id,
        target_version.workspace_id
    ) then
        raise exception 'Actor cannot activate master data in this workspace.'
            using errcode = 'insufficient_privilege';
    end if;
    if target_version.status = 'archived' then
        raise exception 'Archived master-data versions cannot be activated.';
    end if;
    if target_version.status = 'active' then
        return target_version;
    end if;

    update public.master_data_versions
    set status = 'archived'
    where workspace_id = target_version.workspace_id
      and environment = p_environment
      and status = 'active'
      and id <> p_version_id;

    update public.master_data_versions
    set status = 'active',
        activated_at = now(),
        activated_by = p_actor_id
    where workspace_id = target_version.workspace_id
      and id = p_version_id
    returning * into target_version;

    return target_version;
end
$$;

alter table public.workspaces enable row level security;
alter table public.app_user_profiles enable row level security;
alter table public.workspace_memberships enable row level security;
alter table public.user_location_access enable row level security;

revoke all on public.workspaces from anon, authenticated;
revoke all on public.app_user_profiles from anon, authenticated;
revoke all on public.workspace_memberships from anon, authenticated;
revoke all on public.user_location_access from anon, authenticated;

revoke all on function public.provision_private_workspace_for_user_v1()
    from public, anon, authenticated;
revoke all on function public.user_can_admin_workspace_v1(uuid, uuid)
    from public, anon, authenticated;
revoke all on function public.user_can_access_location_v1(uuid, uuid, text, boolean)
    from public, anon, authenticated;
revoke all on function public.validate_master_workspace_actor_v1()
    from public, anon, authenticated;
revoke all on function public.validate_source_import_workspace_actor_v1()
    from public, anon, authenticated;
revoke all on function public.validate_planning_run_workspace_actor_v1()
    from public, anon, authenticated;
revoke all on function public.validate_location_scoped_import_child_v1()
    from public, anon, authenticated;
revoke all on function public.validate_planning_run_child_location_v1()
    from public, anon, authenticated;

comment on table public.workspaces is
    'Private-by-default authorization boundary. Email domain membership never grants workspace access.';
comment on table public.workspace_memberships is
    'Explicit user membership and role for one planning workspace.';
comment on table public.user_location_access is
    'Location grants for planner/viewer members; owners and workspace admins have workspace-wide location access.';

commit;
