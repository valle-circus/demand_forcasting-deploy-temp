import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  clearResourceCache,
  invalidateResource,
  primeResource,
  readResource,
} from './resourceCache'
import { useApiResource } from './useApiResource'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('useApiResource cache', () => {
  it('renders a recent result immediately after a route-style remount', async () => {
    const fetcher = vi.fn(async () => ({ label: 'known result' }))
    const first = renderHook(() => useApiResource('test:remount', fetcher))

    await waitFor(() => {
      expect(first.result.current.state.status).toBe('success')
    })
    first.unmount()

    const second = renderHook(() => useApiResource('test:remount', fetcher))

    expect(second.result.current.state).toMatchObject({
      status: 'success',
      data: { label: 'known result' },
      isRefreshing: false,
    })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it("never flashes the previous resource when a mounted page's key changes", () => {
    primeResource('test:key:a', { label: 'location A' })
    primeResource('test:key:b', { label: 'location B' })
    const fetcher = vi.fn(async () => ({ label: 'unused' }))
    const resource = renderHook(
      ({ key }) => useApiResource(key, fetcher),
      { initialProps: { key: 'test:key:a' } },
    )

    expect(resource.result.current.state).toMatchObject({
      status: 'success',
      data: { label: 'location A' },
    })

    resource.rerender({ key: 'test:key:b' })

    expect(resource.result.current.state).toMatchObject({
      status: 'success',
      data: { label: 'location B' },
    })
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('keeps stale data visible while it revalidates', async () => {
    let now = 1_000
    vi.spyOn(Date, 'now').mockImplementation(() => now)
    const next = deferred<{ label: string }>()
    const fetcher = vi
      .fn<(signal: AbortSignal) => Promise<{ label: string }>>()
      .mockResolvedValueOnce({ label: 'previous result' })
      .mockImplementationOnce(() => next.promise)

    const first = renderHook(() => useApiResource('test:stale', fetcher))
    await waitFor(() => {
      expect(first.result.current.state.status).toBe('success')
    })
    first.unmount()
    now += 30_001

    const second = renderHook(() => useApiResource('test:stale', fetcher))
    expect(second.result.current.state).toMatchObject({
      status: 'success',
      data: { label: 'previous result' },
    })
    await waitFor(() => {
      expect(second.result.current.state).toMatchObject({
        status: 'success',
        data: { label: 'previous result' },
        isRefreshing: true,
      })
    })

    await act(async () => {
      next.resolve({ label: 'new result' })
      await next.promise
    })
    await waitFor(() => {
      expect(second.result.current.state).toMatchObject({
        status: 'success',
        data: { label: 'new result' },
        isRefreshing: false,
      })
    })
  })

  it('deduplicates concurrent consumers with the same key', async () => {
    const pending = deferred<{ value: number }>()
    const fetcher = vi.fn(() => pending.promise)

    const first = renderHook(() => useApiResource('test:dedupe', fetcher))
    const second = renderHook(() => useApiResource('test:dedupe', fetcher))

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(1)
    })
    await act(async () => {
      pending.resolve({ value: 1 })
      await pending.promise
    })
    await waitFor(() => {
      expect(first.result.current.state.status).toBe('success')
      expect(second.result.current.state.status).toBe('success')
    })
  })

  it('revalidates an invalidated key without hiding its known data', async () => {
    const next = deferred<{ value: number }>()
    const fetcher = vi
      .fn<(signal: AbortSignal) => Promise<{ value: number }>>()
      .mockResolvedValueOnce({ value: 1 })
      .mockImplementationOnce(() => next.promise)
    const resource = renderHook(() =>
      useApiResource('test:invalidate', fetcher),
    )
    await waitFor(() => {
      expect(resource.result.current.state.status).toBe('success')
    })

    act(() => {
      invalidateResource('test:invalidate')
    })

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(2)
      expect(resource.result.current.state).toMatchObject({
        status: 'success',
        data: { value: 1 },
        isRefreshing: true,
      })
    })
    await act(async () => {
      next.resolve({ value: 2 })
      await next.promise
    })
    await waitFor(() => {
      expect(resource.result.current.state).toMatchObject({
        status: 'success',
        data: { value: 2 },
      })
    })
  })

  it('forces a network request when Refresh is used inside the fresh window', async () => {
    const fetcher = vi
      .fn<(signal: AbortSignal) => Promise<{ value: number }>>()
      .mockResolvedValueOnce({ value: 1 })
      .mockResolvedValueOnce({ value: 2 })
    const resource = renderHook(() => useApiResource('test:force', fetcher))
    await waitFor(() => {
      expect(resource.result.current.state).toMatchObject({
        status: 'success',
        data: { value: 1 },
      })
    })

    act(() => {
      resource.result.current.refetch()
    })

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(2)
      expect(resource.result.current.state).toMatchObject({
        status: 'success',
        data: { value: 2 },
      })
    })
  })

  it('keeps refresh failures visible beside the previous result', async () => {
    let now = 1_000
    vi.spyOn(Date, 'now').mockImplementation(() => now)
    const fetcher = vi
      .fn<(signal: AbortSignal) => Promise<{ value: number }>>()
      .mockResolvedValueOnce({ value: 1 })
      .mockRejectedValueOnce(new Error('refresh unavailable'))
    const first = renderHook(() => useApiResource('test:error', fetcher))
    await waitFor(() => {
      expect(first.result.current.state.status).toBe('success')
    })
    first.unmount()
    now += 30_001

    const second = renderHook(() => useApiResource('test:error', fetcher))
    await waitFor(() => {
      expect(second.result.current.state).toMatchObject({
        status: 'success',
        data: { value: 1 },
        isRefreshing: false,
        refreshError: new Error('refresh unavailable'),
      })
    })
  })

  it('primes returned mutation data and clears all session data', () => {
    primeResource('test:prime', { value: 3 })
    expect(readResource<{ value: number }>('test:prime')).toMatchObject({
      hasData: true,
      data: { value: 3 },
    })

    clearResourceCache()

    expect(readResource('test:prime')).toMatchObject({
      hasData: false,
      data: null,
    })
  })
})
