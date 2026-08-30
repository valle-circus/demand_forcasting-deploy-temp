import { Link } from 'react-router-dom'

import { formatDate, formatRelativeAge } from '@/lib/formatting'
import type { PlanningStatusResponse } from '@/lib/types'
import { runCurrency } from './planning'

interface Item {
  label: string
  value: string
  /** Set when the value deserves attention rather than plain reading. */
  attention?: boolean
}

/**
 * The five things that decide whether a run can be trusted, on one line.
 *
 * Each source shows how old it is, because "imported" is not "true": a stock
 * export counted on Friday and imported today describes Friday.
 */
export function FreshnessStrip({
  status,
}: {
  status: PlanningStatusResponse
}) {
  const { sources } = status
  const currency = runCurrency(status)

  const items: Item[] = [
    {
      label: 'Master',
      value: sources.master_data_version?.version_label ?? 'none',
      attention: sources.master_data_version === null,
    },
    {
      label: 'Forecast to',
      value:
        sources.planning_input?.coverage_end_date === undefined ||
        sources.planning_input?.coverage_end_date === null
          ? 'none'
          : formatDate(sources.planning_input.coverage_end_date),
      attention: sources.planning_input === null,
    },
    {
      label: 'Stock counted',
      value:
        sources.stock === null
          ? 'none'
          : formatRelativeAge(
              sources.stock.source_as_of_at ?? sources.stock.created_at,
            ),
      attention: sources.stock === null,
    },
    {
      label: 'Orders imported',
      value:
        sources.purchase_orders === null
          ? 'none'
          : formatRelativeAge(sources.purchase_orders.created_at),
      attention: sources.purchase_orders === null,
    },
    {
      label: 'Run',
      value:
        currency === 'none'
          ? 'none yet'
          : currency === 'stale'
            ? 'out of date'
            : 'up to date',
      attention: currency === 'stale',
    },
  ]

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border px-4 py-2.5 text-xs">
      {items.map((item) => (
        <span key={item.label} className="flex items-baseline gap-1.5">
          <span className="text-muted-foreground">{item.label}</span>
          <span
            className={`tabular ${item.attention ? 'text-warning' : 'text-foreground'}`}
          >
            {item.value}
          </span>
        </span>
      ))}
      <Link
        to="/data"
        className="ml-auto text-accent-text underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        Update sources
      </Link>
    </div>
  )
}
