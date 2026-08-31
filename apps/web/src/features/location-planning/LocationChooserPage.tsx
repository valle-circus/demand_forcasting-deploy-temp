import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { fetchLocations } from '@/lib/apiClient'
import { isNotFound } from '@/lib/errors'
import { useApiResource } from '@/lib/useApiResource'

/**
 * Shown at `/locations` before a location is chosen, and carrying the
 * application's first-run state.
 *
 * `GET /locations` returns 404 — not an empty list — when no master-data
 * version is active, because the API resolves locations through that version.
 * Treating that as an error would tell a maintainer on a fresh environment
 * that something is broken when they have simply not imported anything yet.
 */
export function LocationChooserPage() {
  const { state, refetch } = useApiResource((signal) => fetchLocations(signal), [])

  if (state.status === 'loading' || state.status === 'idle') {
    return <LoadingState label="Loading locations" />
  }

  if (state.status === 'error') {
    if (isNotFound(state.error)) {
      return (
        <EmptyState
          title="No master data yet"
          description="Import the master workbook and activate it. Nothing can load until then."
          action={{ label: 'Go to data & settings', to: '/data' }}
        />
      )
    }
    return <ErrorState error={state.error} onRetry={refetch} />
  }

  const { locations } = state.data

  if (locations.length === 0) {
    return (
      <EmptyState
        title="No active locations"
        description="The active master version has no locations marked active."
        action={{ label: 'Go to data & settings', to: '/data' }}
      />
    )
  }

  return (
    <div className="mx-auto max-w-[1280px] space-y-4">
      <h1 className="text-3xl font-semibold tracking-tight">Location planning</h1>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {locations.map((location) => (
          <li key={location.location_id}>
            <Link
              to={`/locations/${encodeURIComponent(location.location_id)}`}
              className="block rounded-lg border border-border px-4 py-3 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span className="block text-sm font-medium">
                {location.location_name}
              </span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                {location.timezone}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
