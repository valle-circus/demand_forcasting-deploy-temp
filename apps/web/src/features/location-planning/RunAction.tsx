import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import type { PlanningStatusResponse } from '@/lib/types'

interface RunActionProps {
  status: PlanningStatusResponse
  running: boolean
  error: Error | null
  onRun: () => void
}

/**
 * The one primary action on this page.
 *
 * The run is synchronous, has no job id and no idempotency key, so a second
 * submission would start a second calculation. Duplicate submission is
 * prevented in the mutation hook by an in-flight ref rather than by the
 * disabled attribute alone, because a fast second click lands before React
 * re-renders the button.
 */
export function RunAction({ status, running, error, onRun }: RunActionProps) {
  const blocked = !status.ready

  return (
    <div className="flex flex-col items-end gap-1">
      <Button size="lg" disabled={blocked || running} onClick={onRun}>
        {running ? 'Calculating' : 'Compute recommendation'}
      </Button>

      {running && (
        <p className="text-xs text-muted-foreground">
          This can take a while. Keep the tab open.
        </p>
      )}

      {error !== null && (
        <p role="alert" className="max-w-xs text-right text-xs text-danger">
          {errorMessage(error)}
        </p>
      )}

      <p aria-live="polite" className="sr-only">
        {running ? 'Calculating.' : ''}
      </p>
    </div>
  )
}

/**
 * Why the run is unavailable, in the server's own words, as visible text
 * rather than a tooltip on a disabled button.
 */
export function BlockerList({ status }: { status: PlanningStatusResponse }) {
  if (status.ready || status.blockers.length === 0) {
    return null
  }

  return (
    <div className="rounded-lg border border-border bg-surface px-4 py-3">
      <p className="text-sm font-medium text-warning">
        {status.blockers.length === 1
          ? 'One thing is missing before this can run'
          : `${String(status.blockers.length)} things are missing before this can run`}
      </p>
      <ul className="mt-2 space-y-1">
        {status.blockers.map((blocker) => (
          <li key={blocker.code} className="text-xs text-muted-foreground">
            {blocker.message}
          </li>
        ))}
      </ul>
      <Link
        to="/data"
        className="mt-3 inline-flex h-8 items-center rounded-md border border-border px-3 text-xs font-medium transition-colors hover:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        Go to data &amp; settings
      </Link>
    </div>
  )
}
