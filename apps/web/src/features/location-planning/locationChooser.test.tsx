import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { configureAuthTokenProvider } from '../../lib/apiClient'
import { LocationChooserPage } from './LocationChooserPage'

const fetchMock = vi.fn<typeof fetch>()

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function renderChooser() {
  return render(
    <MemoryRouter>
      <LocationChooserPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  configureAuthTokenProvider(async () => 'test-access-token')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the first-run state', () => {
  it('treats a 404 as "no master data yet", not as a failure', async () => {
    // GET /locations resolves locations through the active master-data version,
    // so on a fresh environment it 404s rather than returning an empty list.
    // Rendering that as an error would tell the maintainer something is broken
    // when they simply have not imported the master workbook yet.
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        jsonResponse(
          {
            error: {
              code: 'not_found',
              message: "Active master-data version 'development' was not found.",
            },
          },
          404,
        ),
      ),
    )

    renderChooser()

    expect(
      await screen.findByRole('heading', { name: /no master data yet/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /go to data & settings/i }),
    ).toHaveAttribute('href', '/data')
  })

  it('sends the maintainer to the page that fixes it', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(jsonResponse({ error: { code: 'not_found' } }, 404)),
    )

    renderChooser()

    expect(
      await screen.findByText(/import the master workbook and activate it/i),
    ).toBeInTheDocument()
  })
})

describe('other outcomes', () => {
  it('presents an unavailable database as a failure, not as no data', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        jsonResponse(
          {
            error: {
              code: 'persistence_unavailable',
              message: 'Planning persistence is currently unavailable.',
            },
          },
          503,
        ),
      ),
    )

    renderChooser()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/service is unavailable/i)
    expect(alert).toHaveTextContent(/not an empty result/i)
  })

  it('separates "no active locations" from "no master data"', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        jsonResponse({ master_data_version_id: 'v1', locations: [] }),
      ),
    )

    renderChooser()

    expect(
      await screen.findByRole('heading', { name: /no active locations/i }),
    ).toBeInTheDocument()
  })

  it('lists each location with its identifier and timezone', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        jsonResponse({
          master_data_version_id: 'v1',
          locations: [
            {
              location_id: 'LOC_KOELN',
              location_name: 'Köln',
              timezone: 'Europe/Berlin',
              active: true,
            },
          ],
        }),
      ),
    )

    renderChooser()

    const link = await screen.findByRole('link', { name: /Köln/ })
    expect(link).toHaveAttribute('href', '/locations/LOC_KOELN')
    expect(link).toHaveTextContent('Europe/Berlin')
  })
})
