import { describe, expect, it } from 'vitest'

import type { NettingResult } from '@/lib/types'
import {
  byCoverage,
  describeRow,
  describeSegment,
  formatCoverageDays,
  hasCoverage,
  toCoverageRow,
} from './coverage'

/** A v3 row with coverage. Overrides let each test vary one thing. */
function row(overrides: Partial<NettingResult> = {}): NettingResult {
  return {
    run_id: 'run-1',
    location_id: 'LOC_A',
    item_id: 'ITEM_A',
    projection_start_date: '2026-08-30',
    projection_end_date: '2026-10-11',
    opening_on_hand_g: 2000,
    gross_requirement_g: 42_000,
    open_po_due_g: 2000,
    net_requirement_g: 38_000,
    candidate_receipt_g: 7000,
    overdue_open_po_g: 0,
    open_po_after_horizon_g: 0,
    open_po_after_final_demand_g: 0,
    ending_projected_balance_g: -31_000,
    minimum_projected_balance_g: -31_000,
    first_stockout_date: '2026-09-11',
    unavoidable_pre_candidate_stockout_g: 0,
    risk_horizon_end_date: '2026-09-08',
    risk_evaluated_through_date: '2026-09-08',
    risk_horizon_fully_observed: true,
    actionable_risk_status: 'covered',
    first_stockout_within_horizon_date: null,
    max_stockout_within_horizon_g: 0,
    projected_balance_at_risk_horizon_end_g: 2000,
    coverage_contract_version: 1,
    on_hand_coverage_days: 2,
    on_hand_coverage_through_date: '2026-08-31',
    on_hand_first_uncovered_date: '2026-09-01',
    on_hand_coverage_forecast_limited: false,
    with_open_po_coverage_days: 4,
    with_open_po_coverage_through_date: '2026-09-02',
    with_open_po_first_uncovered_date: '2026-09-03',
    with_open_po_coverage_forecast_limited: false,
    with_proposal_coverage_days: 10,
    with_proposal_coverage_through_date: '2026-09-08',
    with_proposal_first_uncovered_date: '2026-09-09',
    with_proposal_coverage_forecast_limited: false,
    open_po_coverage_extension_days: 2,
    open_po_coverage_extension_status: 'exact',
    proposal_coverage_extension_days: 6,
    proposal_coverage_extension_status: 'exact',
    open_po_receipts_at_or_after_gap: false,
    proposal_receipts_at_or_after_gap: false,
    protection_horizon_days: 10,
    order_requirement_status: 'needs_order',
    ...overrides,
  }
}

describe('legacy runs', () => {
  it('are excluded rather than plotted as zero coverage', () => {
    // A v2 run's nulls mean "not calculated", not "no cover". Charting them
    // flat would invent a shortage that the engine never found.
    const legacy = row({
      coverage_contract_version: null,
      on_hand_coverage_days: null,
    })

    expect(hasCoverage(legacy)).toBe(false)
    expect(toCoverageRow(legacy, 'Pasta')).toBeNull()
  })

  it('accepts a row carrying the contract', () => {
    expect(hasCoverage(row())).toBe(true)
  })
})

describe('stacking', () => {
  it('uses the backend increments rather than subtracting scenarios', () => {
    const coverage = toCoverageRow(row(), 'Pasta')

    expect(coverage?.onHandDays).toBe(2)
    expect(coverage?.openPo.days).toBe(2)
    expect(coverage?.proposal.days).toBe(6)
    // Which is also the with-proposal scenario the backend reports.
    expect(coverage?.totalDays).toBe(10)
  })

  it('takes the total forecast-limited flag from the proposal scenario', () => {
    // Not from on-hand: the total is the with-proposal number, and each
    // scenario carries its own bound.
    const coverage = toCoverageRow(
      row({
        on_hand_coverage_forecast_limited: false,
        with_proposal_coverage_forecast_limited: true,
      }),
      'Pasta',
    )

    expect(coverage?.totalForecastLimited).toBe(true)
    expect(coverage?.onHandForecastLimited).toBe(false)
  })
})

describe('forecast-limited values', () => {
  it('reads as a lower bound, never as an exact figure', () => {
    // The forecast ran out before a shortage did, so the runway is at least
    // this long. A bare number would overstate what is known.
    expect(formatCoverageDays(30, true)).toBe('at least 30 days')
    expect(formatCoverageDays(30, false)).toBe('30 days')
    expect(formatCoverageDays(1, false)).toBe('1 day')
  })
})

describe('segment wording', () => {
  it('never calls an unmeasurable segment "adds nothing"', () => {
    // not_observable means earlier supply already covers the whole forecast,
    // so nothing could be measured — not that the delivery is worthless.
    const text = describeSegment(
      { days: 0, status: 'not_observable', afterGap: false, throughDate: null },
      'Already on order',
    )

    expect(text).toMatch(/not measurable/i)
    expect(text).not.toMatch(/adds nothing/i)
  })

  it('describes a lower-bound segment as at least N', () => {
    expect(
      describeSegment({ days: 5, status: 'lower_bound', afterGap: false, throughDate: null }, 'X'),
    ).toBe('X: at least 5 more days')
  })

  it('explains a delivery that lands after stock already ran out', () => {
    const text = describeSegment(
      { days: 0, status: 'exact', afterGap: true, throughDate: null },
      'Already on order',
    )
    expect(text).toMatch(/arrives after stock has already run out/i)
  })
})

describe('sorting', () => {
  it('puts the thinnest supply first', () => {
    const rows = [
      toCoverageRow(row({ item_id: 'plenty', with_proposal_coverage_days: 40 }), 'Plenty'),
      toCoverageRow(row({ item_id: 'thin' }), 'Thin'),
    ].flatMap((entry) => (entry === null ? [] : [entry]))

    // The chart's job is to surface what runs out soonest.
    rows[0].totalDays = 40
    expect([...rows].sort(byCoverage)[0].itemId).toBe('thin')
  })
})

describe('the accessible description', () => {
  it('states every scenario, the total, and the item target', () => {
    // Colour alone must never carry this, so the whole row is also a sentence.
    const coverage = toCoverageRow(row(), 'Pasta')
    const text = describeRow(coverage!)

    expect(text).toContain('2 days from stock on hand')
    expect(text).toContain('Already on order: 2 more days')
    expect(text).toContain('Proposed, not ordered: 6 more days')
    expect(text).toContain('Total 10 days')
    expect(text).toContain('Needs to cover 10 days')
  })

  it('omits the target when policy is not evaluable', () => {
    const coverage = toCoverageRow(row({ protection_horizon_days: null }), 'Pasta')
    expect(describeRow(coverage!)).not.toMatch(/needs to cover/i)
  })
})
