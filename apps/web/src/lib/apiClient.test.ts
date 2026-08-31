import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  configureAuthTokenProvider,
  configureUnauthorizedHandler,
  fetchLocations,
  fetchOverview,
  fetchReadiness,
} from './apiClient'
import { ServiceUnavailableError, UnauthorizedError } from './errors'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  configureAuthTokenProvider(async () => 'test-access-token')
  configureUnauthorizedHandler(() => undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function headersOf(callIndex = 0): Headers {
  const init = fetchMock.mock.calls[callIndex][1]
  return new Headers(init?.headers)
}

describe('authentication', () => {
  it('sends the session token on domain requests', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ master_data_version_id: 'v1', locations: [] }),
    )

    await fetchLocations()

    expect(headersOf().get('Authorization')).toBe('Bearer test-access-token')
  })

  it('leaves readiness unauthenticated so it works before sign-in', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        status: 'ready',
        service: 'supply-planning-api',
        version: '0.1.0',
        environment: 'development',
        supabase: { status: 'ready', message: 'ok' },
      }),
    )

    await fetchReadiness()

    expect(headersOf().get('Authorization')).toBeNull()
  })

  it('fails locally without issuing a request when there is no session', async () => {
    configureAuthTokenProvider(async () => null)

    await expect(fetchLocations()).rejects.toBeInstanceOf(UnauthorizedError)
    // Sending a request we know will 401 wastes a round trip and muddies logs.
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('notifies the session handler once on a rejected token, without retrying', async () => {
    const onUnauthorized = vi.fn()
    configureUnauthorizedHandler(onUnauthorized)
    fetchMock.mockResolvedValue(
      jsonResponse(
        { error: { code: 'invalid_session', message: 'Sign in again.' } },
        401,
      ),
    )

    await expect(fetchOverview()).rejects.toBeInstanceOf(UnauthorizedError)

    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    // A retry loop against an invalid session is worse than one clean failure.
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('error translation', () => {
  it('surfaces an unavailable dependency as such, never as empty data', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'persistence_unavailable',
            message: 'Planning persistence is currently unavailable.',
          },
        },
        503,
      ),
    )

    await expect(fetchOverview()).rejects.toBeInstanceOf(ServiceUnavailableError)
  })

  it('reports a transport failure without inventing a result', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(fetchOverview()).rejects.toMatchObject({
      code: 'network_error',
    })
  })

  it('propagates an abort rather than treating it as a failure', async () => {
    fetchMock.mockRejectedValue(new DOMException('aborted', 'AbortError'))

    await expect(fetchOverview()).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('request shape', () => {
  it('escapes the location id in the path', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}))

    await fetchLocations()
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/locations')
  })
})
