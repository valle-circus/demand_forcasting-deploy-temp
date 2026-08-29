/**
 * A deliberately small data-loading hook.
 *
 * There is no cache. Every screen in this product exists to say how fresh a
 * value is, so serving a previously fetched response while revalidating would
 * make the freshness stamp beside it a lie. A page loads on mount, reloads
 * when its inputs change, and reloads when something it did invalidates it.
 *
 * When flows appear that genuinely need shared caching, deduplication, or
 * polling — asynchronous planning runs, most likely — revisit this in favour
 * of a query library. Until then this is the whole of it.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { isAbort } from './errors'

export type ResourceState<T> =
  | { status: 'idle'; data: null; error: null }
  | { status: 'loading'; data: null; error: null }
  | { status: 'success'; data: T; error: null }
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
}

const IDLE = { status: 'idle', data: null, error: null } as const
const LOADING = { status: 'loading', data: null, error: null } as const

/**
 * @param fetcher Receives an `AbortSignal`; must reject on failure. It must
 *   never resolve with a fallback value, or the UI would present invented data.
 * @param deps Re-runs the fetch when these change, like `useEffect`.
 */
export function useApiResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
  options: ResourceOptions = {},
): Resource<T> {
  const enabled = options.enabled ?? true
  const [state, setState] = useState<ResourceState<T>>(enabled ? LOADING : IDLE)
  const [reloadToken, setReloadToken] = useState(0)

  // Keep the latest fetcher without making it a dependency: callers pass an
  // inline arrow, which would otherwise re-run the effect on every render.
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    if (!enabled) {
      setState(IDLE)
      return
    }

    const controller = new AbortController()
    let active = true
    setState(LOADING)

    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (active) {
          setState({ status: 'success', data, error: null })
        }
      })
      .catch((error: unknown) => {
        if (!active || isAbort(error)) {
          return
        }
        setState({
          status: 'error',
          data: null,
          error: error instanceof Error ? error : new Error(String(error)),
        })
      })

    return () => {
      active = false
      controller.abort()
    }
    // `deps` is the caller's dependency list, spread the same way `useEffect`
    // would consume it; `fetcher` is intentionally read through a ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, reloadToken, ...deps])

  const refetch = useCallback(() => {
    setReloadToken((token) => token + 1)
  }, [])

  return { state, refetch }
}
