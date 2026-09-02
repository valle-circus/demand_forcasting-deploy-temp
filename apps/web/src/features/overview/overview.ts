import type { OverviewLocationRow, OverviewResponse } from '@/lib/types'

/**
 * Overview presentation helpers.
 *
 * Every count comes from `/overview`, which the backend now returns complete:
 * names, timezones, freshness and the earliest risk date are all supplied, so
 * this page issues one request and computes no dates of its own.
 */

export type LocationState =
  | 'blocked'
  | 'at_risk'
  | 'not_evaluated'
  | 'needs_order'
  | 'stale'
  | 'no_run'
  | 'ready'

/**
 * What this location needs, worst first.
 *
 * A blocker outranks risk because a blocked location cannot even be assessed.
 * A stale result outranks "no run" because a stale number is actively
 * misleading, where an absent one is merely missing.
 */
export function locationState(row: OverviewLocationRow): LocationState {
  if (row.blockers.length > 0) {
    return 'blocked'
  }
  if (row.latest_run === null) {
    return 'no_run'
  }
  if (!row.latest_run_is_current) {
    return 'stale'
  }
  if (row.items_at_risk > 0) {
    return 'at_risk'
  }
  // Incomplete evidence is not the same as a clean bill of health.
  if (row.items_risk_not_evaluated > 0) {
    return 'not_evaluated'
  }
  if (row.items_requiring_order > 0) {
    return 'needs_order'
  }
  return 'ready'
}

const STATE_ORDER: Record<LocationState, number> = {
  blocked: 0,
  at_risk: 1,
  not_evaluated: 2,
  needs_order: 3,
  stale: 4,
  no_run: 5,
  ready: 6,
}

export function byUrgency(
  left: OverviewLocationRow,
  right: OverviewLocationRow,
): number {
  const bySeverity =
    STATE_ORDER[locationState(left)] - STATE_ORDER[locationState(right)]
  if (bySeverity !== 0) {
    return bySeverity
  }
  const leftDate =
    left.earliest_risk_date ??
    left.earliest_order_required_date ??
    '9999-12-31'
  const rightDate =
    right.earliest_risk_date ??
    right.earliest_order_required_date ??
    '9999-12-31'
  return leftDate.localeCompare(rightDate)
}

export interface TopAlert {
  state: LocationState
  location: OverviewLocationRow
  headline: string
  action: string
}

const ALERT_COPY: Record<
  Exclude<LocationState, 'ready'>,
  { headline: (name: string) => string; action: string }
> = {
  blocked: {
    headline: (name) => `${name} cannot be planned yet`,
    action: 'Fix the data',
  },
  at_risk: {
    headline: (name) => `${name}'s proposal does not fully cover demand`,
    action: 'Review the location',
  },
  needs_order: {
    headline: (name) => `${name} needs an order`,
    action: 'Open the location',
  },
  not_evaluated: {
    headline: (name) => `${name} could not be fully checked`,
    action: 'Open the location',
  },
  stale: {
    headline: (name) => `${name} has newer data than its last result`,
    action: 'Recalculate',
  },
  no_run: {
    headline: (name) => `${name} has never been calculated`,
    action: 'Open the location',
  },
}

/**
 * The single most urgent thing across all locations, with somewhere to go.
 *
 * Returns null when nothing needs attention, so the page can show a calm
 * confirmation rather than an empty alert box.
 */
export function topAlert(overview: OverviewResponse): TopAlert | null {
  const worst = [...overview.locations].sort(byUrgency)[0]
  if (worst === undefined) {
    return null
  }
  const state = locationState(worst)
  if (state === 'ready') {
    return null
  }
  const copy = ALERT_COPY[state]
  return {
    state,
    location: worst,
    headline: copy.headline(worst.location_name),
    action: copy.action,
  }
}

/**
 * Whether a KPI derived from planning results can be trusted right now.
 *
 * The backend only counts risk from a current run, so with no current run
 * anywhere the honest answer is "not known", not zero. Rendering `0` would
 * claim an all-clear nobody established.
 */
export function hasCurrentResult(overview: OverviewResponse): boolean {
  return overview.locations.some(
    (row) => row.latest_run !== null && row.latest_run_is_current,
  )
}
