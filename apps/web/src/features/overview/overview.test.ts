import { describe, expect, it } from 'vitest'

import type {
  OverviewLocationRow,
  OverviewResponse,
  PlanningRun,
} from '@/lib/types'
import { byUrgency, hasCurrentResult, locationState, topAlert } from './overview'

const RUN = { run_id: 'run-1', created_at: '2026-08-31T09:00:00+00:00' } as PlanningRun

function location(
  overrides: Partial<OverviewLocationRow> = {},
): OverviewLocationRow {
  return {
    location_id: 'LOC_A',
    location_name: 'Kitchen A',
    timezone: 'Europe/Berlin',
    ready: true,
    items_at_risk: 0,
    items_requiring_order: 0,
    items_risk_not_evaluated: 0,
    earliest_risk_date: null,
    earliest_order_required_date: null,
    sources: {
      master_data_version: null,
      planning_input: null,
      stock: null,
      purchase_orders: null,
    },
    latest_run: RUN,
    latest_run_is_current: true,
    blockers: [],
    ...overrides,
  }
}

function overview(rows: OverviewLocationRow[]): OverviewResponse {
  return {
    as_of_date: '2026-08-31',
    kpis: {
      locations_ready: rows.length,
      locations_total: rows.length,
      locations_at_risk: 0,
      locations_requiring_order: 0,
      items_at_risk: 0,
      items_requiring_order: 0,
      items_risk_not_evaluated: 0,
      recommendations_due: 0,
      blocking_issues: 0,
      open_purchase_order_lines: 0,
    },
    latest_run_at: null,
    locations: rows,
    proposal_only: true,
  }
}

describe('what a location needs', () => {
  it('ranks a blocker above risk, because a blocked kitchen cannot be assessed', () => {
    expect(
      locationState(
        location({
          blockers: [{ code: 'stock_missing', message: 'No stock.' }],
          items_at_risk: 5,
        }),
      ),
    ).toBe('blocked')
  })

  it('treats a stale result as worse than no result', () => {
    // A stale number is actively misleading; an absent one is merely missing.
    const rows = [
      location({ location_id: 'never', latest_run: null }),
      location({ location_id: 'stale', latest_run_is_current: false }),
    ]
    expect([...rows].sort(byUrgency).map((row) => row.location_id)).toEqual([
      'stale',
      'never',
    ])
  })

  it('keeps incomplete evidence distinct from ready', () => {
    expect(
      locationState(location({ items_risk_not_evaluated: 2 })),
    ).toBe('not_evaluated')
    expect(locationState(location())).toBe('ready')
  })

  it('keeps an order requirement distinct from residual proposal risk', () => {
    expect(locationState(location({ items_requiring_order: 1 }))).toBe(
      'needs_order',
    )
    expect(
      locationState(
        location({ items_requiring_order: 1, items_at_risk: 1 }),
      ),
    ).toBe('at_risk')
  })

  it('does not read risk from a stale run', () => {
    // The backend only counts risk from a current run, so a stale row must not
    // present its old count as current risk.
    expect(
      locationState(location({ latest_run_is_current: false, items_at_risk: 3 })),
    ).toBe('stale')
  })

  it('orders by urgency, then by the earliest shortage', () => {
    const rows = [
      location({ location_id: 'ready' }),
      location({
        location_id: 'needs-order',
        items_requiring_order: 1,
        earliest_order_required_date: '2026-09-03',
      }),
      location({
        location_id: 'risk-late',
        items_at_risk: 1,
        earliest_risk_date: '2026-09-20',
      }),
      location({
        location_id: 'risk-soon',
        items_at_risk: 1,
        earliest_risk_date: '2026-09-02',
      }),
      location({
        location_id: 'blocked',
        blockers: [{ code: 'stock_missing', message: 'No stock.' }],
      }),
    ]

    expect([...rows].sort(byUrgency).map((row) => row.location_id)).toEqual([
      'blocked',
      'risk-soon',
      'risk-late',
      'needs-order',
      'ready',
    ])
  })
})

describe('the top alert', () => {
  it('surfaces the single worst thing, with somewhere to go', () => {
    const alert = topAlert(
      overview([
        location({ location_id: 'fine' }),
        location({
          location_id: 'broken',
          location_name: 'Ratingen',
          blockers: [{ code: 'stock_missing', message: 'No stock.' }],
        }),
      ]),
    )

    expect(alert?.state).toBe('blocked')
    expect(alert?.headline).toContain('Ratingen')
    expect(alert?.action).toBeTruthy()
  })

  it('stays silent when nothing needs attention', () => {
    // The page then shows a calm confirmation rather than an empty alert box.
    expect(topAlert(overview([location()]))).toBeNull()
  })

  it('surfaces a proposal that still has to be placed', () => {
    const alert = topAlert(
      overview([
        location({
          location_name: 'Hamburg',
          items_requiring_order: 1,
          earliest_order_required_date: '2026-09-04',
        }),
      ]),
    )

    expect(alert?.state).toBe('needs_order')
    expect(alert?.headline).toBe('Hamburg needs an order')
  })
})

describe('whether a count can be trusted', () => {
  it('is unknown when no current run backs it', () => {
    // Rendering 0 here would claim an all-clear nobody established.
    expect(hasCurrentResult(overview([location({ latest_run: null })]))).toBe(
      false,
    )
    expect(
      hasCurrentResult(overview([location({ latest_run_is_current: false })])),
    ).toBe(false)
  })

  it('is known as soon as one location has a current result', () => {
    expect(
      hasCurrentResult(
        overview([location({ latest_run: null }), location()]),
      ),
    ).toBe(true)
  })
})
