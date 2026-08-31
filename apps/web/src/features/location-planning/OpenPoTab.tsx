import { useState } from 'react'

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
import {
  formatCount,
  formatDate,
  formatGrams,
  formatQuantity,
  toNumber,
} from '@/lib/formatting'
import type { InventoryResponse, PurchaseOrdersResponse } from '@/lib/types'

/**
 * Observed supplier lines, read from imported PDFs.
 *
 * The caveat is permanent and undismissable: these are documents someone
 * exported, not a live feed from the supplier portal. A line can be fulfilled,
 * cancelled or rescheduled without this view knowing.
 */
export function OpenPoTab({
  data,
  inventory,
}: {
  data: PurchaseOrdersResponse
  inventory: InventoryResponse | null
}) {
  const [openOnly, setOpenOnly] = useState(true)

  const lines = data.lines.filter(
    (line) => !openOnly || line.derived_status === 'open',
  )

  // `open_qty_units` counts packs, and the engine converts with
  // `open_qty_units * pack_size_g` (netting.py). The same pack size is applied
  // here so the weight on screen matches what netting used. Only possible for
  // a line matched to an item present in the stock snapshot.
  const packSizes = new Map(
    (inventory?.items ?? []).map((item) => [
      item.item_id,
      toNumber(item.pack_size_g),
    ]),
  )

  function weightOf(itemId: string | null, packs: number | null): string | null {
    if (itemId === null || packs === null) {
      return null
    }
    const packSize = packSizes.get(itemId) ?? null
    return packSize === null ? null : formatGrams(packs * packSize)
  }

  return (
    <div className="space-y-3">
      <p className="rounded-lg border border-border bg-surface px-4 py-2.5 text-xs text-muted-foreground">
        Read from imported PDFs, not confirmed by the supplier. Upload newer
        documents to refresh.
      </p>

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {formatCount(data.summary.document_count, 'document')} ·{' '}
          {formatCount(data.summary.open_line_count, 'open line')}
          {data.summary.unmapped_line_count > 0 &&
            ` · ${String(data.summary.unmapped_line_count)} unmatched`}
        </p>
        <Toggle pressed={openOnly} onPressedChange={setOpenOnly} size="sm">
          Open only
        </Toggle>
      </div>

      {lines.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No lines match this filter.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Document</TableHead>
                <TableHead>Item</TableHead>
                <TableHead>Ordered</TableHead>
                <TableHead>Expected</TableHead>
                <TableHead className="text-right">Open</TableHead>
                <TableHead>Matched</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={`${line.import_id}-${line.po_line_id}`}>
                  <TableCell className="tabular">{line.po_id}</TableCell>
                  <TableCell>
                    <span className="block font-medium">
                      {line.item_id ?? line.supplier_description}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {line.supplier_article_number}
                    </span>
                  </TableCell>
                  <TableCell className="tabular">
                    {formatDate(line.ordered_at)}
                  </TableCell>
                  <TableCell className="tabular">
                    {line.expected_receipt_at === null ? (
                      // No Liefertag, so it is held out of dated netting.
                      <span className="text-warning">no date</span>
                    ) : (
                      formatDate(line.expected_receipt_at)
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {formatQuantity(line.open_qty_units, 'packs')}
                    {(() => {
                      const weight = weightOf(
                        line.item_id,
                        toNumber(line.open_qty_units),
                      )
                      return weight === null ? null : (
                        <span className="block text-xs text-muted-foreground">
                          {weight}
                        </span>
                      )
                    })()}
                  </TableCell>
                  <TableCell>
                    {line.mapping_status === 'mapped' ? (
                      <StatusBadge tone="ready" label="Matched" />
                    ) : (
                      <StatusBadge tone="warning" label="No match" />
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
