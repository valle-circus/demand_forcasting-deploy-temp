import { formatDateTime, formatRelativeAge } from '../lib/formatting'
import type { IsoDateTime } from '../lib/types'

interface FreshnessStampProps {
  /**
   * When the source system produced the data — a stock count time, a supplier
   * document date. Null when the source carries no timestamp of its own.
   */
  sourceAt: IsoDateTime | null
  /** When this workspace accepted the import. */
  importedAt: IsoDateTime
  timeZone: string
  /** What the source timestamp means here, e.g. "Counted" or "Ordered". */
  sourceLabel?: string
}

/**
 * Shows source time and import time as two separate, labelled values.
 *
 * This is the single most important primitive in the application. Collapsing
 * the two into one "last updated" is the mistake this product exists to avoid:
 * a Transgourmet PDF imported five minutes ago can describe orders from a week
 * ago, and a stock export uploaded today can have been counted on Friday.
 * "Last imported" is not "currently true".
 */
export function FreshnessStamp({
  sourceAt,
  importedAt,
  timeZone,
  sourceLabel = 'Source time',
}: FreshnessStampProps) {
  return (
    <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-[auto_1fr]">
      <dt className="font-medium text-stone-700">{sourceLabel}</dt>
      <dd className="text-stone-600">
        {sourceAt === null ? (
          <span className="text-stone-500">
            not stated by the source file
          </span>
        ) : (
          <>
            {formatDateTime(sourceAt, timeZone)}{' '}
            <span className="text-stone-500">
              ({formatRelativeAge(sourceAt)})
            </span>
          </>
        )}
      </dd>

      <dt className="font-medium text-stone-700">Imported</dt>
      <dd className="text-stone-600">
        {formatDateTime(importedAt, timeZone)}{' '}
        <span className="text-stone-500">
          ({formatRelativeAge(importedAt)})
        </span>
      </dd>
    </dl>
  )
}
