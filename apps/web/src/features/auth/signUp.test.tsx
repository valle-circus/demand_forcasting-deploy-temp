import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createFakeSupabase, readinessResponse } from '../../test/supabaseMock'
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

function renderApp(initialPath = '/sign-up') {
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

async function fillForm(
  user: ReturnType<typeof userEvent.setup>,
  email: string,
  password = 'correct horse battery',
  confirmation = password,
) {
  await user.type(await screen.findByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  await user.type(screen.getByLabelText('Confirm password'), confirmation)
}

beforeEach(() => {
  configured = true
  fake = createFakeSupabase(null)
  fetchMock.mockReset()
  fetchMock.mockImplementation(() => Promise.resolve(readinessResponse()))
  vi.stubGlobal('fetch', fetchMock)
  window.sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('self-service sign-up', () => {
  it('creates the account and waits for the emailed confirmation', async () => {
    const user = userEvent.setup()
    renderApp()

    await fillForm(user, 'colleague@circuskitchens.com')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('heading', { name: 'Check your email' }))
      .toBeInTheDocument()
    // Confirmation pending is not signed in: no domain page may appear yet.
    expect(
      screen.queryByRole('navigation', { name: 'Primary' }),
    ).not.toBeInTheDocument()

    const call = fake.signUp.mock.calls[0][0] as {
      email: string
      options?: { emailRedirectTo?: string }
    }
    expect(call.email).toBe('colleague@circuskitchens.com')
    expect(call.options?.emailRedirectTo).toContain('/auth/callback')
  })

  it('refuses an outside email domain without calling Supabase', async () => {
    const user = userEvent.setup()
    renderApp()

    await fillForm(user, 'someone@gmail.com')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(
      await screen.findByText(/use your @circuskitchens\.com address/i),
    ).toBeInTheDocument()
    // The real gate is the auth.users trigger, but there is no reason to spend
    // a request discovering what the form already knows.
    expect(fake.signUp).not.toHaveBeenCalled()
  })

  it('will not submit when the two passwords differ', async () => {
    const user = userEvent.setup()
    renderApp()

    await fillForm(
      user,
      'colleague@circuskitchens.com',
      'correct horse battery',
      'correct horse batteries',
    )
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(
      await screen.findByText(/both passwords must match/i),
    ).toBeInTheDocument()
    expect(fake.signUp).not.toHaveBeenCalled()
  })

  it('rejects a password under the minimum length', async () => {
    const user = userEvent.setup()
    renderApp()

    await fillForm(user, 'colleague@circuskitchens.com', 'short', 'short')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(
      await screen.findByText(/use at least 8 characters/i),
    ).toBeInTheDocument()
    expect(fake.signUp).not.toHaveBeenCalled()
  })

  it('translates the trigger rejection into the domain rule', async () => {
    const user = userEvent.setup()
    // What Supabase actually reports when the auth.users trigger raises.
    fake.failSignUpWith('Database error saving new user')
    renderApp()

    await fillForm(user, 'colleague@circuskitchens.com')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /limited to @circuskitchens\.com email addresses/i,
    )
  })

  it('goes straight into the app when the project needs no confirmation', async () => {
    const user = userEvent.setup()
    fake.signUpReturnsSession()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/readiness')) {
        return Promise.resolve(readinessResponse())
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            error: { code: 'not_found', message: 'No master data.' },
          }),
          { status: 404, headers: { 'content-type': 'application/json' } },
        ),
      )
    })
    renderApp()

    await fillForm(user, 'colleague@circuskitchens.com')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(
      await screen.findByRole('navigation', { name: 'Primary' }),
    ).toBeInTheDocument()
  })

  it('says so when the build has no Supabase values', async () => {
    configured = false
    renderApp()

    expect(
      await screen.findByText(/authentication is not configured/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Create account' }),
    ).not.toBeInTheDocument()
  })
})

describe('the confirmation link landing page', () => {
  it('explains an expired link instead of failing silently', async () => {
    renderApp('/auth/callback#error=access_denied&error_description=Email+link+is+invalid+or+has+expired')

    expect(
      await screen.findByRole('heading', { name: 'This link did not work' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
      'href',
      '/sign-in',
    )
  })
})
