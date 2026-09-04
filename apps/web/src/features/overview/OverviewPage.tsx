import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ErrorState } from '@/components/ErrorState'
import { InfoHint } from '@/components/InfoHint'
import { LoadingState } from '@/components/LoadingState'
import { RefreshErrorNotice } from '@/components/RefreshErrorNotice'
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
import { resourceKeys } from '@/lib/resourceCache'
import type { OverviewLocationRow, OverviewResponse } from '@/lib/types'
import { useApiResource } from '@/lib/useApiResource'
import { byUrgency, hasCurrentResult, locationState, topAlert } from './overview'
import type { LocationState } from './overview'

const STATE_PRESENTATION: Record<
  LocationState,
  { tone: StatusTone; label: string }
> = {
  blocked: { tone: 'blocked', label: 'Blocked' },
  at_risk: { tone: 'blocked', label: 'Proposal insufficient' },
  not_evaluated: { tone: 'neutral', label: 'Not enough data' },
  needs_order: { tone: 'warning', label: 'Needs an order' },
  stale: { tone: 'warning', label: 'Out of date' },
  no_run: { tone: 'neutral', label: 'Never run' },
  ready: { tone: 'ready', label: 'Ready' },
}

export function OverviewPage() {
  const { state, refetch } = useApiResource(
    resourceKeys.overview,
    (signal) => fetchOverview(signal),
  )

  if (state.status === 'error') {
    // No active master version yet: the first-run state, not a failure.
    if (isNotFound(state.error)) {
      return (
        <div className="mx-auto max-w-[1280px]">
          <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
          <div className="mt-6 rounded-xl border border-border bg-card px-6 py-10 text-center">
            <h2 className="text-base font-medium">Nothing to show yet</h2>
            <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
              Import the master workbook and activate it to set up your
              locations.
            </p>
            <Link
              to="/data"
              className="mt-5 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
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
    <div className="mx-auto max-w-[1280px]">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Where things stand across every kitchen.
        </p>
      </header>

      {/* Deliberately three different gaps. A single `space-y-*` gives the
          header, the summary and the table the same distance, and then nothing
          on the page reads as grouped with anything else. */}
      <div className="mt-10 space-y-4">
        <RefreshErrorNotice error={state.refreshError} onRetry={refetch} />
        <TopAlertStrip alert={alert} total={overview.locations.length} />
        <KpiRow overview={overview} />
      </div>

      <div className="mt-8">
        <LocationTable locations={locations} />
      </div>
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
      <div className="flex items-center gap-2.5 rounded-xl border border-border bg-card px-5 py-4 text-sm">
        <StatusBadge tone="ready" label="All clear" />
        <span className="text-muted-foreground">
          {total === 1
            ? 'No order or data action is required.'
            : `No order or data action is required across ${String(total)} kitchens.`}
        </span>
      </div>
    )
  }

  const presentation = STATE_PRESENTATION[alert.state]

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card px-5 py-4"
    >
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
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border-strong bg-card px-3.5 text-xs font-medium transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
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
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <Kpi
        label="Kitchens ready to plan"
        value={`${String(kpis.locations_ready)} of ${String(kpis.locations_total)}`}
        to="/data"
      />
      <Kpi
        label="Kitchens needing an order"
        value={known ? String(kpis.locations_requiring_order) : null}
        tone={kpis.locations_requiring_order > 0 ? 'warning' : undefined}
      />
      <Kpi
        label="Ingredients needing an order"
        value={known ? String(kpis.items_requiring_order) : null}
        tone={kpis.items_requiring_order > 0 ? 'warning' : undefined}
        hint="Ingredients whose accepted stock and open orders do not cover the current protection window. The proposed order is not counted here."
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
      <span className="flex items-start gap-1 text-[13px] text-muted-foreground">
        {label}
        {hint !== undefined && <InfoHint label={label}>{hint}</InfoHint>}
      </span>
      {/* `mt-auto` pins every value to the bottom of its tile, so the numbers
          share a baseline no matter how many lines the label above wraps to.
          30px, and the status tokens are the calmer brand pairs now, so a
          non-zero count reads as noteworthy rather than as an alarm. */}
      <span
        className={[
          'mt-auto block pt-3 text-3xl leading-none font-semibold tracking-tight tabular',
          value === null
            ? 'text-muted-foreground'
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

  const shell =
    'flex h-full flex-col rounded-xl border border-border bg-card px-5 py-4'

  return (
    <li>
      {to === undefined ? (
        <div className={shell}>{body}</div>
      ) : (
        <Link
          to={to}
          className={`${shell} transition-colors hover:border-border-strong hover:bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none`}
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
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
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
                  {row.latest_run_is_current
                    ? row.items_requiring_order
                    : '—'}
                </TableCell>
                <TableCell className="tabular">
                  {row.earliest_order_required_date === null
                    ? '—'
                    : formatDate(row.earliest_order_required_date)}
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
