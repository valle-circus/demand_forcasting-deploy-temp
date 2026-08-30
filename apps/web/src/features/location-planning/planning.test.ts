import { describe, expect, it } from 'vitest'

import type {
  NettingResult,
  PlanningException,
  PlanningLine,
  PlanningRun,
  PlanningStatusResponse,
} from '@/lib/types'
import {
  byRisk,
  derivationSteps,
  exceptionsForLine,
  riskLevel,
  runCurrency,
} from './planning'

function netting(overrides: Partial<NettingResult> = {}): NettingResult {
  return {
    run_id: 'run-1',
    location_id: 'LOC_A',
    item_id: 'ITEM_A',
    projection_start_date: '2026-08-29',
    projection_end_date: '2026-09-29',
    opening_on_hand_g: 1000,
    gross_requirement_g: 500,
    open_po_due_g: 0,
    net_requirement_g: 0,
    candidate_receipt_g: 0,
    overdue_open_po_g: 0,
    open_po_after_horizon_g: 0,
    open_po_after_final_demand_g: 0,
    ending_projected_balance_g: 500,
    minimum_projected_balance_g: 500,
    first_stockout_date: null,
    unavoidable_pre_candidate_stockout_g: 0,
    ...overrides,
  }
}

function line(overrides: Partial<PlanningLine> = {}): PlanningLine {
  return {
    planning_line_id: 'line-1',
    run_id: 'run-1',
    location_id: 'LOC_A',
    item_id: 'ITEM_A',
    supplier_id: 'SUP_A',
    schedule_rule_id: 'RULE_A',
    order_date: '2026-08-30',
    expected_delivery_date: '2026-09-02',
    coverage_start_date: '2026-09-02',
    coverage_end_date: '2026-09-09',
    protection_days: 7,
    gross_requirement_g: 12_400,
    yield_factor: 1.05,
    yield_factor_provenance: 'policy_default',
    adjusted_requirement_g: 13_020,
    safety_stock_g: 1800,
    safety_stock_provenance: 'policy_default',
    usable_on_hand_g: 4200,
    open_po_due_g: 2000,
    raw_order_g: 8620,
    shelf_life_cap_g: null,
    max_cover_cap_g: 6000,
    capped_order_g: 6000,
    order_unit_size_g: 2000,
    moq_order_units: 2,
    case_multiple_order_units: 1,
    proposed_order_units: 3,
    rounding_delta_g: 0,
    data_status: 'PROPOSAL',
    ...overrides,
  }
}

describe('run currency', () => {
  const run = { run_id: 'run-1' } as PlanningRun

  function status(overrides: Partial<PlanningStatusResponse>) {
    return {
      location_id: 'LOC_A',
      ready: true,
      blockers: [],
      sources: {
        master_data_version: null,
        planning_input: null,
        stock: null,
        purchase_orders: null,
      },
      latest_run: null,
      latest_run_is_current: false,
      proposal_only: true,
      ...overrides,
    } as PlanningStatusResponse
  }

  it('reads the server verdict rather than deriving one', () => {
    expect(runCurrency(status({ latest_run: null }))).toBe('none')
    expect(
      runCurrency(status({ latest_run: run, latest_run_is_current: true })),
    ).toBe('current')
    // A newer accepted import makes an existing result stale. Only the server
    // knows that; the browser must not guess from timestamps.
    expect(
      runCurrency(status({ latest_run: run, latest_run_is_current: false })),
    ).toBe('stale')
  })
})

describe('item risk', () => {
  it('ranks an unfixable shortfall above a plain stockout', () => {
    // Ordering now cannot fix a shortfall that lands before any delivery, so
    // it is a different and worse problem.
    expect(
      riskLevel(
        netting({
          first_stockout_date: '2026-09-01',
          unavoidable_pre_candidate_stockout_g: 300,
        }),
      ),
    ).toBe('unavoidable')
    expect(riskLevel(netting({ first_stockout_date: '2026-09-01' }))).toBe(
      'stockout',
    )
    expect(riskLevel(netting())).toBe('ok')
  })

  it('accepts a decimal string, as PostgREST may send one', () => {
    expect(
      riskLevel(netting({ unavoidable_pre_candidate_stockout_g: '300.00' })),
    ).toBe('unavoidable')
  })

  it('sorts worst first, then by earliest stockout', () => {
    const rows = [
      netting({ item_id: 'ok' }),
      netting({ item_id: 'late', first_stockout_date: '2026-09-20' }),
      netting({ item_id: 'early', first_stockout_date: '2026-09-02' }),
      netting({
        item_id: 'unfixable',
        first_stockout_date: '2026-09-25',
        unavoidable_pre_candidate_stockout_g: 1,
      }),
    ]

    expect([...rows].sort(byRisk).map((row) => row.item_id)).toEqual([
      'unfixable',
      'early',
      'late',
      'ok',
    ])
  })
})

describe('derivation', () => {
  it('follows the order the engine applies constraints in', () => {
    // Floor, then shelf-life cap, then max-cover cap, then MOQ, then case
    // rounding. Showing them out of order would misrepresent the calculation.
    expect(derivationSteps(line()).map((step) => step.label)).toEqual([
      'Gross requirement',
      'Yield factor',
      'Adjusted requirement',
      'Safety stock',
      'Usable on hand',
      'Open purchase orders due',
      'Raw order',
      'Shelf-life cap',
      'Max-cover cap',
      'After caps',
      'Minimum order quantity',
      'Case multiple',
      'Proposed',
    ])
  })

  it('reports stored values verbatim and never recomputes them', () => {
    // A line whose numbers do not add up. The browser must still show what the
    // engine stored: if these ever disagree the bug is in the engine, and
    // silently "fixing" it here would hide that.
    const steps = derivationSteps(
      line({
        gross_requirement_g: 100,
        yield_factor: 2,
        adjusted_requirement_g: 999,
        raw_order_g: 12_345,
        proposed_order_units: 7,
      }),
    )
    const value = (label: string) =>
      steps.find((step) => step.label === label)?.value

    expect(value('Adjusted requirement')).toBe(999)
    expect(value('Raw order')).toBe(12_345)
    expect(value('Proposed')).toBe(7)
  })

  it('marks an absent cap as absent rather than as zero', () => {
    const steps = derivationSteps(line({ shelf_life_cap_g: null }))
    const shelf = steps.find((step) => step.label === 'Shelf-life cap')

    expect(shelf?.absent).toBe(true)
    // Zero would read as "capped at nothing", which is the opposite meaning.
    expect(shelf?.value).toBeNull()
  })

  it('carries provenance for the policy-derived inputs', () => {
    const steps = derivationSteps(line())
    expect(
      steps.find((step) => step.label === 'Yield factor')?.provenance,
    ).toBe('policy_default')
    expect(steps.find((step) => step.label === 'Safety stock')?.provenance).toBe(
      'policy_default',
    )
  })
})

describe('exceptions', () => {
  const exceptions: PlanningException[] = [
    {
      exception_id: 'e1',
      run_id: 'run-1',
      planning_line_id: 'line-1',
      code: 'CASE_ROUNDING_APPLIED',
      severity: 'info',
      dataset: null,
      record_ref: null,
      message: 'Rounded up to a full case.',
      remedy: 'No action needed.',
    },
    {
      exception_id: 'e2',
      run_id: 'run-1',
      planning_line_id: 'line-2',
      code: 'MOQ_INFLATED',
      severity: 'warning',
      dataset: null,
      record_ref: null,
      message: 'Raised to the minimum order quantity.',
      remedy: 'Review the minimum with the supplier.',
    },
    {
      exception_id: 'e3',
      run_id: 'run-1',
      planning_line_id: null,
      code: 'UNAPPROVED_MASTER_DATA',
      severity: 'warning',
      dataset: 'items',
      record_ref: null,
      message: 'Master data is not approved.',
      remedy: 'Approve the master workbook.',
    },
  ]

  it('selects only the notes belonging to one line', () => {
    // How the UI says a cap bound or an order was inflated: the engine
    // recorded it, so the browser quotes it instead of inferring it.
    expect(
      exceptionsForLine(exceptions, 'line-1').map((row) => row.exception_id),
    ).toEqual(['e1'])
  })

  it('leaves run-level notes out of a line detail', () => {
    expect(exceptionsForLine(exceptions, 'line-3')).toEqual([])
  })
})
