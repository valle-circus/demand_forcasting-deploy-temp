import { ChevronRight } from 'lucide-react'
import { motion } from 'motion/react'
import { Fragment, useState } from 'react'

import { InfoHint } from '@/components/InfoHint'
import { StatusBadge } from '@/components/StatusBadge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Toggle } from '@/components/ui/toggle'
import { formatCount, formatDate, formatGrams } from '@/lib/formatting'
import type {
  CoverageContext,
  InventoryResponse,
  NettingResult,
  PlanningLine,
  ProjectionDay,
} from '@/lib/types'
import { CoverageChart } from './CoverageChart'
import { StockProjectionChart } from './StockProjectionChart'
import { byRisk, needsAttention, riskDisposition } from './planning'
import type { RiskDisposition } from './planning'

/**
 * What the status column says.
 *
 * The backend classifies risk from the projection **including the proposed
 * receipt**, so it answers "does this plan work?", not "what happens if you do
 * nothing?". The labels have to reflect that or they mislead: an item whose
 * proposal is the very thing that saves it must not read as needing no action.
 */
const DISPOSITION: Record<
  RiskDisposition,
  { tone: 'blocked' | 'warning' | 'ready' | 'neutral'; label: string }
> = {
  // The shortfall lands before any delivery could arrive, so ordering cannot
  // fix it however large the order.
  unavoidable: { tone: 'blocked', label: 'Too late to fix' },
  // Short even with the proposal applied — the proposal is not enough.
  at_risk: { tone: 'warning', label: 'Still short' },
  // Evidence did not reach the end of the window. Not the same as safe.
  not_evaluated: { tone: 'neutral', label: 'Not enough data' },
  // Covered through this window; the forecast dips again afterwards, which a
  // later review handles.
  future_replan: { tone: 'ready', label: 'Covered' },
  covered: { tone: 'ready', label: 'Covered' },
}

interface RiskStockTabProps {
  netting: NettingResult[]
  projections: ProjectionDay[]
  lines: PlanningLine[]
  inventory: InventoryResponse | null
  coverageContext: CoverageContext
}

export function RiskStockTab({
  netting,
  projections,
  lines,
  inventory,
  coverageContext,
}: RiskStockTabProps) {
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [openItemId, setOpenItemId] = useState<string | null>(null)

  const names = new Map(
    (inventory?.items ?? []).map((item) => [item.item_id, item.item_name]),
  )
  const lineByItem = new Map(lines.map((line) => [line.item_id, line]))

  if (netting.length === 0) {
    return <p className="text-sm text-muted-foreground">No items in this result.</p>
  }

  const rows = [...netting]
    .sort(byRisk)
    .filter((row) => !attentionOnly || needsAttention(row))

  const attention = netting.filter(needsAttention).length

  return (
    <div className="space-y-4">
      <CoverageChart
        netting={netting}
        names={names}
        context={coverageContext}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          {attention === 0
            ? `${formatCount(netting.length, 'ingredient')} covered for this decision.`
            : `${String(attention)} of ${String(netting.length)} ingredients need attention now.`}
        </p>
        <Toggle
          pressed={attentionOnly}
          onPressedChange={setAttentionOnly}
          size="sm"
        >
          Needs attention
        </Toggle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ingredient</TableHead>
              <TableHead className="text-right">In stock</TableHead>
              <TableHead className="text-right">
                <span className="inline-flex items-center gap-1">
                  To protect
                  <InfoHint label="What does “to protect” mean?">
                    Demand this ordering decision has to cover, up to the end of
                    this item&rsquo;s protection window. It is not the whole
                    uploaded forecast.
                  </InfoHint>
                </span>
              </TableHead>
              <TableHead className="text-right">On order</TableHead>
              <TableHead>
                <span className="inline-flex items-center gap-1">
                  Covered through
                  <InfoHint label="What does “covered through” mean?">
                    The end of this item&rsquo;s protection window: its lead time
                    plus the review cadence. A shortage after it is handled by a
                    later review.
                  </InfoHint>
                </span>
              </TableHead>
              <TableHead>
                <span className="inline-flex items-center gap-1">
                  With this order
                  <InfoHint label="What does the status mean?">
                    Whether this item is covered through its protection window
                    once the proposed order is placed. It is not what happens
                    if you order nothing.
                  </InfoHint>
                </span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const open = openItemId === row.item_id
              const name = names.get(row.item_id) ?? row.item_id
              const line = lineByItem.get(row.item_id) ?? null
              const disposition = riskDisposition(row)
              const shortage = row.first_stockout_within_horizon_date

              return (
                <Fragment key={row.item_id}>
                  <TableRow>
                    <TableCell className="font-medium">
                      {/* A real button, not a click handler on the row: the
                          detail has to be reachable by keyboard, and on touch
                          a bare row handler selects text instead of opening. */}
                      <button
                        type="button"
                        aria-expanded={open}
                        onClick={() => {
                          setOpenItemId(open ? null : row.item_id)
                        }}
                        className="-m-1 flex w-full items-center gap-1.5 rounded-md p-1 text-left select-none hover:text-accent-text focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      >
                        <ChevronRight
                          aria-hidden="true"
                          className={`size-3.5 shrink-0 text-muted-foreground transition-transform duration-150 ${
                            open ? 'rotate-90' : ''
                          }`}
                        />
                        {name}
                      </button>
                    </TableCell>
                    <TableCell className="text-right tabular">
                      {formatGrams(row.opening_on_hand_g)}
                    </TableCell>
                    {/* Demand for this decision, from the planning line — not
                        the full-forecast total, which spans a longer window. */}
                    <TableCell className="text-right tabular">
                      {line === null
                        ? '—'
                        : formatGrams(line.gross_requirement_g)}
                    </TableCell>
                    <TableCell className="text-right tabular">
                      {formatGrams(row.open_po_due_g)}
                    </TableCell>
                    <TableCell className="tabular">
                      {shortage !== null ? (
                        <span className="text-warning">
                          short from {formatDate(shortage)}
                        </span>
                      ) : (
                        formatDate(
                          row.risk_horizon_end_date ??
                            line?.coverage_end_date ??
                            null,
                        )
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusBadge {...DISPOSITION[disposition]} />
                      {disposition === 'future_replan' &&
                        row.first_stockout_date !== null && (
                          <span className="mt-0.5 block text-xs text-faint">
                            dips again {formatDate(row.first_stockout_date)}
                          </span>
                        )}
                    </TableCell>
                  </TableRow>

                  {open && (
                    <TableRow className="bg-surface">
                      <TableCell colSpan={6} className="p-4">
                        {/* Only opacity and transform move: animating height
                            causes jank on a table row. */}
                        <motion.div
                          initial={{ opacity: 0, y: -4 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                        >
                          <ItemDetail
                            row={row}
                            line={line}
                            disposition={disposition}
                            days={projections.filter(
                              (day) => day.item_id === row.item_id,
                            )}
                          />
                        </motion.div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

/**
 * The expanded row: a short status line and the chart.
 *
 * Deliberately terse. The table row already states covered-through and the
 * status badge, so a full sentence repeating them costs a line of visual
 * weight for nothing. Full-forecast totals were removed for the same reason:
 * they were three numbers nobody was acting on.
 */
function ItemDetail({
  row,
  line,
  disposition,
  days,
}: {
  row: NettingResult
  line: PlanningLine | null
  disposition: RiskDisposition
  days: ProjectionDay[]
}) {
  const horizonEnd = row.risk_horizon_end_date ?? line?.coverage_end_date ?? null
  const shortage =
    row.first_stockout_within_horizon_date ?? row.first_stockout_date

  return (
    <div>
      {disposition === 'not_evaluated' && (
        <p className="mb-2 text-xs text-warning">
          Evidence stops at{' '}
          {formatDate(row.risk_evaluated_through_date ?? horizonEnd)}, before
          this window ends.
        </p>
      )}
      {disposition === 'unavoidable' && (
        <p className="mb-2 text-xs text-danger">
          Ordering now cannot fix this — the shortfall lands before any
          delivery could arrive.
        </p>
      )}

      <StockProjectionChart
        days={days}
        horizonEndDate={horizonEnd}
        shortageDate={shortage}
      />
    </div>
  )
}
