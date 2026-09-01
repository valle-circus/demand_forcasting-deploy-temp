import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { InfoHint } from '@/components/InfoHint'
import { formatDateShort } from '@/lib/formatting'
import type { CoverageContext, NettingResult } from '@/lib/types'
import {
  byCoverage,
  describeRow,
  formatCoverageDays,
  toCoverageRow,
} from './coverage'
import type { CoverageRow } from './coverage'

const VISIBLE_BY_DEFAULT = 12

/**
 * How far each ingredient's supply carries this kitchen.
 *
 * Deliberately hand-built rather than drawn with the charting library. This is
 * a bullet-style bar list: every row needs its own target marker, its own
 * accessible sentence, and a patterned third segment. In HTML each row is real
 * text that a screen reader reads and a browser can search; in an SVG chart the
 * same information would have to be duplicated into a hidden table.
 *
 * All three segments are persisted day counts. Nothing here divides stock by
 * demand or subtracts one scenario from another.
 */
export function CoverageChart({
  netting,
  names,
  context,
}: {
  netting: NettingResult[]
  names: Map<string, string>
  context: CoverageContext
}) {
  const [showAll, setShowAll] = useState(false)

  if (context.requires_fresh_schema_v3_run || !context.available_for_all_items) {
    return (
      <div className="rounded-lg border border-dashed border-border px-4 py-6 text-center">
        <p className="text-sm text-muted-foreground">
          Compute a fresh recommendation to see supply coverage.
        </p>
        <p className="mt-1 text-xs text-faint">
          This result predates the coverage calculation. Its coverage values are
          absent, not zero.
        </p>
      </div>
    )
  }

  const rows = netting
    .map((row) => toCoverageRow(row, names.get(row.item_id) ?? row.item_id))
    .filter((row): row is CoverageRow => row !== null)
    .sort(byCoverage)

  if (rows.length === 0) {
    return null
  }

  const visible = showAll ? rows : rows.slice(0, VISIBLE_BY_DEFAULT)
  const hidden = rows.length - visible.length

  // One shared scale so bar lengths are comparable between ingredients.
  const scaleMax = Math.max(
    ...rows.map((row) => Math.max(row.totalDays, row.protectionHorizonDays ?? 0)),
    1,
  )

  return (
    <section aria-labelledby="coverage-heading" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3
          id="coverage-heading"
          className="flex items-center gap-1 text-sm font-medium"
        >
          How long supply lasts
          <InfoHint label="How long supply lasts">
            Continuous days covered against the real dated forecast, counted by
            the planning engine. Zero-demand days extend the runway, and a
            delivery arriving after stock has already run out does not repair
            the days before it.
          </InfoHint>
        </h3>
        <Legend />
      </div>

      <ul className="space-y-2">
        {visible.map((row) => (
          <CoverageBar key={row.itemId} row={row} scaleMax={scaleMax} />
        ))}
      </ul>

      {hidden > 0 && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowAll(true)
          }}
        >
          Show {hidden} more {hidden === 1 ? 'ingredient' : 'ingredients'}
        </Button>
      )}
      {showAll && rows.length > VISIBLE_BY_DEFAULT && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setShowAll(false)
          }}
        >
          Show fewer
        </Button>
      )}
    </section>
  )
}

function Legend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <li className="flex items-center gap-1.5">
        <span className="h-2.5 w-4 rounded-sm bg-primary" />
        In stock
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-2.5 w-4 rounded-sm bg-info/55" />
        On order
      </li>
      <li className="flex items-center gap-1.5">
        {/* Outlined and striped, never a solid fill: this has not been ordered. */}
        <span className="h-2.5 w-4 rounded-sm border border-dashed border-primary bg-[repeating-linear-gradient(45deg,color-mix(in_oklch,var(--circus-accent),transparent_55%)_0_3px,transparent_3px_6px)]" />
        Proposal — not ordered
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-3 w-0.5 bg-foreground" />
        Needs to cover
      </li>
    </ul>
  )
}

/** Inline numbers only where the segment is wide enough to hold them. */
const LABEL_THRESHOLD_PERCENT = 9

function CoverageBar({ row, scaleMax }: { row: CoverageRow; scaleMax: number }) {
  const share = (days: number) => (days / scaleMax) * 100
  const percent = (days: number) => `${String(share(days))}%`

  // A shortfall against this item's own target, never one global line.
  const shortOfTarget =
    row.protectionHorizonDays !== null && row.totalDays < row.protectionHorizonDays

  return (
    <li className="grid grid-cols-[minmax(7rem,11rem)_1fr_auto] items-center gap-3 text-xs">
      <span className="truncate" title={row.name}>
        {row.name}
      </span>

      {/* Focusable, so the breakdown is reachable by keyboard and not only on
          hover. The bar is the summary; the card is the detail. */}
      <div className="group relative" tabIndex={0} aria-label={describeRow(row)}>
        <div className="relative h-6 rounded-sm bg-surface ring-ring group-focus-visible:ring-2">
          {/* `inset-0`, not `left-0`: the segments are sized in percent, so
              the container must span the full track. */}
          <div className="absolute inset-0 flex overflow-hidden rounded-sm">
            <Segment
              widthPercent={share(row.onHandDays)}
              className="bg-primary text-primary-foreground"
              label={String(row.onHandDays)}
            />
            <Segment
              widthPercent={share(row.openPo.days)}
              className="bg-info/55 text-foreground"
              label={`+${String(row.openPo.days)}`}
            />
            <Segment
              widthPercent={share(row.proposal.days)}
              className="border-y border-r border-dashed border-primary bg-[repeating-linear-gradient(45deg,color-mix(in_oklch,var(--circus-accent),transparent_55%)_0_4px,transparent_4px_8px)] text-accent-text"
              label={`+${String(row.proposal.days)}`}
            />
          </div>

          {row.protectionHorizonDays !== null && (
            <span
              aria-hidden="true"
              // Full-height marker with a cap, so "how far must this reach"
              // survives being next to a long bar.
              className="absolute -top-1 -bottom-1 w-0.5 bg-foreground"
              style={{ left: percent(row.protectionHorizonDays) }}
            />
          )}
        </div>

        <CoverageCard row={row} shortOfTarget={shortOfTarget} />
      </div>

      <span
        className={`tabular whitespace-nowrap ${shortOfTarget ? 'text-warning' : 'text-muted-foreground'}`}
      >
        {formatCoverageDays(row.totalDays, row.totalForecastLimited)}
      </span>
    </li>
  )
}

function Segment({
  widthPercent,
  className,
  label,
}: {
  widthPercent: number
  className: string
  label: string
}) {
  return (
    <span
      className={`flex h-full items-center justify-center overflow-hidden text-[10px] font-medium tabular ${className}`}
      style={{ width: `${String(widthPercent)}%` }}
    >
      {widthPercent >= LABEL_THRESHOLD_PERCENT && label}
    </span>
  )
}

/**
 * The breakdown, on hover and on keyboard focus.
 *
 * The bar alone cannot say how many days each part contributes, and the total
 * on its own reads as an unexplained number. Nothing here is required to act —
 * the total, the target and the risk badge stay visible — so a card is the
 * right place for the arithmetic.
 */
function CoverageCard({
  row,
  shortOfTarget,
}: {
  row: CoverageRow
  shortOfTarget: boolean
}) {
  return (
    <div
      role="presentation"
      className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 hidden w-64 rounded-lg border border-border bg-background p-3 shadow-lg group-hover:block group-focus-visible:block"
    >
      <p className="mb-2 font-medium">{row.name}</p>
      <dl className="space-y-1">
        <CardRow
          label="In stock"
          value={formatCoverageDays(row.onHandDays, row.onHandForecastLimited)}
          through={row.onHandThroughDate}
        />
        <CardRow
          label="On order"
          value={segmentValue(row.openPo)}
          through={row.openPo.throughDate}
        />
        <CardRow
          label="Proposal"
          value={segmentValue(row.proposal)}
          through={row.proposal.throughDate}
          note="not ordered"
        />
      </dl>
      <div className="mt-2 flex justify-between border-t border-border pt-2 font-medium">
        <span>Lasts</span>
        <span className="tabular">
          {formatCoverageDays(row.totalDays, row.totalForecastLimited)}
        </span>
      </div>
      {row.protectionHorizonDays !== null && (
        <p
          className={`mt-1 flex justify-between ${shortOfTarget ? 'text-warning' : 'text-muted-foreground'}`}
        >
          <span>Needs to cover</span>
          <span className="tabular">
            {String(row.protectionHorizonDays)} days
            {shortOfTarget ? ' — short' : ''}
          </span>
        </p>
      )}
      {(row.openPo.afterGap || row.proposal.afterGap) && (
        <p className="mt-2 text-warning">
          A delivery arrives after stock has already run out, so it does not
          extend the run.
        </p>
      )}
    </div>
  )
}

/** Words rather than a bare number, so a zero is never ambiguous. */
function segmentValue(segment: CoverageRow['openPo']): string {
  if (segment.status === 'not_observable') {
    return 'not measurable'
  }
  const unit = segment.days === 1 ? 'day' : 'days'
  const prefix = segment.status === 'lower_bound' ? 'at least ' : ''
  return `${prefix}+${String(segment.days)} ${unit}`
}

function CardRow({
  label,
  value,
  through,
  note,
}: {
  label: string
  value: string
  through: string | null
  note?: string
}) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">
        {label}
        {note !== undefined && <span className="text-faint"> ({note})</span>}
      </dt>
      <dd className="text-right tabular">
        {value}
        {through !== null && (
          <span className="block text-faint">to {formatDateShort(through)}</span>
        )}
      </dd>
    </div>
  )
}
