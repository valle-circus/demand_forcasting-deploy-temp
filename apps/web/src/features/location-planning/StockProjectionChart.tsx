import { useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  XAxis,
  YAxis,
} from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import type { ChartConfig } from '@/components/ui/chart'
import { Toggle } from '@/components/ui/toggle'
import { formatDateShort, toNumber } from '@/lib/formatting'
import type { IsoDate, ProjectionDay } from '@/lib/types'

const config = {
  stockKg: { label: 'Usable stock', color: 'var(--chart-in-stock)' },
} satisfies ChartConfig

interface Point {
  date: string
  label: string
  /** Never negative: you cannot hold a negative quantity of an ingredient. */
  stockKg: number
  arrivingKg: number
  proposedKg: number
}

function toPoints(days: ProjectionDay[]): Point[] {
  return days.map((day) => {
    const closing = toNumber(day.closing_balance_g) ?? 0
    return {
      date: day.projection_date,
      label: formatDateShort(day.projection_date),
      // A negative closing balance is a running backlog, not stock on a shelf.
      // The plot shows physical stock; the backlog is stated in text beside it.
      stockKg: Math.max(0, closing) / 1000,
      arrivingKg: (toNumber(day.open_po_receipts_g) ?? 0) / 1000,
      proposedKg: (toNumber(day.candidate_receipts_g) ?? 0) / 1000,
    }
  })
}

/**
 * Projected usable stock for one item, day by day.
 *
 * Drawn with straight daily segments rather than a smoothed curve: the engine
 * evaluates the closing balance once per day, and a monotone spline would
 * appear to cross zero between two dates on which it never did.
 *
 * Defaults to this decision's horizon. The full-forecast view is a display
 * zoom only — it changes nothing about the recommendation.
 */
export function StockProjectionChart({
  days,
  horizonEndDate,
  shortageDate,
}: {
  days: ProjectionDay[]
  horizonEndDate: IsoDate | null
  shortageDate: IsoDate | null
}) {
  const [showFullForecast, setShowFullForecast] = useState(false)

  if (days.length < 2) {
    return (
      <p className="mt-2 text-xs text-muted-foreground">
        No daily projection was stored for this item.
      </p>
    )
  }

  const all = toPoints(days)
  const points =
    showFullForecast || horizonEndDate === null
      ? all
      : (() => {
          const within = all.filter((point) => point.date <= horizonEndDate)
          return within.length >= 2 ? within : all
        })()

  const arrivals = points.filter((point) => point.arrivingKg > 0)
  const proposals = points.filter((point) => point.proposedKg > 0)
  const shortageInView =
    shortageDate !== null &&
    points.some((point) => point.date === shortageDate)

  return (
    <div className="mt-2">
      <div className="mb-1 flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          Usable stock
          {horizonEndDate !== null && !showFullForecast && (
            <> through {formatDateShort(horizonEndDate)}</>
          )}
        </p>
        {horizonEndDate !== null && (
          <Toggle
            pressed={showFullForecast}
            onPressedChange={setShowFullForecast}
            size="sm"
            onClick={(event) => {
              event.stopPropagation()
            }}
          >
            Full forecast
          </Toggle>
        )}
      </div>

      <ChartContainer config={config} className="h-52 w-full">
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="stockFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-in-stock)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--chart-in-stock)" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid vertical={false} stroke="var(--circus-border)" />

          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            minTickGap={40}
            tick={{ fontSize: 11, fill: 'var(--circus-muted)' }}
          />
          <YAxis
            width={44}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: 'var(--circus-muted)' }}
            tickFormatter={(value: number) => `${String(value)} kg`}
          />

          {/* Each receipt labelled with what actually arrives. */}
          {arrivals.map((point) => (
            <ReferenceLine
              key={`arrival-${point.date}`}
              x={point.label}
              stroke="var(--chart-on-order)"
              strokeDasharray="3 3"
              label={{
                value: `On order +${point.arrivingKg.toFixed(1)} kg`,
                position: 'insideTopRight',
                fill: 'var(--chart-on-order)',
                fontSize: 10,
              }}
            />
          ))}

          {proposals.map((point) => (
            <ReferenceLine
              key={`proposed-${point.date}`}
              x={point.label}
              stroke="var(--chart-in-stock)"
              strokeDasharray="3 3"
              label={{
                value: `Proposed +${point.proposedKg.toFixed(1)} kg`,
                position: 'insideTopLeft',
                fill: 'var(--circus-accent-hover)',
                fontSize: 10,
              }}
            />
          ))}

          {/* The zero line is an axis, not an alarm. In danger red it read as a
              red x-axis under every chart, including charts that never run
              short — the dashed "Runs out" marker is what carries the warning. */}
          <ReferenceLine
            y={0}
            stroke="var(--circus-border-strong)"
            strokeWidth={1}
          />

          {shortageInView && (
            <ReferenceLine
              x={formatDateShort(shortageDate)}
              stroke="var(--circus-danger)"
              strokeDasharray="4 2"
              label={{
                value: 'Runs out',
                position: 'insideBottomRight',
                fill: 'var(--circus-danger)',
                fontSize: 10,
              }}
            />
          )}

          {horizonEndDate !== null && showFullForecast && (
            <ReferenceLine
              x={formatDateShort(horizonEndDate)}
              stroke="var(--circus-border-strong)"
              label={{
                value: 'Decision ends',
                position: 'insideTopRight',
                fill: 'var(--circus-muted)',
                fontSize: 10,
              }}
            />
          )}

          <ChartTooltip
            content={
              <ChartTooltipContent
                labelKey="label"
                formatter={(value) => `${String(Number(value).toFixed(1))} kg`}
              />
            }
          />

          <Area
            // Straight daily segments: the engine works at daily grain, so a
            // smoothed curve would imply crossings that never happened.
            type="linear"
            dataKey="stockKg"
            name="Usable stock"
            stroke="var(--chart-in-stock)"
            strokeWidth={2}
            fill="url(#stockFill)"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ChartContainer>

      {shortageDate !== null && (
        // Metadata, not prose. The daily-grain caveat is worth keeping — the
        // engine cannot say what time of day — but not worth a sentence.
        <p className="mt-1 text-xs text-muted-foreground">
          Reaches zero {formatDateShort(shortageDate)}
          <span className="text-muted-foreground"> · whole days only</span>
        </p>
      )}
    </div>
  )
}
