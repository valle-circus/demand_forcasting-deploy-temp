import { useState } from 'react'

import { StatusBadge } from '@/components/StatusBadge'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Toggle } from '@/components/ui/toggle'
import { formatDate, formatGrams } from '@/lib/formatting'
import type {
  InventoryResponse,
  NettingResult,
  ProjectionDay,
} from '@/lib/types'
import { ItemProjectionChart } from './ItemProjectionChart'
import { byRisk, riskLevel } from './planning'
import type { RiskLevel } from './planning'

const RISK_PRESENTATION: Record<
  RiskLevel,
  { tone: 'blocked' | 'warning' | 'ready'; label: string }
> = {
  // Ordering now cannot fix this — the shortfall lands before anything arrives.
  unavoidable: { tone: 'blocked', label: 'Too late to fix' },
  stockout: { tone: 'warning', label: 'Runs out' },
  ok: { tone: 'ready', label: 'Covered' },
}

interface RiskStockTabProps {
  netting: NettingResult[]
  projections: ProjectionDay[]
  inventory: InventoryResponse | null
}

export function RiskStockTab({
  netting,
  projections,
  inventory,
}: RiskStockTabProps) {
  const [riskOnly, setRiskOnly] = useState(false)
  const [openItem, setOpenItem] = useState<NettingResult | null>(null)

  const names = new Map(
    (inventory?.items ?? []).map((item) => [item.item_id, item.item_name]),
  )

  const rows = [...netting]
    .sort(byRisk)
    .filter((row) => !riskOnly || riskLevel(row) !== 'ok')

  const atRisk = netting.filter((row) => riskLevel(row) !== 'ok').length

  if (netting.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No items in this result.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {atRisk === 0
            ? 'Every item is covered through the horizon.'
            : `${String(atRisk)} of ${String(netting.length)} items run out.`}
        </p>
        <Toggle pressed={riskOnly} onPressedChange={setRiskOnly} size="sm">
          At risk only
        </Toggle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead className="text-right">On hand</TableHead>
              <TableHead className="text-right">Needed</TableHead>
              <TableHead className="text-right">On order</TableHead>
              <TableHead>Runs out</TableHead>
              <TableHead className="text-right">Ends at</TableHead>
              <TableHead>Risk</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const level = riskLevel(row)
              const presentation = RISK_PRESENTATION[level]
              return (
                <TableRow
                  key={row.item_id}
                  onClick={() => {
                    setOpenItem(row)
                  }}
                  className="cursor-pointer"
                >
                  <TableCell className="font-medium">
                    {names.get(row.item_id) ?? row.item_id}
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
                  <TableCell className="tabular">
                    {row.first_stockout_date === null
                      ? '—'
                      : formatDate(row.first_stockout_date)}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {formatGrams(row.ending_projected_balance_g)}
                  </TableCell>
                  <TableCell>
                    <StatusBadge {...presentation} />
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      <Sheet
        open={openItem !== null}
        onOpenChange={(open) => {
          if (!open) {
            setOpenItem(null)
          }
        }}
      >
        <SheetContent className="w-full sm:max-w-md">
          {openItem !== null && (
            <>
              <SheetHeader>
                <SheetTitle>
                  {names.get(openItem.item_id) ?? openItem.item_id}
                </SheetTitle>
                <SheetDescription>
                  Projected balance over the planning horizon.
                </SheetDescription>
              </SheetHeader>
              <div className="px-4 pb-4">
                {/* Only the opened item's days are drawn: the run payload
                    carries every item across every day. */}
                <ItemProjectionChart
                  days={projections.filter(
                    (day) => day.item_id === openItem.item_id,
                  )}
                />
                <dl className="mt-4 space-y-2 text-xs">
                  <Row label="Lowest balance">
                    {formatGrams(openItem.minimum_projected_balance_g)}
                  </Row>
                  <Row label="Overdue on order">
                    {formatGrams(openItem.overdue_open_po_g)}
                  </Row>
                  <Row label="Shortfall before any delivery">
                    {formatGrams(openItem.unavoidable_pre_candidate_stockout_g)}
                  </Row>
                </dl>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function Row({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="tabular">{children}</dd>
    </div>
  )
}
