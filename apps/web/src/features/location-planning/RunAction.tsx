import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import type { PlanningStatusResponse } from '@/lib/types'

interface RunActionProps {
  status: PlanningStatusResponse
  running: boolean
  error: Error | null
  onRun: () => void
  /** datetime-local value; the page converts it to a tz-aware instant. */
  cutoff: string
  onCutoffChange: (value: string) => void
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
export function RunAction({
  status,
  running,
  error,
  onRun,
  cutoff,
  onCutoffChange,
}: RunActionProps) {
  const blocked = !status.ready
  const [showCutoff, setShowCutoff] = useState(false)

  return (
    <div className="flex flex-col items-end gap-1">
      <Button size="lg" disabled={blocked || running} onClick={onRun}>
        {running ? 'Calculating' : 'Compute recommendation'}
      </Button>

      {/* Behind a disclosure: the cutoff is almost always "now", but
          reproducing an earlier run needs the exact instant it used. */}
      <button
        type="button"
        onClick={() => {
          setShowCutoff((open) => !open)
        }}
        aria-expanded={showCutoff}
        className="rounded-md px-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {showCutoff ? 'Use the current time' : 'Plan as of a different time'}
      </button>

      {showCutoff && (
        <div className="flex flex-col items-end gap-1">
          <input
            type="datetime-local"
            value={cutoff}
            aria-label="Plan as of"
            onChange={(event) => {
              onCutoffChange(event.target.value)
            }}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs tabular focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          />
          <p className="max-w-xs text-right text-xs text-muted-foreground">
            The forecast must start on or after this time.
          </p>
        </div>
      )}

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
