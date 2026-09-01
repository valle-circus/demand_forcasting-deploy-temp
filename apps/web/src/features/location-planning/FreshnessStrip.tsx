import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { formatDate, formatRelativeAge } from '@/lib/formatting'
import type { PlanningStatusResponse } from '@/lib/types'
import { runCurrency } from './planning'

interface Fact {
  label: string
  value: string
  /** Worth reading twice: the value is missing or out of date. */
  attention?: boolean
}

/**
 * How trustworthy this location's inputs are.
 *
 * Only the three facts that change a decision are shown: how old the stock
 * count is, how old the supplier documents are, and whether the last result
 * still matches its inputs. Version labels and the forecast end date matter
 * when something looks wrong, so they sit behind a disclosure rather than
 * spending a line of the page every time.
 */
export function FreshnessStrip({ status }: { status: PlanningStatusResponse }) {
  const [showAll, setShowAll] = useState(false)
  const { sources } = status
  const currency = runCurrency(status)

  const primary: Fact[] = [
    {
      label: 'Stock',
      value:
        sources.stock === null
          ? 'none'
          : formatRelativeAge(
              sources.stock.source_as_of_at ?? sources.stock.created_at,
            ),
      attention: sources.stock === null,
    },
    {
      label: 'Orders',
      value:
        sources.purchase_orders === null
          ? 'none'
          : formatRelativeAge(sources.purchase_orders.created_at),
      attention: sources.purchase_orders === null,
    },
    {
      label: 'Result',
      value:
        currency === 'none'
          ? 'none yet'
          : currency === 'stale'
            ? 'out of date'
            : 'up to date',
      attention: currency !== 'current',
    },
  ]

  const secondary: Fact[] = [
    {
      label: 'Master data',
      value: sources.master_data_version?.version_label ?? 'none',
      attention: sources.master_data_version === null,
    },
    {
      label: 'Forecast to',
      value:
        sources.planning_input?.coverage_end_date == null
          ? 'none'
          : formatDate(sources.planning_input.coverage_end_date),
      attention: sources.planning_input === null,
    },
  ]

  return (
    <div className="text-xs">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {primary.map((fact) => (
          <FactValue key={fact.label} fact={fact} />
        ))}

        <button
          type="button"
          onClick={() => {
            setShowAll((open) => !open)
          }}
          aria-expanded={showAll}
          className="inline-flex items-center gap-0.5 rounded-md text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <ChevronDown
            aria-hidden="true"
            className={`size-3 transition-transform duration-150 ${
              showAll ? 'rotate-180' : ''
            }`}
          />
          {showAll ? 'Less' : 'More'}
        </button>

        <Link
          to="/data"
          className="ml-auto rounded-md text-accent-text underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          Update sources
        </Link>
      </div>

      {showAll && (
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          {secondary.map((fact) => (
            <FactValue key={fact.label} fact={fact} />
          ))}
        </div>
      )}
    </div>
  )
}

function FactValue({ fact }: { fact: Fact }) {
  return (
    <span className="flex items-baseline gap-1">
      <span className="text-muted-foreground">{fact.label}</span>
      <span
        className={`tabular ${fact.attention === true ? 'text-warning' : ''}`}
      >
        {fact.value}
      </span>
    </span>
  )
}
