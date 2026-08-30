import { toNumber } from '@/lib/formatting'
import type {
  NettingResult,
  PlanningException,
  PlanningLine,
  PlanningRun,
  PlanningStatusResponse,
  Provenance,
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

export type RiskLevel = 'unavoidable' | 'stockout' | 'ok'

/**
 * Risk for one item, from the persisted netting summary.
 *
 * `unavoidable` means the shortfall lands before any order placed now could
 * arrive — ordering cannot fix it, so it is worse than a plain projected
 * stockout and is ranked above it.
 */
export function riskLevel(row: NettingResult): RiskLevel {
  if ((toNumber(row.unavoidable_pre_candidate_stockout_g) ?? 0) > 0) {
    return 'unavoidable'
  }
  return row.first_stockout_date === null ? 'ok' : 'stockout'
}

const RISK_ORDER: Record<RiskLevel, number> = {
  unavoidable: 0,
  stockout: 1,
  ok: 2,
}

/** Worst first, then earliest stockout, so the top row is the real problem. */
export function byRisk(left: NettingResult, right: NettingResult): number {
  const bySeverity = RISK_ORDER[riskLevel(left)] - RISK_ORDER[riskLevel(right)]
  if (bySeverity !== 0) {
    return bySeverity
  }
  const leftDate = left.first_stockout_date ?? '9999-12-31'
  const rightDate = right.first_stockout_date ?? '9999-12-31'
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
