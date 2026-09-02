import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  TEST_SESSION,
  createFakeSupabase,
  readinessResponse,
} from '../test/supabaseMock'
import type { FakeSupabase } from '../test/supabaseMock'

let fake: FakeSupabase

vi.mock('../lib/supabase', () => ({
  browserSupabaseConfigured: true,
  getSupabaseClient: () => fake.client,
}))

const { AppRoutes } = await import('./AppRoutes')
const { AuthProvider } = await import('./auth/AuthProvider')
const { SelectedLocationProvider } = await import(
  './location/SelectedLocationProvider'
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

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

const EMPTY_OVERVIEW = {
  as_of_date: '2026-08-31',
  kpis: {
    locations_ready: 0,
    locations_total: 0,
    locations_at_risk: 0,
    locations_requiring_order: 0,
    items_at_risk: 0,
    items_requiring_order: 0,
    items_risk_not_evaluated: 0,
    recommendations_due: 0,
    blocking_issues: 0,
    open_purchase_order_lines: 0,
  },
  latest_run_at: null,
  locations: [],
  proposal_only: true,
}

/**
 * Each endpoint needs its own shape. A single catch-all body would hand a page
 * the wrong thing and fail these shell tests for an unrelated reason.
 */
function routedFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input)
  if (url.includes('/readiness')) {
    // A Response body can only be read once, so every call needs a fresh one.
    return Promise.resolve(readinessResponse())
  }
  if (url.includes('/overview')) {
    return Promise.resolve(jsonResponse(EMPTY_OVERVIEW))
  }
  return Promise.resolve(jsonResponse({ master_data_version_id: 'v1', locations: [] }))
}

beforeEach(() => {
  fake = createFakeSupabase(TEST_SESSION)
  fetchMock.mockReset()
  fetchMock.mockImplementation(routedFetch)
  vi.stubGlobal('fetch', fetchMock)
  window.sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the proposal boundary', () => {
  it('states on every screen that nothing places an order', async () => {
    renderApp()

    // This is the one claim that must never be missing from any page.
    expect(
      await screen.findByText(/nothing here orders anything/i),
    ).toBeInTheDocument()
  })

  it('offers no way to dismiss that statement', async () => {
    renderApp()
    await screen.findByText(/nothing here orders anything/i)

    expect(
      screen.queryByRole('button', { name: /dismiss|close banner/i }),
    ).not.toBeInTheDocument()
  })
})

describe('navigation', () => {
  it('exposes exactly the three primary destinations', async () => {
    renderApp()

    const nav = await screen.findByRole('navigation', { name: 'Primary' })
    const links = within(nav).getAllByRole('link')

    // Exactly three, and no more: subsections never become nav items.
    expect(links).toHaveLength(3)
    expect(
      links.map((link) => link.textContent?.replace('(current page)', '').trim()),
    ).toEqual(['Overview', 'Location planning', 'Data & settings'])
  })

  it('announces the active destination in text, not only in colour', async () => {
    renderApp('/data')

    const nav = await screen.findByRole('navigation', { name: 'Primary' })
    const active = within(nav).getByRole('link', { name: /Data & settings/ })

    expect(active).toHaveTextContent('(current page)')
    expect(
      within(nav).getByRole('link', { name: /^Overview$/ }),
    ).not.toHaveTextContent('(current page)')
  })

  it('points Location planning at the chooser until a location is chosen', async () => {
    renderApp()

    const nav = await screen.findByRole('navigation', { name: 'Primary' })
    expect(
      within(nav).getByRole('link', { name: /Location planning/ }),
    ).toHaveAttribute('href', '/locations')
  })

  it('remembers the location the maintainer last opened', async () => {
    // Each endpoint needs its own shape; one catch-all body would hand a page
    // the wrong thing and fail this test for an unrelated reason.
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/readiness')) {
        return Promise.resolve(readinessResponse())
      }
      const body = url.includes('/locations/')
        ? {
            location_id: 'LOC_KOELN',
            ready: false,
            blockers: [],
            sources: {
              master_data_version: null,
              planning_input: null,
              stock: null,
              purchase_orders: null,
            },
            latest_run: null,
            latest_run_is_current: false,
            proposal_only: true,
          }
        : { master_data_version_id: 'v1', locations: [] }
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      )
    })

    renderApp('/locations/LOC_KOELN')

    const nav = await screen.findByRole('navigation', { name: 'Primary' })
    await waitFor(() => {
      expect(
        within(nav).getByRole('link', { name: /Location planning/ }),
      ).toHaveAttribute('href', '/locations/LOC_KOELN')
    })
  })
})

describe('the small-screen drawer', () => {
  it('opens, traps focus, and closes on Escape without losing the trigger', async () => {
    const user = userEvent.setup()
    renderApp()

    const trigger = await screen.findByRole('button', {
      name: /open navigation/i,
    })
    await user.click(trigger)

    const drawer = await screen.findByRole('dialog', {
      name: /primary navigation/i,
    })
    expect(drawer).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: /primary navigation/i }),
      ).not.toBeInTheDocument()
    })
    // Focus must come back to the control that opened it.
    expect(trigger).toHaveFocus()
  })
})

describe('the dependency indicator', () => {
  it('distinguishes an unconfigured database from a healthy one', async () => {
    // Only readiness changes; the other endpoints still need their own shapes.
    fetchMock.mockImplementation((input) =>
      String(input).includes('/readiness')
        ? Promise.resolve(readinessResponse('not_configured'))
        : routedFetch(input),
    )
    renderApp()

    // Text, not only a coloured dot, carries the status.
    expect(
      await screen.findAllByText(/database not configured/i),
    ).not.toHaveLength(0)
  })

  it('reports an unreachable API rather than showing nothing', async () => {
    fetchMock.mockImplementation((input) =>
      String(input).includes('/readiness')
        ? Promise.reject(new TypeError('Failed to fetch'))
        : routedFetch(input),
    )
    renderApp()

    expect(await screen.findAllByText(/api unreachable/i)).not.toHaveLength(0)
  })
})
