import { toNumber } from '@/lib/formatting'
import type {
  BindingConstraint,
  ConstraintStatus,
  NettingResult,
  PlanningException,
  PlanningLine,
  PlanningRun,
  PlanningStatusResponse,
  Provenance,
  ShelfLifeCapBasis,
} from '@/lib/types'

/**
 * Presentation helpers for one location's planning result.
 *
 * Everything here reads fields the Python engine already produced. Nothing
 * recalculates a requirement, a cap, or a rounding decision — where the UI
 * needs to say *why* a number came out as it did, it quotes the engine's own
 * exceptions rather than inferring it from a comparison in the browser.
 */

// ---------------------------------------------------------------------------
// Run currency
// ---------------------------------------------------------------------------

export type RunCurrency = 'none' | 'current' | 'stale'

/**
 * Whether the latest run still reflects the accepted inputs.
 *
 * The server decides this; `latest_run_is_current` is read, never derived.
 */
export function runCurrency(status: PlanningStatusResponse): RunCurrency {
  if (status.latest_run === null) {
    return 'none'
  }
  return status.latest_run_is_current ? 'current' : 'stale'
}

export function runStatusLabel(run: PlanningRun): string {
  switch (run.status) {
    case 'completed':
      return 'Completed'
    case 'blocked':
      return 'Blocked'
    case 'failed':
      return 'Failed'
    default:
      return 'Started'
  }
}

// ---------------------------------------------------------------------------
// Item risk
// ---------------------------------------------------------------------------

/**
 * What the maintainer should do about one item.
 *
 * The pre-proposal action comes from `order_requirement_status`; the separate
 * post-proposal outcome remains `actionable_risk_status`. Both are supplied by
 * Python. Dates below are display and tie-breaker fields, not classifications.
 */
export type RiskDisposition =
  | 'unavoidable'
  | 'at_risk'
  | 'not_evaluated'
  | 'order_required'
  | 'future_replan'
  | 'covered'

export function riskDisposition(row: NettingResult): RiskDisposition {
  if (row.actionable_risk_status === 'at_risk') {
    // A shortfall landing before any order placed now could arrive cannot be
    // fixed by ordering, so it is called out separately.
    return (toNumber(row.unavoidable_pre_candidate_stockout_g) ?? 0) > 0
      ? 'unavoidable'
      : 'at_risk'
  }
  if (row.actionable_risk_status === 'not_evaluated') {
    // Incomplete evidence. Emphatically not the same as covered.
    return 'not_evaluated'
  }
  if (row.order_requirement_status === 'needs_order') {
    return 'order_required'
  }
  if (row.order_requirement_status === 'not_evaluated') {
    return 'not_evaluated'
  }
  // Covered through this decision's horizon, but the forecast runs short
  // afterwards — expected to be handled by a later review, not now.
  return row.first_stockout_date === null ? 'covered' : 'future_replan'
}

/**
 * Demand left unmet at the end of the full forecast, in grams.
 *
 * `ending_projected_balance_g` goes negative to express a running backlog, not
 * a physical quantity — you cannot hold minus 31 kg of pasta. This flips the
 * sign so it can be labelled as what it is: demand nobody has ordered for yet,
 * assuming no later planning cycle places an order. Returns null when the
 * balance is non-negative, because then there is no backlog to report.
 */
export function uncoveredDemandG(row: NettingResult): number | null {
  const balance = toNumber(row.ending_projected_balance_g)
  return balance === null || balance >= 0 ? null : Math.abs(balance)
}

/** True for the dispositions that belong in the default "needs attention" filter. */
export function needsAttention(row: NettingResult): boolean {
  const disposition = riskDisposition(row)
  return (
    disposition === 'unavoidable' ||
    disposition === 'at_risk' ||
    disposition === 'not_evaluated' ||
    disposition === 'order_required'
  )
}

const DISPOSITION_ORDER: Record<RiskDisposition, number> = {
  unavoidable: 0,
  at_risk: 1,
  not_evaluated: 2,
  order_required: 3,
  future_replan: 4,
  covered: 5,
}

/** Worst first, then earliest shortage inside the decision window. */
export function byRisk(left: NettingResult, right: NettingResult): number {
  const bySeverity =
    DISPOSITION_ORDER[riskDisposition(left)] -
    DISPOSITION_ORDER[riskDisposition(right)]
  if (bySeverity !== 0) {
    return bySeverity
  }
  const leftDate =
    left.with_open_po_first_uncovered_date ??
    left.first_stockout_within_horizon_date ??
    left.first_stockout_date ??
    '9999-12-31'
  const rightDate =
    right.with_open_po_first_uncovered_date ??
    right.first_stockout_within_horizon_date ??
    right.first_stockout_date ??
    '9999-12-31'
  return leftDate.localeCompare(rightDate)
}

// ---------------------------------------------------------------------------
// Derivation
// ---------------------------------------------------------------------------

export type StepKind = 'value' | 'add' | 'subtract' | 'total' | 'limit'

export interface DerivationStep {
  label: string
  /** Already-formatted display value. */
  value: number | null
  unit: 'g' | 'factor' | 'units'
  kind: StepKind
  provenance?: Provenance
  /** Shown when the engine recorded no value for this constraint. */
  absent?: boolean
}

/**
 * The chain that produced one proposed quantity, in the order the engine
 * applies it: floor at zero, shelf-life cap, max-cover cap, MOQ, then case
 * rounding.
 *
 * Every entry is a field read. The browser does not add, subtract, or cap
 * anything — if these numbers did not already agree, the fix belongs in the
 * engine, not here.
 */
export function derivationSteps(line: PlanningLine): DerivationStep[] {
  const shelfCap = toNumber(line.shelf_life_cap_g)
  const maxCoverCap = toNumber(line.max_cover_cap_g)

  return [
    {
      label: 'Gross requirement',
      value: toNumber(line.gross_requirement_g),
      unit: 'g',
      kind: 'value',
    },
    {
      label: 'Yield factor',
      value: toNumber(line.yield_factor),
      unit: 'factor',
      kind: 'value',
      provenance: line.yield_factor_provenance,
    },
    {
      label: 'Adjusted requirement',
      value: toNumber(line.adjusted_requirement_g),
      unit: 'g',
      kind: 'total',
    },
    {
      label: 'Safety stock',
      value: toNumber(line.safety_stock_g),
      unit: 'g',
      kind: 'add',
      provenance: line.safety_stock_provenance,
    },
    {
      label: 'Usable on hand',
      value: toNumber(line.usable_on_hand_g),
      unit: 'g',
      kind: 'subtract',
    },
    {
      label: 'Open purchase orders due',
      value: toNumber(line.open_po_due_g),
      unit: 'g',
      kind: 'subtract',
    },
    {
      label: 'Raw order',
      value: toNumber(line.raw_order_g),
      unit: 'g',
      kind: 'total',
    },
    {
      label: 'Shelf-life cap',
      value: shelfCap,
      unit: 'g',
      kind: 'limit',
      absent: shelfCap === null,
    },
    {
      label: 'Max-cover cap',
      value: maxCoverCap,
      unit: 'g',
      kind: 'limit',
      absent: maxCoverCap === null,
    },
    {
      label: 'After caps',
      value: toNumber(line.capped_order_g),
      unit: 'g',
      kind: 'total',
    },
    {
      label: 'Minimum order quantity',
      value: toNumber(line.moq_order_units),
      unit: 'units',
      kind: 'limit',
    },
    {
      label: 'Case multiple',
      value: toNumber(line.case_multiple_order_units),
      unit: 'units',
      kind: 'limit',
    },
    {
      label: 'Proposed',
      value: toNumber(line.proposed_order_units),
      unit: 'units',
      kind: 'total',
    },
  ]
}

/**
 * The engine's own exceptions for one line.
 *
 * This is how the UI says a cap bound or an order was inflated to a minimum:
 * the engine records it, the browser repeats it. Comparing numbers here to
 * guess which constraint applied would be reimplementing the decision.
 */
export function exceptionsForLine(
  exceptions: readonly PlanningException[],
  planningLineId: string,
): PlanningException[] {
  return exceptions.filter(
    (exception) => exception.planning_line_id === planningLineId,
  )
}

// ---------------------------------------------------------------------------
// Shelf-life and constraint evidence
// ---------------------------------------------------------------------------

const CAP_BASIS_LABELS: Record<ShelfLifeCapBasis, string> = {
  not_configured: 'No shelf life configured',
  // A configured anchor plus shelf-life days. Never an exact lot MHD, and the
  // wording must not let anyone read it as one.
  policy_approximation: 'Estimated from the item policy, not from lot data',
  exact_lot_expiry: 'From exact lot data',
}

export function capBasisLabel(basis: ShelfLifeCapBasis): string {
  return CAP_BASIS_LABELS[basis] ?? basis
}

const BINDING_LABELS: Record<BindingConstraint, string> = {
  none: 'Nothing limited this order',
  shelf_life: 'Limited by shelf life',
  max_cover: 'Limited by maximum cover',
  shelf_life_and_max_cover: 'Limited by shelf life and maximum cover',
}

export function bindingConstraintLabel(constraint: BindingConstraint): string {
  return BINDING_LABELS[constraint] ?? constraint
}

const CONSTRAINT_STATUS_LABELS: Record<
  ConstraintStatus,
  { label: string; tone: 'ready' | 'warning' | 'blocked' }
> = {
  feasible: { label: 'Safe to order', tone: 'ready' },
  // A hard cap forced a smaller purchasable multiple than the raw need.
  reduced_to_safe_multiple: { label: 'Reduced to a safe amount', tone: 'warning' },
  // Pack sizes leave nothing that fits under the cap. There is no proposal.
  no_safe_positive_order: { label: 'No safe order possible', tone: 'blocked' },
}

export function constraintStatusPresentation(status: ConstraintStatus): {
  label: string
  tone: 'ready' | 'warning' | 'blocked'
} {
  return (
    CONSTRAINT_STATUS_LABELS[status] ?? { label: status, tone: 'warning' as const }
  )
}

export interface ShelfLifeEvidence {
  expiryDate: string | null
  basis: ShelfLifeCapBasis
  /** True when the forecast does not reach the candidate's expiry. */
  coverageIncomplete: boolean
  /** Above zero means some of the proposed delivery is projected to expire unused. */
  residualAtExpiryG: number | null
}

/**
 * What is known about whether the proposed delivery can be consumed in time.
 *
 * Read only. Feasibility is decided in Python; a residual above zero is the
 * engine's own projection, not a browser estimate, and it is evidence of waste
 * risk rather than a claim about actual waste.
 */
export function shelfLifeEvidence(line: PlanningLine): ShelfLifeEvidence {
  return {
    expiryDate: line.candidate_expiry_date,
    basis: line.shelf_life_cap_basis,
    coverageIncomplete:
      line.candidate_expiry_date !== null && !line.forecast_through_expiry,
    residualAtExpiryG: toNumber(line.projected_candidate_residual_at_expiry_g),
  }
}

// ---------------------------------------------------------------------------
// Provenance wording
// ---------------------------------------------------------------------------

const PROVENANCE_LABELS: Record<Provenance, string> = {
  observed: 'Measured',
  manual: 'Entered by hand',
  policy_default: 'Policy default',
  empty_placeholder: 'Known empty',
  unavailable: 'Unavailable',
}

export function provenanceLabel(provenance: Provenance): string {
  return PROVENANCE_LABELS[provenance] ?? provenance
}
