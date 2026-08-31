import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  TEST_SESSION,
  createFakeSupabase,
  readinessResponse,
} from '../../test/supabaseMock'
import type { FakeSupabase } from '../../test/supabaseMock'

let fake: FakeSupabase
let configured = true

vi.mock('../../lib/supabase', () => ({
  get browserSupabaseConfigured() {
    return configured
  },
  getSupabaseClient: () => (configured ? fake.client : null),
}))

const { AppRoutes } = await import('../../app/AppRoutes')
const { AuthProvider } = await import('../../app/auth/AuthProvider')
const { SelectedLocationProvider } = await import(
  '../../app/location/SelectedLocationProvider'
)

const fetchMock = vi.fn<typeof fetch>()

function renderApp(initialPath = '/overview') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <SelectedLocationProvider>
          <AppRoutes />
        </SelectedLocationProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

/**
 * Answers each endpoint the pages behind the gate actually call. A single
 * catch-all body would hand a page the wrong shape and make an unrelated test
 * fail for the wrong reason.
 */
function routedFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input)
  if (url.includes('/readiness')) {
    return Promise.resolve(readinessResponse())
  }
  if (url.includes('/imports') || url.includes('/master-data/versions')) {
    return Promise.resolve(jsonResponse([]))
  }
  // No active master version yet, which is the first-run state.
  return Promise.resolve(
    jsonResponse({ error: { code: 'not_found', message: 'No master data.' } }, 404),
  )
}

beforeEach(() => {
  configured = true
  fake = createFakeSupabase(null)
  fetchMock.mockReset()
  fetchMock.mockImplementation(routedFetch)
  vi.stubGlobal('fetch', fetchMock)
  window.sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the sign-in gate', () => {
  it('blocks a domain route when there is no session', async () => {
    renderApp('/overview')

    expect(
      await screen.findByRole('button', { name: 'Sign in' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('navigation', { name: 'Primary' }),
    ).not.toBeInTheDocument()
  })

  it('signs in and lands on the page that was originally requested', async () => {
    const user = userEvent.setup()
    renderApp('/data')

    await user.type(
      await screen.findByLabelText('Email'),
      'maintainer@example.com',
    )
    await user.type(screen.getByLabelText('Password'), 'correct horse')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    // Not /overview: the maintainer asked for /data before being challenged.
    expect(await screen.findByRole('heading', { name: 'Data & settings' }))
      .toBeInTheDocument()
  })

  it('explains a rejected credential in plain language', async () => {
    const user = userEvent.setup()
    fake.failSignInWith('Invalid login credentials')
    renderApp()

    await user.type(await screen.findByLabelText('Email'), 'wrong@example.com')
    await user.type(screen.getByLabelText('Password'), 'nope')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    // Supabase's own wording is terse; the maintainer sees something usable.
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /email and password combination was not recognised/i,
    )
  })

  it('offers no self-service sign-up', async () => {
    renderApp()
    await screen.findByRole('button', { name: 'Sign in' })

    // Every valid Supabase user is a maintainer to FastAPI, so a public signup
    // form would hand maintainer access to anyone who found the URL.
    expect(
      screen.queryByRole('button', { name: /sign up|create account|register/i }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/no self-service sign-up/i)).toBeInTheDocument()
  })
})

describe('when Supabase is not configured for the browser', () => {
  it('says so instead of showing a login form that cannot work', async () => {
    configured = false
    renderApp()

    expect(
      await screen.findByText(/authentication is not configured/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Sign in' }),
    ).not.toBeInTheDocument()
  })
})

describe('when the API rejects the session mid-visit', () => {
  it('returns to the gate and explains why, without retrying', async () => {
    fake = createFakeSupabase(TEST_SESSION)
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/readiness')) {
        return Promise.resolve(readinessResponse())
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            error: { code: 'invalid_session', message: 'Sign in again.' },
          }),
          { status: 401, headers: { 'content-type': 'application/json' } },
        ),
      )
    })

    renderApp('/locations')

    expect(
      await screen.findByText(/your session has expired/i),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Sign in' }),
    ).toBeInTheDocument()

    // One rejected call, not a retry loop.
    const domainCalls = fetchMock.mock.calls.filter(
      (call) => !String(call[0]).includes('/readiness'),
    )
    expect(domainCalls).toHaveLength(1)
  })
})
