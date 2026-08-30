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
import { formatDateShort, toNumber } from '@/lib/formatting'
import type { ProjectionDay } from '@/lib/types'

const config = {
  balance: { label: 'Stock', color: 'var(--circus-accent)' },
} satisfies ChartConfig

interface Point {
  date: string
  label: string
  balanceKg: number
  demandKg: number
  arrivingKg: number
  proposedKg: number
}

function toPoints(days: ProjectionDay[]): Point[] {
  return days.map((day) => ({
    date: day.projection_date,
    label: formatDateShort(day.projection_date),
    balanceKg: (toNumber(day.closing_balance_g) ?? 0) / 1000,
    demandKg: (toNumber(day.demand_g) ?? 0) / 1000,
    arrivingKg: (toNumber(day.open_po_receipts_g) ?? 0) / 1000,
    proposedKg: (toNumber(day.candidate_receipts_g) ?? 0) / 1000,
  }))
}

/**
 * Projected stock for one item, day by day.
 *
 * One series, so no legend — the heading names it. The only things that need
 * to be unmissable are where the line crosses zero and when deliveries land,
 * so those get reference lines rather than extra series. Both are also stated
 * in text beside the chart, because a status must never be colour alone.
 *
 * Every value is a persisted `planning_projection_days` row. Nothing is
 * projected in the browser.
 */
export function StockProjectionChart({
  days,
  firstStockoutDate,
}: {
  days: ProjectionDay[]
  firstStockoutDate: string | null
}) {
  if (days.length < 2) {
    return (
      <p className="text-xs text-muted-foreground">
        No daily projection was stored for this item.
      </p>
    )
  }

  const points = toPoints(days)
  const arrivals = points.filter((point) => point.arrivingKg > 0)
  const proposals = points.filter((point) => point.proposedKg > 0)

  return (
    <ChartContainer config={config} className="h-56 w-full">
      <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="stockFill" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              stopColor="var(--circus-accent)"
              stopOpacity={0.18}
            />
            <stop
              offset="100%"
              stopColor="var(--circus-accent)"
              stopOpacity={0.02}
            />
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

        {/* Deliveries already on order. */}
        {arrivals.map((point) => (
          <ReferenceLine
            key={`arrival-${point.date}`}
            x={point.label}
            stroke="var(--circus-info)"
            strokeDasharray="3 3"
          />
        ))}

        {/* The delivery this run proposes. */}
        {proposals.map((point) => (
          <ReferenceLine
            key={`proposed-${point.date}`}
            x={point.label}
            stroke="var(--circus-accent)"
            strokeDasharray="3 3"
          />
        ))}

        {/* Empty. Below this line the kitchen has run out. */}
        <ReferenceLine
          y={0}
          stroke="var(--circus-danger)"
          strokeWidth={1.5}
          label={{
            value: 'Empty',
            position: 'insideTopLeft',
            fill: 'var(--circus-danger)',
            fontSize: 11,
          }}
        />

        {firstStockoutDate !== null && (
          <ReferenceLine
            x={formatDateShort(firstStockoutDate)}
            stroke="var(--circus-danger)"
            strokeDasharray="4 2"
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
          type="monotone"
          dataKey="balanceKg"
          name="Stock"
          stroke="var(--circus-accent)"
          strokeWidth={2}
          fill="url(#stockFill)"
          dot={false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ChartContainer>
  )
}
