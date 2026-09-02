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
  capBasisLabel,
  constraintStatusPresentation,
  derivationSteps,
  exceptionsForLine,
  needsAttention,
  riskDisposition,
  runCurrency,
  shelfLifeEvidence,
  uncoveredDemandG,
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
    risk_horizon_end_date: '2026-09-08',
    risk_evaluated_through_date: '2026-09-08',
    risk_horizon_fully_observed: true,
    actionable_risk_status: 'covered',
    first_stockout_within_horizon_date: null,
    max_stockout_within_horizon_g: null,
    projected_balance_at_risk_horizon_end_g: 500,
    // A legacy v2 row: coverage is absent, not zero.
    coverage_contract_version: null,
    on_hand_coverage_days: null,
    on_hand_coverage_through_date: null,
    on_hand_first_uncovered_date: null,
    on_hand_coverage_forecast_limited: null,
    with_open_po_coverage_days: null,
    with_open_po_coverage_through_date: null,
    with_open_po_first_uncovered_date: null,
    with_open_po_coverage_forecast_limited: null,
    with_proposal_coverage_days: null,
    with_proposal_coverage_through_date: null,
    with_proposal_first_uncovered_date: null,
    with_proposal_coverage_forecast_limited: null,
    open_po_coverage_extension_days: null,
    open_po_coverage_extension_status: null,
    proposal_coverage_extension_days: null,
    proposal_coverage_extension_status: null,
    open_po_receipts_at_or_after_gap: null,
    proposal_receipts_at_or_after_gap: null,
    protection_horizon_days: null,
    order_requirement_status: 'covered_without_order',
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
    rounding_direction: 'none',
    candidate_expiry_date: null,
    shelf_life_cap_basis: 'not_configured',
    forecast_through_expiry: true,
    projected_candidate_residual_at_expiry_g: 0,
    max_cover_end_date: null,
    forecast_through_max_cover: true,
    binding_constraint: 'none',
    constraint_status: 'feasible',
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
  it('takes the classification from the backend, not from a stockout date', () => {
    // The v1 UI called any non-null first_stockout_date "at risk", which swept
    // in shortages far beyond the item's own protection horizon and badly
    // inflated the risk list. Only the explicit status decides now.
    expect(
      riskDisposition(netting({ actionable_risk_status: 'at_risk' })),
    ).toBe('at_risk')
    expect(riskDisposition(netting({ actionable_risk_status: 'covered' }))).toBe(
      'covered',
    )
  })

  it('calls a shortage beyond the decision window a later replan', () => {
    // Covered for this decision, short afterwards. Real, but not today's job.
    expect(
      riskDisposition(
        netting({
          actionable_risk_status: 'covered',
          first_stockout_date: '2026-10-02',
        }),
      ),
    ).toBe('future_replan')
  })

  it('keeps incomplete evidence distinct from covered', () => {
    // Reporting "not evaluated" as covered would claim safety nobody checked.
    expect(
      riskDisposition(netting({ actionable_risk_status: 'not_evaluated' })),
    ).toBe('not_evaluated')
  })

  it('uses the backend order requirement instead of comparing dates', () => {
    expect(
      riskDisposition(
        netting({
          order_requirement_status: 'needs_order',
          with_open_po_first_uncovered_date: '2026-09-04',
        }),
      ),
    ).toBe('order_required')
  })

  it('separates a shortfall that ordering cannot fix', () => {
    expect(
      riskDisposition(
        netting({
          actionable_risk_status: 'at_risk',
          unavoidable_pre_candidate_stockout_g: 300,
        }),
      ),
    ).toBe('unavoidable')
  })

  it('accepts a decimal string, as PostgREST may send one', () => {
    expect(
      riskDisposition(
        netting({
          actionable_risk_status: 'at_risk',
          unavoidable_pre_candidate_stockout_g: '300.00',
        }),
      ),
    ).toBe('unavoidable')
  })

  it('puts only current problems in the default filter', () => {
    expect(needsAttention(netting({ actionable_risk_status: 'at_risk' }))).toBe(
      true,
    )
    expect(
      needsAttention(netting({ actionable_risk_status: 'not_evaluated' })),
    ).toBe(true)
    expect(
      needsAttention(netting({ order_requirement_status: 'needs_order' })),
    ).toBe(true)
    // A later replan must not inflate the attention count.
    expect(
      needsAttention(
        netting({
          actionable_risk_status: 'covered',
          first_stockout_date: '2026-10-02',
        }),
      ),
    ).toBe(false)
  })

  it('sorts worst first, then by earliest shortage in the window', () => {
    const rows = [
      netting({ item_id: 'covered' }),
      netting({
        item_id: 'order-required',
        order_requirement_status: 'needs_order',
        with_open_po_first_uncovered_date: '2026-09-04',
      }),
      netting({
        item_id: 'later',
        actionable_risk_status: 'covered',
        first_stockout_date: '2026-10-02',
      }),
      netting({ item_id: 'unknown', actionable_risk_status: 'not_evaluated' }),
      netting({
        item_id: 'soon',
        actionable_risk_status: 'at_risk',
        first_stockout_within_horizon_date: '2026-09-02',
      }),
      netting({
        item_id: 'unfixable',
        actionable_risk_status: 'at_risk',
        first_stockout_within_horizon_date: '2026-09-05',
        unavoidable_pre_candidate_stockout_g: 1,
      }),
    ]

    expect([...rows].sort(byRisk).map((row) => row.item_id)).toEqual([
      'unfixable',
      'soon',
      'unknown',
      'order-required',
      'later',
      'covered',
    ])
  })
})

describe('uncovered demand', () => {
  it('reports a negative ending balance as unmet demand, not as stock', () => {
    // You cannot hold minus 31 kg of pasta. The sign is a running backlog.
    expect(
      uncoveredDemandG(netting({ ending_projected_balance_g: -31_000 })),
    ).toBe(31_000)
  })

  it('has nothing to report when demand is covered', () => {
    expect(uncoveredDemandG(netting({ ending_projected_balance_g: 500 }))).toBeNull()
  })
})

describe('shelf-life evidence', () => {
  it('never presents a policy estimate as an exact expiry', () => {
    const evidence = shelfLifeEvidence(
      line({
        candidate_expiry_date: '2026-09-20',
        shelf_life_cap_basis: 'policy_approximation',
      }),
    )
    expect(evidence.basis).toBe('policy_approximation')
    expect(capBasisLabel(evidence.basis)).toMatch(/not from lot data/i)
  })

  it('flags a forecast that does not reach the expiry', () => {
    // Without coverage to that date the check is unproven, not passed.
    expect(
      shelfLifeEvidence(
        line({
          candidate_expiry_date: '2026-09-20',
          forecast_through_expiry: false,
        }),
      ).coverageIncomplete,
    ).toBe(true)
  })

  it('surfaces a projected leftover at expiry', () => {
    expect(
      shelfLifeEvidence(
        line({ projected_candidate_residual_at_expiry_g: 1200 }),
      ).residualAtExpiryG,
    ).toBe(1200)
  })
})

describe('constraint outcome', () => {
  it('distinguishes a reduced order from an impossible one', () => {
    expect(constraintStatusPresentation('feasible').tone).toBe('ready')
    expect(constraintStatusPresentation('reduced_to_safe_multiple').tone).toBe(
      'warning',
    )
    // Nothing fits under the cap, so the engine proposes nothing and React
    // must not manufacture a quantity.
    expect(constraintStatusPresentation('no_safe_positive_order').tone).toBe(
      'blocked',
    )
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
