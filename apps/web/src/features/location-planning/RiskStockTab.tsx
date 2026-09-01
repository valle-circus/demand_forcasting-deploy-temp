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
import {
  byRisk,
  needsAttention,
  riskDisposition,
  uncoveredDemandG,
} from './planning'
import type { RiskDisposition } from './planning'

const DISPOSITION: Record<
  RiskDisposition,
  { tone: 'blocked' | 'warning' | 'ready' | 'neutral'; label: string }
> = {
  // Ordering now cannot fix this: the shortfall lands before anything arrives.
  unavoidable: { tone: 'blocked', label: 'Too late to fix' },
  at_risk: { tone: 'warning', label: 'Needs an order' },
  // Incomplete evidence. Never shown as covered, never counted as safe.
  not_evaluated: { tone: 'neutral', label: 'Not enough data' },
  // Short later in the forecast, but after this decision's horizon.
  future_replan: { tone: 'neutral', label: 'Replan later' },
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
        <p className="text-sm text-muted-foreground">
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
              <TableHead>Status</TableHead>
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
                            name={name}
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

function ItemDetail({
  row,
  line,
  name,
  disposition,
  days,
}: {
  row: NettingResult
  line: PlanningLine | null
  name: string
  disposition: RiskDisposition
  days: ProjectionDay[]
}) {
  const horizonEnd = row.risk_horizon_end_date ?? line?.coverage_end_date ?? null
  const uncovered = uncoveredDemandG(row)

  return (
    <div>
      <p className="text-sm">
        {disposition === 'covered' && (
          <>
            <span className="font-medium">{name}</span> is covered through{' '}
            {formatDate(horizonEnd)}.
          </>
        )}
        {disposition === 'future_replan' && (
          <>
            <span className="font-medium">{name}</span> is covered through{' '}
            {formatDate(horizonEnd)}. The forecast runs short on{' '}
            {formatDate(row.first_stockout_date)}, which a later review handles.
          </>
        )}
        {disposition === 'not_evaluated' && (
          <>
            <span className="font-medium">{name}</span> could not be assessed —
            the evidence does not reach{' '}
            {formatDate(horizonEnd)}
            {row.risk_evaluated_through_date !== null && (
              <> (it stops at {formatDate(row.risk_evaluated_through_date)})</>
            )}
            .
          </>
        )}
        {(disposition === 'at_risk' || disposition === 'unavoidable') && (
          <>
            <span className="font-medium">{name}</span> runs short on{' '}
            <span className="text-warning">
              {formatDate(row.first_stockout_within_horizon_date)}
            </span>
            , inside the window this decision has to cover.
            {disposition === 'unavoidable' &&
              ' Ordering now cannot fix it — the shortfall lands before any delivery could arrive.'}
          </>
        )}
      </p>

      <StockProjectionChart
        days={days}
        horizonEndDate={horizonEnd}
        shortageDate={
          row.first_stockout_within_horizon_date ?? row.first_stockout_date
        }
      />

      {/* Full-forecast context, kept clearly secondary and clearly labelled. */}
      <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
        <Detail label="Demand across the whole forecast">
          {formatGrams(row.gross_requirement_g)}
        </Detail>
        <Detail label="Balance at the end of this window">
          {formatGrams(row.projected_balance_at_risk_horizon_end_g)}
        </Detail>
        {uncovered !== null && (
          <Detail
            label={`Uncovered demand by ${formatDate(row.projection_end_date)}`}
          >
            {formatGrams(uncovered)}{' '}
            <span className="text-muted-foreground">
              if no further orders are placed
            </span>
          </Detail>
        )}
      </dl>
    </div>
  )
}

function Detail({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="tabular">{children}</dd>
    </div>
  )
}
