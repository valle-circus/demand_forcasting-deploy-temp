import { ChevronRight } from 'lucide-react'
import { motion } from 'motion/react'
import { Fragment, useState } from 'react'

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
  InventoryResponse,
  NettingResult,
  PlanningLine,
  ProjectionDay,
} from '@/lib/types'
import { StockProjectionChart } from './StockProjectionChart'
import { byRisk, daysOfCover, horizonDays, riskLevel } from './planning'
import type { RiskLevel } from './planning'

const RISK_PRESENTATION: Record<
  RiskLevel,
  { tone: 'blocked' | 'warning' | 'ready'; label: string }
> = {
  // Ordering now cannot fix this: the shortfall lands before anything arrives.
  unavoidable: { tone: 'blocked', label: 'Too late to fix' },
  stockout: { tone: 'warning', label: 'Runs out' },
  ok: { tone: 'ready', label: 'Covered' },
}

interface RiskStockTabProps {
  netting: NettingResult[]
  projections: ProjectionDay[]
  lines: PlanningLine[]
  inventory: InventoryResponse | null
}

export function RiskStockTab({
  netting,
  projections,
  lines,
  inventory,
}: RiskStockTabProps) {
  const [riskOnly, setRiskOnly] = useState(false)
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
    .filter((row) => !riskOnly || riskLevel(row) !== 'ok')

  const atRisk = netting.filter((row) => riskLevel(row) !== 'ok').length
  const window = netting[0]
  const horizon = horizonDays(window)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* The window every number in this table refers to, stated once. */}
        <p className="text-sm text-muted-foreground">
          {formatDate(window.projection_start_date)} –{' '}
          {formatDate(window.projection_end_date)}
          {horizon !== null && ` · ${formatCount(horizon, 'day')}`}
          {atRisk > 0 && ` · ${String(atRisk)} of ${String(netting.length)} run out`}
        </p>
        <Toggle pressed={riskOnly} onPressedChange={setRiskOnly} size="sm">
          At risk only
        </Toggle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ingredient</TableHead>
              <TableHead className="text-right">In stock</TableHead>
              <TableHead className="text-right">Needed</TableHead>
              <TableHead className="text-right">On order</TableHead>
              <TableHead className="text-right">Lasts</TableHead>
              <TableHead>Empty on</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const open = openItemId === row.item_id
              const cover = daysOfCover(row)
              const name = names.get(row.item_id) ?? row.item_id
              const line = lineByItem.get(row.item_id) ?? null

              return (
                <Fragment key={row.item_id}>
                  <TableRow
                    onClick={() => {
                      setOpenItemId(open ? null : row.item_id)
                    }}
                    aria-expanded={open}
                    className="cursor-pointer"
                  >
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-1.5">
                        <ChevronRight
                          aria-hidden="true"
                          className={`size-3.5 shrink-0 text-muted-foreground transition-transform duration-150 ${
                            open ? 'rotate-90' : ''
                          }`}
                        />
                        {name}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular">
                      {formatGrams(row.opening_on_hand_g)}
                    </TableCell>
                    <TableCell className="text-right tabular">
                      {formatGrams(row.gross_requirement_g)}
                    </TableCell>
                    <TableCell className="text-right tabular">
                      {formatGrams(row.open_po_due_g)}
                    </TableCell>
                    <TableCell className="text-right tabular">
                      {cover === null ? 'whole period' : formatCount(cover, 'day')}
                    </TableCell>
                    <TableCell className="tabular">
                      {row.first_stockout_date === null
                        ? '—'
                        : formatDate(row.first_stockout_date)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge {...RISK_PRESENTATION[riskLevel(row)]} />
                    </TableCell>
                  </TableRow>

                  {open && (
                    <TableRow className="bg-surface">
                      <TableCell colSpan={7} className="p-4">
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
                            cover={cover}
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
  cover,
  days,
}: {
  row: NettingResult
  line: PlanningLine | null
  name: string
  cover: number | null
  days: ProjectionDay[]
}) {
  return (
    <div>
      <p className="text-sm">
        {cover === null ? (
          <>
            <span className="font-medium">{name}</span> stays in stock for the
            whole period.
          </>
        ) : (
          <>
            <span className="font-medium">{name}</span> runs out in{' '}
            <span className="text-warning">{formatCount(cover, 'day')}</span>, on{' '}
            {formatDate(row.first_stockout_date)}.
          </>
        )}
      </p>

      <StockProjectionChart
        days={days}
        firstStockoutDate={row.first_stockout_date}
      />

      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
        <li>
          <span className="mr-1.5 inline-block h-0.5 w-3 align-middle bg-info" />
          Already on order
        </li>
        <li>
          <span className="mr-1.5 inline-block h-0.5 w-3 align-middle bg-primary" />
          Proposed delivery
        </li>
        <li>
          <span className="mr-1.5 inline-block h-0.5 w-3 align-middle bg-danger" />
          Empty
        </li>
      </ul>

      {/* The closing balance is meaningless without saying what it assumes. */}
      <p className="mt-3 max-w-2xl text-xs text-muted-foreground">
        Ends at {formatGrams(row.ending_projected_balance_g)}
        {line !== null && (
          <>
            {' '}
            — this run plans one delivery covering{' '}
            {formatCount(line.protection_days, 'day')}, and the projection
            assumes nothing is ordered after it
          </>
        )}
        . Shelf life limits how much may be ordered at once; it does not reduce
        what is needed.
      </p>
    </div>
  )
}
