import { useCallback, useState } from 'react'

import { useSelectedLocation } from '@/app/location/locationContext'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { RefreshErrorNotice } from '@/components/RefreshErrorNotice'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  activateMasterVersion,
  fetchLocations,
  fetchPlanningStatus,
  importMasterData,
  importPlanningInput,
  importPurchaseOrders,
  importStock,
  listImports,
  listMasterVersions,
} from '@/lib/apiClient'
import type { UploadOptions } from '@/lib/apiClient'
import { errorMessage, isNotFound } from '@/lib/errors'
import {
  browserTimeZone,
  fromLocalInputValue,
  nowWithOffset,
  toLocalInputValue,
} from '@/lib/formatting'
import type { DatasetType, MasterDataVersion, SourceImport } from '@/lib/types'
import { resourceKeys } from '@/lib/resourceCache'
import { refreshError, useApiResource } from '@/lib/useApiResource'
import { ActivateMasterDialog } from './ActivateMasterDialog'
import { MasterVersionList } from './MasterVersionList'
import { UploadCard } from './UploadCard'
import { DATASETS, currentImport, importHistory, prerequisiteFor } from './datasets'

export function DataSettingsPage() {
  const { locationId, setLocationId } = useSelectedLocation()
  const [poAsOf, setPoAsOf] = useState(() => toLocalInputValue())
  const [pendingActivation, setPendingActivation] =
    useState<MasterDataVersion | null>(null)
  const [activating, setActivating] = useState(false)
  const [activationError, setActivationError] = useState<string | null>(null)

  const imports = useApiResource(resourceKeys.imports(), (signal) =>
    listImports({}, signal),
  )
  const versions = useApiResource(resourceKeys.masterVersions, (signal) =>
    listMasterVersions(signal),
  )
  const locations = useApiResource(resourceKeys.locations, (signal) =>
    fetchLocations(signal),
  )
  const planningStatus = useApiResource(
    resourceKeys.planningStatus(locationId ?? ''),
    (signal) => fetchPlanningStatus(locationId ?? '', signal),
    { enabled: locationId !== null },
  )

  const refreshAll = useCallback(() => {
    imports.refetch()
    versions.refetch()
    locations.refetch()
    planningStatus.refetch()
  }, [imports, versions, locations, planningStatus])

  // This page is where a missing master version gets fixed, so a 404 from
  // /locations must not stop it rendering. Anything else is a real failure.
  const locationList =
    locations.state.status === 'success' ? locations.state.data.locations : []
  const locationsError =
    locations.state.status === 'error' && !isNotFound(locations.state.error)
      ? locations.state.error
      : null
  const refreshFailure =
    refreshError(imports.state) ??
    refreshError(versions.state) ??
    refreshError(locations.state) ??
    refreshError(planningStatus.state)

  if (imports.state.status === 'error') {
    return <ErrorState error={imports.state.error} onRetry={refreshAll} />
  }
  if (versions.state.status === 'error') {
    return <ErrorState error={versions.state.error} onRetry={refreshAll} />
  }
  if (imports.state.status !== 'success' || versions.state.status !== 'success') {
    return <LoadingState label="Loading…" />
  }

  const allImports: SourceImport[] = imports.state.data
  const knownImportIds = new Set(allImports.map((entry) => entry.id))
  const masterVersions = versions.state.data
  const activeVersion =
    masterVersions.find((version) => version.status === 'active') ?? null
  // Newest first from the API, so the first draft is the one just imported.
  const latestDraft =
    masterVersions.find((version) => version.status === 'draft') ?? null

  const selectedLocation =
    locationList.find((entry) => entry.location_id === locationId) ?? null
  const locationTimeZone = selectedLocation?.timezone ?? browserTimeZone()

  const readiness = {
    hasActiveMasterVersion: activeVersion !== null,
    hasLocations: locationList.length > 0,
    selectedLocationId: locationId,
    planningInputCoversLocation:
      planningStatus.state.status === 'success' &&
      planningStatus.state.data.sources.planning_input !== null,
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
        // The input carries no offset; the API rejects a naive value.
        fromLocalInputValue(poAsOf) ?? nowWithOffset(),
        options,
      ),
  }

  async function confirmActivation() {
    if (pendingActivation === null) {
      return
    }
    setActivating(true)
    setActivationError(null)
    try {
      await activateMasterVersion(pendingActivation.id)
      setPendingActivation(null)
      refreshAll()
    } catch (error) {
      setActivationError(errorMessage(error))
      setPendingActivation(null)
    } finally {
      setActivating(false)
    }
  }

  // The one step to do next: the lowest-numbered step that is unblocked and has
  // no usable import yet. While a master draft is waiting, the next action is
  // activating it rather than another upload, so no card claims the accent.
  const nextStep =
    latestDraft !== null
      ? null
      : (DATASETS.find((definition) => {
          const scopeKey = definition.scope === 'location' ? locationId : null
          const existing = currentImport(allImports, definition.key, scopeKey)
          return (
            !prerequisiteFor(definition.key, readiness).blocked &&
            (existing === null || existing.status === 'rejected')
          )
        })?.step ?? null)

  function statusForStepOne() {
    if (activeVersion !== null) {
      return { tone: 'ready' as const, label: 'Active' }
    }
    if (latestDraft !== null) {
      return { tone: 'warning' as const, label: 'Draft ready' }
    }
    return undefined
  }

  return (
    <div className="mx-auto max-w-[1280px]">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Data &amp; settings
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Import the four sources in order. Uploading never runs planning.
          </p>
        </div>

        <div className="w-56">
          <label
            htmlFor="location-scope"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Location for steps 3 and 4
          </label>
          <Select
            value={locationId ?? ''}
            onValueChange={(value) => {
              if (value !== null) {
                setLocationId(value)
              }
            }}
            disabled={locationList.length === 0}
          >
            <SelectTrigger id="location-scope" className="w-full">
              {/* Base UI renders the raw value unless told otherwise, which
                  leaks the location id where the kitchen name belongs. */}
              <SelectValue>
                {(value: unknown) =>
                  locationList.find((entry) => entry.location_id === value)
                    ?.location_name ??
                  (locationList.length === 0 ? 'None yet' : 'Choose a kitchen')
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {locationList.map((entry) => (
                <SelectItem key={entry.location_id} value={entry.location_id}>
                  {entry.location_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </header>

      <div className="mt-6 space-y-4 empty:mt-0">
        <RefreshErrorNotice error={refreshFailure} onRetry={refreshAll} />

        {locationsError !== null && (
          <ErrorState
            error={locationsError}
            onRetry={refreshAll}
            title="Locations could not be loaded"
          />
        )}

        {activationError !== null && (
          <div
            role="alert"
            className="rounded-xl border border-border bg-card px-5 py-4 text-sm text-danger"
          >
            {activationError}
          </div>
        )}
      </div>

      <div className="mt-8 grid gap-5 lg:grid-cols-2">
        {DATASETS.map((definition) => {
          const scoped = definition.scope === 'location'
          const scopeKey = scoped ? locationId : null

          return (
            <UploadCard
              key={definition.key}
              definition={definition}
              prerequisite={prerequisiteFor(definition.key, readiness)}
              current={currentImport(allImports, definition.key, scopeKey)}
              history={importHistory(allImports, definition.key, scopeKey)}
              timeZone={scoped ? locationTimeZone : browserTimeZone()}
              scopeLabel={
                scoped
                  ? (selectedLocation?.location_name ?? 'No location chosen')
                  : 'All locations'
              }
              knownImportIds={knownImportIds}
              upload={(files, options) => uploaders[definition.key](files, options)}
              onImported={refreshAll}
              isNextStep={definition.step === nextStep}
              statusOverride={
                definition.key === 'master_data' ? statusForStepOne() : undefined
              }
              completionSlot={
                // Activation is the completion of step 1, not a separate task
                // further down the page.
                definition.key === 'master_data' && latestDraft !== null ? (
                  <Button
                    size="lg"
                    className="w-full"
                    disabled={activating}
                    onClick={() => {
                      setPendingActivation(latestDraft)
                    }}
                  >
                    Activate master data and continue
                  </Button>
                ) : undefined
              }
              extraControls={
                definition.key === 'purchase_orders' ? (
                  <div>
                    <label
                      htmlFor="po-as-of"
                      className="mb-1 block text-xs font-medium text-muted-foreground"
                    >
                      Documents seen as of
                    </label>
                    <input
                      id="po-as-of"
                      type="datetime-local"
                      value={poAsOf}
                      onChange={(event) => {
                        setPoAsOf(event.target.value)
                      }}
                      className="h-9 w-full rounded-lg border border-input bg-card px-2.5 text-xs tabular focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      Decides which lines still count as open.
                    </p>
                  </div>
                ) : undefined
              }
            />
          )
        })}
      </div>

      <section className="mt-12 space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">
            Maintained data
          </h2>
          {/* The boundary, stated once. This used to be three dashed cards
              labelled "Planned", which put a roadmap in a working tool without
              telling the maintainer anything they could act on. */}
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Item policies, the menu calendar and the bill of materials come from
            the master workbook. Stock and supplier lines are corrected at the
            source, not edited here.
          </p>
        </div>

        <MasterVersionList
          versions={masterVersions}
          timeZone={browserTimeZone()}
          activating={activating}
          onActivate={setPendingActivation}
        />

      </section>

      {pendingActivation !== null && (
        <ActivateMasterDialog
          version={pendingActivation}
          replacing={activeVersion}
          pending={activating}
          onConfirm={() => void confirmActivation()}
          onCancel={() => {
            setPendingActivation(null)
          }}
        />
      )}
    </div>
  )
}
