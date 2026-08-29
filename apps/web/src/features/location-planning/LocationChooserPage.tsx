import { Link } from 'react-router-dom'

import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { fetchLocations } from '../../lib/apiClient'
import { isNotFound } from '../../lib/errors'
import { useApiResource } from '../../lib/useApiResource'

/**
 * Shown at `/locations` when no location has been selected yet.
 *
 * It also carries the application's first-run state. `GET /locations` returns
 * **404** — not an empty list — when no active master-data version exists for
 * the API's environment, because the API resolves locations through that
 * version. Treating that 404 as an error would tell a maintainer on a fresh
 * environment that something is broken, when in fact they simply have not
 * imported the master workbook yet.
 */
export function LocationChooserPage() {
  const { state, refetch } = useApiResource(
    (signal) => fetchLocations(signal),
    [],
  )

  if (state.status === 'loading' || state.status === 'idle') {
    return <LoadingState label="Loading locations…" />
  }

  if (state.status === 'error') {
    if (isNotFound(state.error)) {
      return (
        <EmptyState
          tone="attention"
          title="No active master data yet"
          description={
            <>
              <p>
                Locations come from the active master-data version, and this
                environment does not have one yet. Import the master workbook in
                Data &amp; settings, then activate it — nothing else in the
                workspace can load until then.
              </p>
              <p className="mt-2">
                Importing creates a draft. Activation is a separate, deliberate
                step.
              </p>
            </>
          }
          action={{ label: 'Go to Data & settings', to: '/data' }}
        />
      )
    }
    return <ErrorState error={state.error} onRetry={refetch} />
  }

  const { locations } = state.data

  if (locations.length === 0) {
    return (
      <EmptyState
        tone="attention"
        title="No active locations"
        description="The active master-data version contains no locations marked active. Check the Locations sheet of the master workbook and import a corrected version."
        action={{ label: 'Go to Data & settings', to: '/data' }}
      />
    )
  }

  return (
    <section aria-labelledby="choose-location-heading">
      <h2
        id="choose-location-heading"
        className="text-sm font-semibold text-stone-700"
      >
        Choose a location to plan
      </h2>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {locations.map((location) => (
          <li key={location.location_id}>
            <Link
              to={`/locations/${encodeURIComponent(location.location_id)}`}
              className="block rounded-xl border border-stone-200 bg-white p-4 transition hover:border-stone-400 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:outline-none"
            >
              <span className="block text-sm font-semibold text-stone-950">
                {location.location_name}
              </span>
              <span className="mt-1 block text-xs text-stone-500">
                {location.location_id} · {location.timezone}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
