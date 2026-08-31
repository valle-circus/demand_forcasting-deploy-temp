import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { useSelectedLocation } from '@/app/location/locationContext'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { StatusBadge } from '@/components/StatusBadge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  createPlanningRun,
  fetchInventory,
  fetchLocations,
  fetchPlanningStatus,
  fetchPurchaseOrders,
  getPlanningRun,
} from '@/lib/apiClient'
import { isNotFound } from '@/lib/errors'
import { nowWithOffset } from '@/lib/formatting'
import type { PlanningRunResponse } from '@/lib/types'
import { useApiResource } from '@/lib/useApiResource'
import { useMutation } from '@/lib/useMutation'
import { FreshnessStrip } from './FreshnessStrip'
import { LocationChooserPage } from './LocationChooserPage'
import { OpenPoTab } from './OpenPoTab'
import { RecommendationTab } from './RecommendationTab'
import { RiskStockTab } from './RiskStockTab'
import { BlockerList, RunAction } from './RunAction'
import { runCurrency, runStatusLabel } from './planning'

const TABS = ['risk', 'orders', 'proposals'] as const
type TabKey = (typeof TABS)[number]

export function LocationPlanningPage() {
  const { locationId } = useParams<{ locationId: string }>()
  const { setLocationId } = useSelectedLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [freshRun, setFreshRun] = useState<PlanningRunResponse | null>(null)

  const rawTab = searchParams.get('tab')
  const tab: TabKey = TABS.includes(rawTab as TabKey) ? (rawTab as TabKey) : 'risk'

  useEffect(() => {
    if (locationId) {
      setLocationId(locationId)
    }
  }, [locationId, setLocationId])

  const locations = useApiResource((signal) => fetchLocations(signal), [])
  const status = useApiResource(
    (signal) => fetchPlanningStatus(locationId ?? '', signal),
    [locationId],
    { enabled: Boolean(locationId) },
  )

  const latestRunId =
    status.state.status === 'success'
      ? (status.state.data.latest_run?.run_id ?? null)
      : null

  const persistedRun = useApiResource(
    (signal) => getPlanningRun(latestRunId ?? '', signal),
    [latestRunId],
    { enabled: latestRunId !== null },
  )

  const inventory = useApiResource(
    (signal) => fetchInventory(locationId ?? '', signal),
    [locationId],
    { enabled: Boolean(locationId) },
  )

  // Only fetched when its tab is open: the maintainer may never look at it.
  const purchaseOrders = useApiResource(
    (signal) => fetchPurchaseOrders(locationId ?? '', signal),
    [locationId],
    { enabled: Boolean(locationId) && tab === 'orders' },
  )

  const run = useMutation(async (id: string) => {
    const result = await createPlanningRun({
      location_id: id,
      // The API rejects a naive timestamp.
      planning_as_of_at: nowWithOffset(),
      run_mode: 'scenario',
    })
    setFreshRun(result)
    status.refetch()
    return result
  })

  const setTab = useCallback(
    (next: string) => {
      setSearchParams({ tab: next }, { replace: true })
    },
    [setSearchParams],
  )

  if (!locationId) {
    return <LocationChooserPage />
  }

  if (status.state.status === 'error') {
    return <ErrorState error={status.state.error} onRetry={status.refetch} />
  }
  if (status.state.status !== 'success') {
    return <LoadingState label="Loading this location" />
  }

  const planningStatus = status.state.data
  const locationList =
    locations.state.status === 'success' ? locations.state.data.locations : []
  const location =
    locationList.find((entry) => entry.location_id === locationId) ?? null

  // The freshly computed run wins over the persisted read until a refetch.
  const result =
    freshRun ??
    (persistedRun.state.status === 'success' ? persistedRun.state.data : null)

  const currency = runCurrency(planningStatus)
  const inventoryData =
    inventory.state.status === 'success' ? inventory.state.data : null

  return (
    <div className="mx-auto max-w-[1280px] space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {location?.location_name ?? locationId}
          </h1>
          <div className="mt-2 flex items-center gap-3">
            {locationList.length > 1 && (
              <Select
                value={locationId}
                onValueChange={(value) => {
                  if (value !== null) {
                    void navigate(`/locations/${encodeURIComponent(value)}`)
                  }
                }}
              >
                <SelectTrigger className="h-8 w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {locationList.map((entry) => (
                    <SelectItem key={entry.location_id} value={entry.location_id}>
                      {entry.location_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {currency === 'stale' && (
              <StatusBadge tone="warning" label="Result out of date" />
            )}
            {result !== null && result.run.status !== 'completed' && (
              <StatusBadge tone="blocked" label={runStatusLabel(result.run)} />
            )}
          </div>
        </div>

        <RunAction
          status={planningStatus}
          running={run.isPending}
          error={run.state.status === 'error' ? run.state.error : null}
          onRun={() => void run.mutate(locationId)}
        />
      </header>

      <FreshnessStrip status={planningStatus} />

      <BlockerList status={planningStatus} />

      {currency === 'stale' && (
        <p className="rounded-lg border border-border bg-surface px-4 py-2.5 text-xs text-warning">
          Newer data has been imported since this was calculated. Compute again
          before acting on it.
        </p>
      )}

      {result === null && latestRunId !== null ? (
        // A run exists and is still being fetched. Saying "no result yet" here
        // would invite a second synchronous calculation for no reason.
        persistedRun.state.status === 'error' ? (
          <ErrorState
            error={persistedRun.state.error}
            onRetry={persistedRun.refetch}
            title="The last result could not be loaded"
          />
        ) : (
          <LoadingState label="Loading the last result" />
        )
      ) : result === null ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {planningStatus.ready
            ? 'No result yet. Compute a recommendation to see risk and proposals.'
            : 'No result yet.'}
        </p>
      ) : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="risk">
              Risk &amp; stock
              {result.summary.items_at_risk > 0 &&
                ` (${String(result.summary.items_at_risk)})`}
            </TabsTrigger>
            <TabsTrigger value="orders">On order</TabsTrigger>
            <TabsTrigger value="proposals">
              Proposals ({result.summary.recommendation_count})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="risk" className="mt-4">
            <RiskStockTab
              netting={result.netting_results}
              projections={result.projection_days}
              lines={result.planning_lines}
              inventory={inventoryData}
            />
          </TabsContent>

          <TabsContent value="orders" className="mt-4">
            {purchaseOrders.state.status === 'error' ? (
              isNotFound(purchaseOrders.state.error) ? (
                <p className="text-sm text-muted-foreground">
                  No supplier documents imported for this location yet.
                </p>
              ) : (
                <ErrorState
                  error={purchaseOrders.state.error}
                  onRetry={purchaseOrders.refetch}
                />
              )
            ) : purchaseOrders.state.status === 'success' ? (
              <OpenPoTab
                data={purchaseOrders.state.data}
                inventory={inventoryData}
              />
            ) : (
              <LoadingState label="Loading supplier documents" />
            )}
          </TabsContent>

          <TabsContent value="proposals" className="mt-4">
            <RecommendationTab run={result} inventory={inventoryData} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
