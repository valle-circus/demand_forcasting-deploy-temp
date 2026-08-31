-- Add explicit actionable-horizon and candidate-lot constraint evidence.
-- Run after 202608290003_ui_backend_transactions.sql in the Supabase SQL Editor.

begin;

do $$
begin
    if to_regclass('public.planning_lines') is null
        or to_regclass('public.planning_netting_results') is null
        or to_regprocedure('public.persist_planning_run_v1(jsonb)') is null
    then
        raise exception
            'Missing backend foundation. Apply migrations 001 through 003 before migration 004.';
    end if;
end
$$;

alter table public.planning_lines
    add column candidate_expiry_date date,
    add column shelf_life_cap_basis text not null default 'not_configured'
        check (shelf_life_cap_basis in (
            'not_configured',
            'policy_approximation',
            'exact_lot_expiry'
        )),
    add column forecast_through_expiry boolean,
    add column projected_candidate_residual_at_expiry_g numeric
        check (projected_candidate_residual_at_expiry_g >= 0),
    add column max_cover_end_date date,
    add column forecast_through_max_cover boolean,
    add column binding_constraint text not null default 'none'
        check (binding_constraint in (
            'none',
            'shelf_life',
            'max_cover',
            'shelf_life_and_max_cover'
        )),
    add column constraint_status text not null default 'feasible'
        check (constraint_status in (
            'feasible',
            'reduced_to_safe_multiple',
            'no_safe_positive_order'
        )),
    add column rounding_direction text not null default 'none'
        check (rounding_direction in ('none', 'up', 'down')),
    add constraint planning_lines_expiry_evidence_check check (
        candidate_expiry_date is not null
        or (
            forecast_through_expiry is null
            and projected_candidate_residual_at_expiry_g is null
        )
    ),
    add constraint planning_lines_max_cover_evidence_check check (
        max_cover_end_date is not null
        or forecast_through_max_cover is null
    );

alter table public.planning_netting_results
    add column risk_horizon_end_date date,
    add column risk_evaluated_through_date date,
    add column risk_horizon_fully_observed boolean not null default false,
    add column actionable_risk_status text not null default 'not_evaluated'
        check (actionable_risk_status in ('at_risk', 'covered', 'not_evaluated')),
    add column first_stockout_within_horizon_date date,
    add column projected_balance_at_risk_horizon_end_g numeric,
    add column max_stockout_within_horizon_g numeric not null default 0
        check (max_stockout_within_horizon_g >= 0),
    add constraint planning_netting_results_risk_window_check check (
        risk_evaluated_through_date is null
        or (
            risk_horizon_end_date is not null
            and risk_evaluated_through_date >= projection_start_date
            and risk_evaluated_through_date <= risk_horizon_end_date
        )
    ),
    add constraint planning_netting_results_actionable_stockout_check check (
        (actionable_risk_status = 'at_risk')
        = (first_stockout_within_horizon_date is not null)
    );

create index planning_netting_results_location_actionable_risk_idx
    on public.planning_netting_results (location_id, actionable_risk_status);

comment on column public.planning_netting_results.first_stockout_date is
    'First shortage anywhere in the uploaded forecast; secondary context only.';
comment on column public.planning_netting_results.actionable_risk_status is
    'Backend classification for the current item-specific protection horizon.';
comment on column public.planning_lines.projected_candidate_residual_at_expiry_g is
    'Tagged candidate quantity remaining at estimated expiry after competing supply is consumed first.';
comment on column public.planning_lines.shelf_life_cap_basis is
    'Whether expiry evidence is absent, a configured policy approximation, or exact lot data.';

create function public.persist_planning_run_v2(p_payload jsonb)
returns text
language sql
set search_path = public
as $$
    select public.persist_planning_run_v1(p_payload)
$$;

revoke all on function public.persist_planning_run_v2(jsonb)
    from public, anon, authenticated;
grant execute on function public.persist_planning_run_v2(jsonb)
    to service_role;

comment on function public.persist_planning_run_v2(jsonb) is
    'Persists the v2 actionable-risk and shelf-life evidence contract atomically.';

commit;
