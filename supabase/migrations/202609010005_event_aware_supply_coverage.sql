-- Add event-aware, per-item continuous coverage for the location stock-health chart.
-- Run after 202608300004_actionable_risk_and_shelf_life.sql in the Supabase SQL Editor.

begin;

do $$
begin
    if to_regclass('public.planning_netting_results') is null
        or to_regprocedure('public.persist_planning_run_v2(jsonb)') is null
    then
        raise exception
            'Missing v2 planning foundation. Apply migrations 001 through 004 before migration 005.';
    end if;
end
$$;

alter table public.planning_netting_results
    add column coverage_contract_version smallint
        check (coverage_contract_version = 1),
    add column on_hand_coverage_days integer
        check (on_hand_coverage_days >= 0),
    add column on_hand_coverage_through_date date,
    add column on_hand_first_uncovered_date date,
    add column on_hand_coverage_forecast_limited boolean,
    add column with_open_po_coverage_days integer
        check (with_open_po_coverage_days >= 0),
    add column with_open_po_coverage_through_date date,
    add column with_open_po_first_uncovered_date date,
    add column with_open_po_coverage_forecast_limited boolean,
    add column with_proposal_coverage_days integer
        check (with_proposal_coverage_days >= 0),
    add column with_proposal_coverage_through_date date,
    add column with_proposal_first_uncovered_date date,
    add column with_proposal_coverage_forecast_limited boolean,
    add column open_po_coverage_extension_days integer
        check (open_po_coverage_extension_days >= 0),
    add column open_po_coverage_extension_status text
        check (open_po_coverage_extension_status in
            ('exact', 'lower_bound', 'not_observable')),
    add column proposal_coverage_extension_days integer
        check (proposal_coverage_extension_days >= 0),
    add column proposal_coverage_extension_status text
        check (proposal_coverage_extension_status in
            ('exact', 'lower_bound', 'not_observable')),
    add column open_po_receipts_at_or_after_gap boolean,
    add column proposal_receipts_at_or_after_gap boolean,
    add column protection_horizon_days integer
        check (protection_horizon_days > 0),
    add constraint planning_netting_results_coverage_contract_check check (
        (
            coverage_contract_version is null
            and on_hand_coverage_days is null
            and on_hand_coverage_through_date is null
            and on_hand_first_uncovered_date is null
            and on_hand_coverage_forecast_limited is null
            and with_open_po_coverage_days is null
            and with_open_po_coverage_through_date is null
            and with_open_po_first_uncovered_date is null
            and with_open_po_coverage_forecast_limited is null
            and with_proposal_coverage_days is null
            and with_proposal_coverage_through_date is null
            and with_proposal_first_uncovered_date is null
            and with_proposal_coverage_forecast_limited is null
            and open_po_coverage_extension_days is null
            and open_po_coverage_extension_status is null
            and proposal_coverage_extension_days is null
            and proposal_coverage_extension_status is null
            and open_po_receipts_at_or_after_gap is null
            and proposal_receipts_at_or_after_gap is null
            and protection_horizon_days is null
        )
        or (
            coverage_contract_version = 1
            and on_hand_coverage_days is not null
            and on_hand_coverage_forecast_limited is not null
            and with_open_po_coverage_days is not null
            and with_open_po_coverage_forecast_limited is not null
            and with_proposal_coverage_days is not null
            and with_proposal_coverage_forecast_limited is not null
            and open_po_coverage_extension_days is not null
            and open_po_coverage_extension_status is not null
            and proposal_coverage_extension_days is not null
            and proposal_coverage_extension_status is not null
            and open_po_receipts_at_or_after_gap is not null
            and proposal_receipts_at_or_after_gap is not null
            and with_open_po_coverage_days
                = on_hand_coverage_days + open_po_coverage_extension_days
            and with_proposal_coverage_days
                = with_open_po_coverage_days + proposal_coverage_extension_days
            and open_po_coverage_extension_status = case
                when on_hand_coverage_forecast_limited then 'not_observable'
                when with_open_po_coverage_forecast_limited then 'lower_bound'
                else 'exact'
            end
            and proposal_coverage_extension_status = case
                when with_open_po_coverage_forecast_limited then 'not_observable'
                when with_proposal_coverage_forecast_limited then 'lower_bound'
                else 'exact'
            end
            and (
                (
                    risk_horizon_end_date is null
                    and protection_horizon_days is null
                )
                or protection_horizon_days
                    = (risk_horizon_end_date - projection_start_date) + 1
            )
            and (
                (
                    on_hand_first_uncovered_date is null
                    and on_hand_coverage_forecast_limited
                    and on_hand_coverage_through_date = projection_end_date
                    and on_hand_coverage_days
                        = (projection_end_date - projection_start_date) + 1
                )
                or (
                    on_hand_first_uncovered_date between
                        projection_start_date and projection_end_date
                    and not on_hand_coverage_forecast_limited
                    and on_hand_coverage_days
                        = on_hand_first_uncovered_date - projection_start_date
                    and (
                        (
                            on_hand_coverage_days = 0
                            and on_hand_coverage_through_date is null
                        )
                        or on_hand_coverage_through_date
                            = on_hand_first_uncovered_date - 1
                    )
                )
            )
            and (
                (
                    with_open_po_first_uncovered_date is null
                    and with_open_po_coverage_forecast_limited
                    and with_open_po_coverage_through_date = projection_end_date
                    and with_open_po_coverage_days
                        = (projection_end_date - projection_start_date) + 1
                )
                or (
                    with_open_po_first_uncovered_date between
                        projection_start_date and projection_end_date
                    and not with_open_po_coverage_forecast_limited
                    and with_open_po_coverage_days
                        = with_open_po_first_uncovered_date - projection_start_date
                    and (
                        (
                            with_open_po_coverage_days = 0
                            and with_open_po_coverage_through_date is null
                        )
                        or with_open_po_coverage_through_date
                            = with_open_po_first_uncovered_date - 1
                    )
                )
            )
            and (
                (
                    with_proposal_first_uncovered_date is null
                    and with_proposal_coverage_forecast_limited
                    and with_proposal_coverage_through_date = projection_end_date
                    and with_proposal_coverage_days
                        = (projection_end_date - projection_start_date) + 1
                )
                or (
                    with_proposal_first_uncovered_date between
                        projection_start_date and projection_end_date
                    and not with_proposal_coverage_forecast_limited
                    and with_proposal_coverage_days
                        = with_proposal_first_uncovered_date - projection_start_date
                    and (
                        (
                            with_proposal_coverage_days = 0
                            and with_proposal_coverage_through_date is null
                        )
                        or with_proposal_coverage_through_date
                            = with_proposal_first_uncovered_date - 1
                    )
                )
            )
        )
    );

comment on column public.planning_netting_results.on_hand_coverage_days is
    'Continuous calendar days served from usable opening stock before the first unmet-demand day.';
comment on column public.planning_netting_results.open_po_coverage_extension_days is
    'Additional continuous days served when accepted dated open POs are added; late receipts cannot bridge an earlier gap.';
comment on column public.planning_netting_results.open_po_coverage_extension_status is
    'Whether the incremental PO days are exact, a lower bound, or not observable because stock already covers the supplied forecast.';
comment on column public.planning_netting_results.proposal_coverage_extension_days is
    'Additional continuous days served when proposal-only receipts are added after accepted open POs.';
comment on column public.planning_netting_results.proposal_coverage_extension_status is
    'Whether the incremental proposal days are exact, a lower bound, or not observable because prior supply already covers the supplied forecast.';
comment on column public.planning_netting_results.with_proposal_coverage_forecast_limited is
    'True when the forecast ends before a shortage is observed, so the coverage value is a lower bound.';

create function public.persist_planning_run_v3(p_payload jsonb)
returns text
language plpgsql
set search_path = public
as $$
declare
    run_payload jsonb;
    persisted_run_id text;
begin
    run_payload := p_payload -> 'run';
    if jsonb_typeof(run_payload) <> 'object'
        or coalesce((run_payload ->> 'schema_version')::integer, 0) <> 3
    then
        raise exception 'Planning persistence v3 requires run.schema_version = 3.';
    end if;

    if exists (
        select 1
        from jsonb_array_elements(
            coalesce(p_payload -> 'netting_results', '[]'::jsonb)
        ) as coverage_row
        where coverage_row ->> 'coverage_contract_version' is distinct from '1'
    ) then
        raise exception
            'Planning persistence v3 requires coverage_contract_version = 1 on every netting row.';
    end if;

    select public.persist_planning_run_v2(p_payload)
    into persisted_run_id;
    return persisted_run_id;
end
$$;

revoke all on function public.persist_planning_run_v3(jsonb)
    from public, anon, authenticated;
grant execute on function public.persist_planning_run_v3(jsonb)
    to service_role;

comment on function public.persist_planning_run_v3(jsonb) is
    'Persists schema-v3 event-aware stock, open-PO, and proposal coverage atomically.';

commit;
