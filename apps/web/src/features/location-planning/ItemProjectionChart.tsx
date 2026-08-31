import { formatDateShort, formatGrams, toNumber } from '@/lib/formatting'
import type { ProjectionDay } from '@/lib/types'

/**
 * Projected closing balance for one item across the horizon.
 *
 * Deliberately a hand-drawn SVG rather than the charting stack: one series, no
 * legend, no categorical colour, no axis labels beyond the endpoints. The one
 * thing that must be unmissable is where the line crosses zero, because that
 * is the stockout. Revisit if this ever needs more than a single series.
 */
export function ItemProjectionChart({ days }: { days: ProjectionDay[] }) {
  if (days.length < 2) {
    return null
  }

  const values = days.map((day) => toNumber(day.closing_balance_g) ?? 0)
  const max = Math.max(...values, 0)
  const min = Math.min(...values, 0)
  const span = max - min || 1

  const width = 100
  const height = 32
  const x = (index: number) => (index / (days.length - 1)) * width
  const y = (value: number) => height - ((value - min) / span) * height

  const path = values
    .map((value, index) => `${index === 0 ? 'M' : 'L'}${String(x(index))},${String(y(value))}`)
    .join(' ')

  const firstShortfall = values.findIndex((value) => value <= 0)

  return (
    <figure className="mt-1">
      <svg
        viewBox={`0 0 ${String(width)} ${String(height)}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Projected balance from ${formatGrams(values[0])} to ${formatGrams(values[values.length - 1])}`}
        className="h-16 w-full"
      >
        {/* Zero line: below it the item has run out. */}
        <line
          x1="0"
          x2={width}
          y1={y(0)}
          y2={y(0)}
          stroke="var(--circus-border-strong)"
          strokeWidth="0.5"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d={path}
          fill="none"
          stroke={
            firstShortfall === -1
              ? 'var(--circus-accent)'
              : 'var(--circus-danger)'
          }
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <figcaption className="mt-1 flex justify-between text-xs text-muted-foreground tabular">
        <span>{formatDateShort(days[0].projection_date)}</span>
        <span>{formatDateShort(days[days.length - 1].projection_date)}</span>
      </figcaption>
    </figure>
  )
}
