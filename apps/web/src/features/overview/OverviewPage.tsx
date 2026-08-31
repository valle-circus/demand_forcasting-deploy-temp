import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ErrorState } from '@/components/ErrorState'
import { InfoHint } from '@/components/InfoHint'
import { LoadingState } from '@/components/LoadingState'
import { StatusBadge } from '@/components/StatusBadge'
import type { StatusTone } from '@/components/StatusBadge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { fetchOverview } from '@/lib/apiClient'
import { isNotFound } from '@/lib/errors'
import { formatDate, formatRelativeAge } from '@/lib/formatting'
import type { OverviewLocationRow, OverviewResponse } from '@/lib/types'
import { useApiResource } from '@/lib/useApiResource'
import { byUrgency, hasCurrentResult, locationState, topAlert } from './overview'
import type { LocationState } from './overview'

const STATE_PRESENTATION: Record<
  LocationState,
  { tone: StatusTone; label: string }
> = {
  blocked: { tone: 'blocked', label: 'Blocked' },
  at_risk: { tone: 'warning', label: 'Needs an order' },
  not_evaluated: { tone: 'neutral', label: 'Not enough data' },
  stale: { tone: 'warning', label: 'Out of date' },
  no_run: { tone: 'neutral', label: 'Never run' },
  ready: { tone: 'ready', label: 'Ready' },
}

export function OverviewPage() {
  const { state, refetch } = useApiResource((signal) => fetchOverview(signal), [])

  if (state.status === 'error') {
    // No active master version yet: the first-run state, not a failure.
    if (isNotFound(state.error)) {
      return (
        <div className="mx-auto max-w-[1280px]">
          <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
          <div className="mt-6 rounded-lg border border-border px-6 py-10 text-center">
            <h2 className="text-base font-medium">Nothing to show yet</h2>
            <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
              Import the master workbook and activate it to set up your
              locations.
            </p>
            <Link
              to="/data"
              className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              Go to data &amp; settings
            </Link>
          </div>
        </div>
      )
    }
    return <ErrorState error={state.error} onRetry={refetch} />
  }

  if (state.status !== 'success') {
    return <LoadingState label="Loading overview" />
  }

  const overview = state.data
  const alert = topAlert(overview)
  const locations = [...overview.locations].sort(byUrgency)

  return (
    <div className="mx-auto max-w-[1280px] space-y-6">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Where things stand across every kitchen.
        </p>
      </header>

      <TopAlertStrip alert={alert} total={overview.locations.length} />

      <KpiRow overview={overview} />

      <LocationTable locations={locations} />
    </div>
  )
}

/**
 * The single most urgent thing, with somewhere to go.
 *
 * When nothing needs attention this becomes a calm confirmation rather than an
 * empty box — the absence of a problem is itself worth stating.
 */
function TopAlertStrip({
  alert,
  total,
}: {
  alert: ReturnType<typeof topAlert>
  total: number
}) {
  if (alert === null) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-3 text-sm">
        <StatusBadge tone="ready" label="All clear" />
        <span className="text-muted-foreground">
          {total === 1
            ? 'The kitchen is ready and covered.'
            : `All ${String(total)} kitchens are ready and covered.`}
        </span>
      </div>
    )
  }

  const presentation = STATE_PRESENTATION[alert.state]

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-2.5">
        <StatusBadge {...presentation} />
        <span className="text-sm font-medium">{alert.headline}</span>
      </div>
      <Link
        to={
          alert.state === 'blocked'
            ? '/data'
            : `/locations/${encodeURIComponent(alert.location.location_id)}`
        }
        className="inline-flex h-8 items-center gap-1 rounded-md border border-border bg-background px-3 text-xs font-medium transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {alert.action}
        <ArrowRight aria-hidden="true" className="size-3.5" />
      </Link>
    </div>
  )
}

/**
 * Five numbers, each a link to the view that explains it.
 *
 * A count that cannot navigate is decoration. Counts derived from planning
 * results render as unknown rather than zero when no current run backs them,
 * because zero would claim an all-clear nobody established.
 */
function KpiRow({ overview }: { overview: OverviewResponse }) {
  const { kpis } = overview
  const known = hasCurrentResult(overview)

  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Kpi
        label="Kitchens ready"
        value={`${String(kpis.locations_ready)} of ${String(kpis.locations_total)}`}
        to="/data"
      />
      <Kpi
        label="Kitchens needing an order"
        value={known ? String(kpis.locations_at_risk) : null}
        tone={kpis.locations_at_risk > 0 ? 'warning' : undefined}
      />
      <Kpi
        label="Ingredients needing an order"
        value={known ? String(kpis.items_at_risk) : null}
        tone={kpis.items_at_risk > 0 ? 'warning' : undefined}
        hint="Ingredients short within the window the current order has to cover. A shortage after that is handled by a later review."
      />
      <Kpi
        label="Not fully checked"
        value={known ? String(kpis.items_risk_not_evaluated) : null}
        hint="The evidence did not reach the end of the item's protection window, so it could be neither confirmed nor ruled out."
      />
      <Kpi
        label="Blocking issues"
        value={String(kpis.blocking_issues)}
        tone={kpis.blocking_issues > 0 ? 'blocked' : undefined}
        to="/data"
      />
    </ul>
  )
}

function Kpi({
  label,
  value,
  tone,
  to,
  hint,
}: {
  label: string
  /** Null renders as "not known", which is not the same as zero. */
  value: string | null
  tone?: 'warning' | 'blocked'
  to?: string
  hint?: string
}) {
  const body = (
    <>
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        {label}
        {hint !== undefined && <InfoHint label={label}>{hint}</InfoHint>}
      </span>
      <span
        className={[
          'mt-1 block text-2xl font-semibold tabular',
          value === null
            ? 'text-faint'
            : tone === 'blocked'
              ? 'text-danger'
              : tone === 'warning'
                ? 'text-warning'
                : '',
        ].join(' ')}
      >
        {value ?? 'not known'}
      </span>
    </>
  )

  return (
    <li>
      {to === undefined ? (
        <div className="rounded-lg border border-border px-4 py-3">{body}</div>
      ) : (
        <Link
          to={to}
          className="block rounded-lg border border-border px-4 py-3 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {body}
        </Link>
      )}
    </li>
  )
}

function LocationTable({ locations }: { locations: OverviewLocationRow[] }) {
  if (locations.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No active locations in the master data.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Kitchen</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Needs an order</TableHead>
            <TableHead>First shortage</TableHead>
            <TableHead>Stock counted</TableHead>
            <TableHead>Last calculated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {locations.map((row) => {
            const state = locationState(row)
            const stock = row.sources.stock
            return (
              <TableRow key={row.location_id}>
                <TableCell className="font-medium">
                  <Link
                    to={`/locations/${encodeURIComponent(row.location_id)}`}
                    className="hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    {row.location_name}
                  </Link>
                </TableCell>
                <TableCell>
                  <StatusBadge {...STATE_PRESENTATION[state]} />
                </TableCell>
                <TableCell className="text-right tabular">
                  {/* Blank rather than 0 when no current run backs the count. */}
                  {row.latest_run_is_current ? row.items_at_risk : '—'}
                </TableCell>
                <TableCell className="tabular">
                  {row.earliest_risk_date === null
                    ? '—'
                    : formatDate(row.earliest_risk_date)}
                </TableCell>
                <TableCell className="tabular">
                  {stock === null
                    ? '—'
                    : formatRelativeAge(stock.source_as_of_at ?? stock.created_at)}
                </TableCell>
                <TableCell className="tabular">
                  {row.latest_run === null
                    ? 'never'
                    : formatRelativeAge(row.latest_run.created_at)}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
