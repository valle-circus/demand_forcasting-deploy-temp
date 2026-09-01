import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { InfoHint } from '@/components/InfoHint'
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

function CoverageBar({ row, scaleMax }: { row: CoverageRow; scaleMax: number }) {
  const percent = (days: number) => `${String((days / scaleMax) * 100)}%`

  // A shortfall against this item's own target, never one global line.
  const shortOfTarget =
    row.protectionHorizonDays !== null && row.totalDays < row.protectionHorizonDays

  return (
    <li className="grid grid-cols-[minmax(7rem,11rem)_1fr_auto] items-center gap-3 text-xs">
      <span className="truncate" title={row.name}>
        {row.name}
      </span>

      <div
        className="relative h-5 rounded-sm bg-surface"
        role="img"
        aria-label={describeRow(row)}
        title={[
          describeRow(row),
          row.openPo.afterGap || row.proposal.afterGap
            ? 'A delivery arrives after stock has already run out.'
            : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {/* `inset-0`, not `left-0`: the segments are sized in percent, so the
            container must span the full track or they resolve against zero. */}
        <div className="absolute inset-0 flex overflow-hidden rounded-sm">
          <span
            className="h-full bg-primary"
            style={{ width: percent(row.onHandDays) }}
          />
          <span
            className="h-full bg-info/55"
            style={{ width: percent(row.openPo.days) }}
          />
          <span
            className="h-full border-y border-r border-dashed border-primary bg-[repeating-linear-gradient(45deg,color-mix(in_oklch,var(--circus-accent),transparent_55%)_0_4px,transparent_4px_8px)]"
            style={{ width: percent(row.proposal.days) }}
          />
        </div>

        {row.protectionHorizonDays !== null && (
          <span
            aria-hidden="true"
            className="absolute inset-y-0 w-0.5 bg-foreground"
            style={{ left: percent(row.protectionHorizonDays) }}
          />
        )}
      </div>

      <span
        className={`tabular whitespace-nowrap ${shortOfTarget ? 'text-warning' : 'text-muted-foreground'}`}
      >
        {formatCoverageDays(row.totalDays, row.totalForecastLimited)}
      </span>
    </li>
  )
}
