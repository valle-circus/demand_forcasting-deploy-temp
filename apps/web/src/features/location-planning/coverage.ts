import type {
  CoverageExtensionStatus,
  NettingResult,
} from '@/lib/types'

/**
 * Presentation for the cross-ingredient supply-coverage chart.
 *
 * Every number here is a persisted day count from the v3 contract. Nothing
 * divides stock by demand, subtracts one scenario from another, or re-projects
 * anything: the engine counts continuous covered days against the real dated
 * forecast, and average-demand arithmetic would disagree with it precisely on
 * the lumpy, menu-driven items where it matters.
 */

export interface CoverageSegment {
  days: number
  status: CoverageExtensionStatus
  /** True when a receipt lands on or after an earlier gap and cannot bridge it. */
  afterGap: boolean
  /** Last date this scenario fully serves. */
  throughDate: string | null
}

export interface CoverageRow {
  itemId: string
  name: string
  /** Days served by usable stock alone. */
  onHandDays: number
  /** True when the count is a lower bound because the forecast ended first. */
  onHandForecastLimited: boolean
  onHandThroughDate: string | null
  openPo: CoverageSegment
  proposal: CoverageSegment
  /** Total across all three scenarios, used for sorting and bar width. */
  totalDays: number
  /** Whether the *total* is a lower bound — from the proposal scenario. */
  totalForecastLimited: boolean
  /** Item-specific target. Null when policy is not evaluable. */
  protectionHorizonDays: number | null
}

function segment(
  days: number | null,
  status: CoverageExtensionStatus | null,
  afterGap: boolean | null,
  throughDate: string | null,
): CoverageSegment {
  return {
    days: days ?? 0,
    status: status ?? 'exact',
    afterGap: afterGap ?? false,
    throughDate,
  }
}

/**
 * True when this row carries the v3 contract. A legacy row's nulls are absent
 * values, not zero coverage, so it must be excluded rather than plotted flat.
 */
export function hasCoverage(row: NettingResult): boolean {
  return row.coverage_contract_version === 1 && row.on_hand_coverage_days !== null
}

export function toCoverageRow(
  row: NettingResult,
  name: string,
): CoverageRow | null {
  if (!hasCoverage(row)) {
    return null
  }
  const onHandDays = row.on_hand_coverage_days ?? 0
  const openPo = segment(
    row.open_po_coverage_extension_days,
    row.open_po_coverage_extension_status,
    row.open_po_receipts_at_or_after_gap,
    row.with_open_po_coverage_through_date,
  )
  const proposal = segment(
    row.proposal_coverage_extension_days,
    row.proposal_coverage_extension_status,
    row.proposal_receipts_at_or_after_gap,
    row.with_proposal_coverage_through_date,
  )

  return {
    itemId: row.item_id,
    name,
    onHandDays,
    onHandForecastLimited: row.on_hand_coverage_forecast_limited ?? false,
    onHandThroughDate: row.on_hand_coverage_through_date,
    openPo,
    proposal,
    totalDays: onHandDays + openPo.days + proposal.days,
    totalForecastLimited: row.with_proposal_coverage_forecast_limited ?? false,
    protectionHorizonDays: row.protection_horizon_days,
  }
}

/** Thinnest supply first — the ingredient most likely to run out leads. */
export function byCoverage(left: CoverageRow, right: CoverageRow): number {
  if (left.totalDays !== right.totalDays) {
    return left.totalDays - right.totalDays
  }
  return left.onHandDays - right.onHandDays
}

/**
 * A day count as words.
 *
 * A forecast-limited value is a lower bound: the uploaded forecast ran out
 * before a shortage did, so the true runway is at least this long. Printing a
 * bare number would overstate what is known.
 */
export function formatCoverageDays(days: number, forecastLimited: boolean): string {
  const unit = days === 1 ? 'day' : 'days'
  return forecastLimited ? `at least ${String(days)} ${unit}` : `${String(days)} ${unit}`
}

/**
 * What an incremental segment actually means, in the maintainer's terms.
 *
 * `not_observable` is the subtle one: the earlier supply already covers the
 * whole uploaded forecast, so the stored zero says nothing could be measured —
 * not that the receipt is worthless.
 */
export function describeSegment(
  segmentValue: CoverageSegment,
  label: string,
): string {
  if (segmentValue.status === 'not_observable') {
    return `${label}: not measurable — supply before it already covers the whole forecast`
  }
  if (segmentValue.afterGap && segmentValue.days === 0) {
    return `${label}: adds no continuous cover because it arrives after stock has already run out`
  }
  const unit = segmentValue.days === 1 ? 'day' : 'days'
  if (segmentValue.status === 'lower_bound') {
    return `${label}: at least ${String(segmentValue.days)} more ${unit}`
  }
  return `${label}: ${String(segmentValue.days)} more ${unit}`
}

/** The complete row description, for screen readers and the tooltip. */
export function describeRow(row: CoverageRow): string {
  const parts = [
    `${row.name}: ${formatCoverageDays(row.onHandDays, row.onHandForecastLimited)} from stock on hand`,
    describeSegment(row.openPo, 'Already on order'),
    describeSegment(row.proposal, 'Proposed, not ordered'),
  ]
  parts.push(`Total ${formatCoverageDays(row.totalDays, row.totalForecastLimited)}`)
  if (row.protectionHorizonDays !== null) {
    parts.push(`Needs to cover ${String(row.protectionHorizonDays)} days`)
  }
  return `${parts.join('. ')}.`
}
