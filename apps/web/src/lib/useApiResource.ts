/**
 * Small session-scoped server-state hook. Successful snapshots survive route
 * unmounts briefly, stale data stays visible during revalidation, and requests
 * with the same explicit key are deduplicated.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { isAbort } from './errors'
import {
  RESOURCE_FRESH_TIME_MS,
  loadResource,
  readResource,
  subscribeResource,
} from './resourceCache'

export type ResourceState<T> =
  | { status: 'idle'; data: null; error: null }
  | { status: 'loading'; data: null; error: null }
  | {
      status: 'success'
      data: T
      error: null
      isRefreshing: boolean
      refreshError: Error | null
    }
  | { status: 'error'; data: null; error: Error }

export interface Resource<T> {
  state: ResourceState<T>
  /** Re-run the fetch, e.g. after an upload or a completed planning run. */
  refetch: () => void
}

export interface ResourceOptions {
  /**
   * When false the fetch is skipped and the state stays `idle`. Used for
   * requests that need a selection that does not exist yet.
   */
  enabled?: boolean
  /** How long a successful in-memory snapshot can be reused without a fetch. */
  staleTimeMs?: number
}

const IDLE = { status: 'idle', data: null, error: null } as const
const LOADING = { status: 'loading', data: null, error: null } as const

/**
 * @param key Stable identity shared by every consumer of the same API result.
 * @param fetcher Receives an `AbortSignal`; must reject on failure. It must
 *   never resolve with a fallback value, or the UI would present invented data.
 */
export function useApiResource<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: ResourceOptions = {},
): Resource<T> {
  const enabled = options.enabled ?? true
  const staleTimeMs = options.staleTimeMs ?? RESOURCE_FRESH_TIME_MS

  function stateFromCache(): ResourceState<T> {
    if (!enabled) {
      return IDLE
    }
    const snapshot = readResource<T>(key)
    if (snapshot.hasData && snapshot.data !== null) {
      return {
        status: 'success',
        data: snapshot.data,
        error: null,
        isRefreshing: snapshot.isRefreshing,
        refreshError: snapshot.error,
      }
    }
    if (snapshot.error !== null) {
      return { status: 'error', data: null, error: snapshot.error }
    }
    return LOADING
  }

  // The cache is the only source of truth and is read on every render, so a
  // location/key change - which can occur without unmounting the page - never
  // renders the previous key's data. The subscription below therefore only has
  // to ask for a re-render when the cache entry changes.
  const state = stateFromCache()
  const [, requestRender] = useState(0)

  // Keep the latest fetcher without making it a dependency: callers pass an
  // inline arrow, which would otherwise re-run the effect on every render. The
  // write happens in an effect because a ref must not be mutated during render,
  // and this effect is declared first so it lands before the load below.
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    if (!enabled) {
      return
    }

    const startLoad = (force = false): void => {
      void loadResource({
        key,
        fetcher: (signal) => fetcherRef.current(signal),
        staleTimeMs,
        force,
      }).catch((error: unknown) => {
        // Cache notifications update visible state. This catch only consumes
        // the promise so a route unmount cannot leave a rejection unhandled.
        if (!isAbort(error)) {
          return
        }
      })
    }

    const onCacheChange = (): void => {
      requestRender((revision) => revision + 1)
      const snapshot = readResource<T>(key)
      if (snapshot.invalidated && !snapshot.isRefreshing) {
        startLoad()
      }
    }

    // Subscribe before loading: starting a request notifies subscribers, which
    // is how the first `isRefreshing` render is triggered. An entry that is
    // already invalidated is refetched by this same call.
    const unsubscribe = subscribeResource(key, onCacheChange)
    startLoad()

    return () => {
      unsubscribe()
    }
  }, [enabled, key, staleTimeMs])

  const refetch = useCallback(() => {
    if (!enabled) {
      return
    }
    void loadResource({
      key,
      fetcher: (signal) => fetcherRef.current(signal),
      staleTimeMs,
      force: true,
    }).catch(() => undefined)
  }, [enabled, key, staleTimeMs])

  return { state, refetch }
}

export function refreshError<T>(state: ResourceState<T>): Error | null {
  return state.status === 'success' ? state.refreshError : null
}
