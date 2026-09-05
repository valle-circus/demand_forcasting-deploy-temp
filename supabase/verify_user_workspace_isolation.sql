-- Read-only post-migration reconciliation for migration 008.
-- Run in the Supabase SQL Editor after applying the migration. This script
-- changes no data. Review every result set before reopening multi-user tests.

-- Each Auth user should have exactly one active default membership. Existing
-- planning rows should appear only beside their recorded owner; newly created
-- colleague workspaces should have zeroes until that user uploads their data.
with import_counts as (
    select workspace_id, count(*) as source_imports
    from public.source_imports
    group by workspace_id
), master_counts as (
    select workspace_id, count(*) as master_versions
    from public.master_data_versions
    group by workspace_id
), run_counts as (
    select workspace_id, count(*) as planning_runs
    from public.planning_runs
    group by workspace_id
)
select
    auth_user.email,
    membership.workspace_id,
    membership.role,
    membership.status,
    membership.is_default,
    coalesce(import_counts.source_imports, 0) as source_imports,
    coalesce(master_counts.master_versions, 0) as master_versions,
    coalesce(run_counts.planning_runs, 0) as planning_runs
from auth.users auth_user
left join public.workspace_memberships membership
  on membership.user_id = auth_user.id
left join import_counts
  on import_counts.workspace_id = membership.workspace_id
left join master_counts
  on master_counts.workspace_id = membership.workspace_id
left join run_counts
  on run_counts.workspace_id = membership.workspace_id
order by auth_user.created_at, membership.workspace_id;

-- Every anomaly count below must be zero.
select 'users_without_one_active_default_workspace' as check_name, count(*) as anomalies
from (
    select auth_user.id
    from auth.users auth_user
    left join public.workspace_memberships membership
      on membership.user_id = auth_user.id
     and membership.status = 'active'
     and membership.is_default
    group by auth_user.id
    having count(membership.workspace_id) <> 1
) anomaly
union all
select 'source_import_actor_workspace_mismatch', count(*)
from public.source_imports source
where not exists (
    select 1
    from public.workspace_memberships membership
    where membership.user_id = source.created_by
      and membership.workspace_id = source.workspace_id
      and membership.status = 'active'
)
union all
select 'master_actor_workspace_mismatch', count(*)
from public.master_data_versions version
where not exists (
    select 1
    from public.workspace_memberships membership
    where membership.user_id = version.created_by
      and membership.workspace_id = version.workspace_id
      and membership.status = 'active'
)
union all
select 'run_actor_workspace_mismatch', count(*)
from public.planning_runs run
where not exists (
    select 1
    from public.workspace_memberships membership
    where membership.user_id = run.created_by
      and membership.workspace_id = run.workspace_id
      and membership.status = 'active'
)
union all
select 'stock_location_mismatch', count(*)
from public.inventory_snapshots child
join public.source_imports source on source.id = child.import_id
where child.workspace_id <> source.workspace_id
   or child.location_id <> source.location_id
   or source.dataset_type <> 'stock'
union all
select 'purchase_order_location_mismatch', count(*)
from public.purchase_order_lines child
join public.source_imports source on source.id = child.import_id
where child.workspace_id <> source.workspace_id
   or child.location_id <> source.location_id
   or source.dataset_type <> 'purchase_orders'
union all
select 'planning_line_location_mismatch', count(*)
from public.planning_lines child
join public.planning_runs run on run.run_id = child.run_id
where child.workspace_id <> run.workspace_id
   or child.location_id <> run.location_id
union all
select 'recommendation_location_mismatch', count(*)
from public.planning_recommendations child
join public.planning_runs run on run.run_id = child.run_id
where child.workspace_id <> run.workspace_id
   or child.location_id <> run.location_id
union all
select 'netting_location_mismatch', count(*)
from public.planning_netting_results child
join public.planning_runs run on run.run_id = child.run_id
where child.workspace_id <> run.workspace_id
   or child.location_id <> run.location_id
union all
select 'projection_location_mismatch', count(*)
from public.planning_projection_days child
join public.planning_runs run on run.run_id = child.run_id
where child.workspace_id <> run.workspace_id
   or child.location_id <> run.location_id
order by check_name;

-- Browser roles must still have no direct table privileges. Every boolean in
-- this result must be false; the API remains the data boundary.
select
    table_name,
    has_table_privilege('anon', 'public.' || table_name, 'select')
        as anon_can_select,
    has_table_privilege('authenticated', 'public.' || table_name, 'select')
        as authenticated_can_select,
    has_table_privilege('authenticated', 'public.' || table_name, 'insert,update,delete')
        as authenticated_can_mutate
from unnest(array[
    'workspaces', 'app_user_profiles', 'workspace_memberships',
    'user_location_access', 'source_imports', 'master_data_versions',
    'locations', 'items', 'item_policy_overrides', 'delivery_rules',
    'forecast_daily', 'menu_calendar', 'bom_lines', 'inventory_snapshots',
    'purchase_order_lines', 'planning_runs', 'planning_run_inputs',
    'planning_lines', 'planning_recommendations', 'planning_exceptions',
    'planning_netting_results', 'planning_projection_days'
]) as checked_tables(table_name)
order by table_name;
