import { formatDateTime, formatRelativeAge } from '@/lib/formatting'
import type { IsoDateTime } from '@/lib/types'

interface FreshnessStampProps {
  /** When the source system produced the data. Null if it states no time. */
  sourceAt: IsoDateTime | null
  /** When this workspace accepted the import. */
  importedAt: IsoDateTime
  timeZone: string
  /** What the source time means here, e.g. "Counted" or "Ordered". */
  sourceLabel?: string
}

/**
 * Source time and import time, as two separate values.
 *
 * Collapsing them into one "last updated" is the mistake this product exists
 * to avoid: a supplier PDF imported five minutes ago can describe orders from
 * last week, and a stock export uploaded today may have been counted on
 * Friday. Imported is not the same as true.
 */
export function FreshnessStamp({
  sourceAt,
  importedAt,
  timeZone,
  sourceLabel = 'Source',
}: FreshnessStampProps) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs tabular">
      <dt className="text-muted-foreground">{sourceLabel}</dt>
      <dd>
        {sourceAt === null ? (
          <span className="text-muted-foreground">not stated in the file</span>
        ) : (
          <>
            {formatDateTime(sourceAt, timeZone)}
            <span className="text-muted-foreground">
              {' '}
              · {formatRelativeAge(sourceAt)}
            </span>
          </>
        )}
      </dd>

      <dt className="text-muted-foreground">Imported</dt>
      <dd>
        {formatDateTime(importedAt, timeZone)}
        <span className="text-muted-foreground">
          {' '}
          · {formatRelativeAge(importedAt)}
        </span>
      </dd>
    </dl>
  )
}
