import { useCallback, useId, useState } from 'react'

import { useSelectedLocation } from '../../app/location/locationContext'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import {
  fetchLocations,
  fetchPlanningStatus,
  importMasterData,
  importPlanningInput,
  importPurchaseOrders,
  importStock,
  listImports,
  listMasterVersions,
} from '../../lib/apiClient'
import type { UploadOptions } from '../../lib/apiClient'
import { isNotFound } from '../../lib/errors'
import {
  browserTimeZone,
  fromLocalInputValue,
  nowWithOffset,
  toLocalInputValue,
} from '../../lib/formatting'
import type { DatasetType, SourceImport } from '../../lib/types'
import { useApiResource } from '../../lib/useApiResource'
import { MasterVersionList } from './MasterVersionList'
import { PlannedFeatureCard } from './PlannedFeatureCard'
import { UploadCard } from './UploadCard'
import {
  DATASETS,
  currentImport,
  importHistory,
  prerequisiteFor,
} from './datasets'

export function DataSettingsPage() {
  const { locationId, setLocationId } = useSelectedLocation()
  const locationSelectId = useId()
  const asOfId = useId()

  const [poAsOf, setPoAsOf] = useState(() => toLocalInputValue())

  const imports = useApiResource((signal) => listImports({}, signal), [])
  const versions = useApiResource((signal) => listMasterVersions(signal), [])
  const locations = useApiResource((signal) => fetchLocations(signal), [])
  const planningStatus = useApiResource(
    (signal) => fetchPlanningStatus(locationId ?? '', signal),
    [locationId],
    { enabled: locationId !== null },
  )

  const refreshAll = useCallback(() => {
    imports.refetch()
    versions.refetch()
    locations.refetch()
    planningStatus.refetch()
  }, [imports, versions, locations, planningStatus])

  // This page is where a missing master version gets fixed, so a 404 from
  // /locations must not stop it from rendering.
  const locationList =
    locations.state.status === 'success' ? locations.state.data.locations : []
  // A 404 is the expected first-run case and is explained by the select below;
  // anything else is a genuine failure worth surfacing.
  const locationsError =
    locations.state.status === 'error' && !isNotFound(locations.state.error)
      ? locations.state.error
      : null

  if (imports.state.status === 'error') {
    return <ErrorState error={imports.state.error} onRetry={refreshAll} />
  }
  if (versions.state.status === 'error') {
    return <ErrorState error={versions.state.error} onRetry={refreshAll} />
  }
  if (imports.state.status !== 'success' || versions.state.status !== 'success') {
    return <LoadingState label="Loading imports and versions…" />
  }

  const allImports: SourceImport[] = imports.state.data
  const knownImportIds = new Set(allImports.map((entry) => entry.id))
  const masterVersions = versions.state.data
  const hasActiveMasterVersion = masterVersions.some(
    (version) => version.status === 'active',
  )

  const selectedLocation =
    locationList.find((entry) => entry.location_id === locationId) ?? null
  const locationTimeZone = selectedLocation?.timezone ?? browserTimeZone()

  const planningInputCoversLocation =
    planningStatus.state.status === 'success' &&
    planningStatus.state.data.sources.planning_input !== null

  const readiness = {
    hasActiveMasterVersion,
    hasLocations: locationList.length > 0,
    selectedLocationId: locationId,
    planningInputCoversLocation,
  }

  const uploaders: Record<
    DatasetType,
    (files: File[], options: UploadOptions) => Promise<SourceImport>
  > = {
    master_data: (files, options) => importMasterData(files[0], options),
    planning_input: (files, options) => importPlanningInput(files[0], options),
    stock: (files, options) => importStock(files[0], locationId ?? '', options),
    purchase_orders: (files, options) =>
      importPurchaseOrders(
        files,
        locationId ?? '',
        // The input has no offset of its own; the API rejects a naive value.
        fromLocalInputValue(poAsOf) ?? nowWithOffset(),
        options,
      ),
  }

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-stone-200 bg-white p-5">
        <h2 className="text-base font-semibold text-stone-950">
          Planning inputs
        </h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-stone-600">
          These four sources feed every recommendation. They must be imported in
          order: the planning workbook is validated against the active master
          version, and a stock export is validated against the item set that
          workbook defines.
        </p>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">
          Uploading never runs planning and never activates a draft. Both are
          separate, deliberate actions.
        </p>

        <div className="mt-5 border-t border-stone-200 pt-4">
          <label
            htmlFor={locationSelectId}
            className="block text-sm font-medium text-stone-800"
          >
            Location for steps 3 and 4
          </label>
          <select
            id={locationSelectId}
            value={locationId ?? ''}
            disabled={locationList.length === 0}
            onChange={(event) => {
              setLocationId(event.target.value)
            }}
            className="mt-1.5 w-full max-w-sm rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-950 focus:border-lime-600 focus:ring-2 focus:ring-lime-600/30 focus:outline-none disabled:bg-stone-100 disabled:text-stone-500"
          >
            <option value="" disabled>
              {locationList.length === 0
                ? 'No locations until a master version is active'
                : 'Choose a location'}
            </option>
            {locationList.map((entry) => (
              <option key={entry.location_id} value={entry.location_id}>
                {entry.location_name} ({entry.location_id})
              </option>
            ))}
          </select>
        </div>

        {locationsError !== null && (
          <div className="mt-4">
            <ErrorState
              error={locationsError}
              onRetry={refreshAll}
              title="Locations could not be loaded"
            />
          </div>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        {DATASETS.map((definition) => {
          const scoped = definition.scope === 'location'
          const scopeKey = scoped ? locationId : null
          const prerequisite = prerequisiteFor(definition.key, readiness)

          return (
            <UploadCard
              key={definition.key}
              definition={definition}
              prerequisite={prerequisite}
              current={currentImport(allImports, definition.key, scopeKey)}
              history={importHistory(allImports, definition.key, scopeKey)}
              timeZone={scoped ? locationTimeZone : browserTimeZone()}
              scopeLabel={
                scoped
                  ? `Location: ${selectedLocation?.location_name ?? 'none selected'}`
                  : 'Applies to every location'
              }
              knownImportIds={knownImportIds}
              upload={(files, options) =>
                uploaders[definition.key](files, options)
              }
              onImported={refreshAll}
              extraControls={
                definition.key === 'purchase_orders' ? (
                  <div>
                    <label
                      htmlFor={asOfId}
                      className="block text-xs font-medium text-stone-800"
                    >
                      Documents observed as of
                    </label>
                    <input
                      id={asOfId}
                      type="datetime-local"
                      value={poAsOf}
                      onChange={(event) => {
                        setPoAsOf(event.target.value)
                      }}
                      className="mt-1 rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-950 focus:border-lime-600 focus:ring-2 focus:ring-lime-600/30 focus:outline-none"
                    />
                    <p className="mt-1 text-xs text-stone-500">
                      Decides which supplier lines still count as open. Use the
                      time you exported the PDFs, not now, if they are older.
                    </p>
                  </div>
                ) : undefined
              }
            />
          )
        })}
      </div>

      <section className="space-y-5">
        <div>
          <h2 className="text-base font-semibold text-stone-950">
            Maintained data & rules
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-stone-600">
            Versioned data that changes rarely. Observed stock and purchase-order
            lines are never edited here — correct them by re-exporting the
            source or fixing the item mapping in master data.
          </p>
        </div>

        <MasterVersionList
          versions={masterVersions}
          timeZone={browserTimeZone()}
          onActivated={refreshAll}
        />

        <div className="grid gap-4 lg:grid-cols-3">
          <PlannedFeatureCard
            title="Items & item policies"
            description="Edit supplier mapping, pack and order units, storage class, lead time, shelf life, safety and yield, max cover, MOQ, and case multiple in a validated draft."
            reason="Field-level editing needs draft, validation and change-history contracts that are not built yet. Until then, the master workbook is the write path."
          />
          <PlannedFeatureCard
            title="Menu calendar"
            description="Review and adjust the weekly menu without re-importing the whole planning workbook."
            reason="Waiting on agreed version and activation semantics for planning input, which are separate from master data."
          />
          <PlannedFeatureCard
            title="Bill of materials"
            description="Adjust dish, silo and ingredient quantities per portion."
            reason="Deferred until referential and effective-date validation are agreed — a bad BOM edit silently changes every recommendation."
          />
        </div>
      </section>
    </div>
  )
}
