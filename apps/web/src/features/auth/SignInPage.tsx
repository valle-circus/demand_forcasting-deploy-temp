import { useId, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../../app/auth/authContext'
import { ApiStatusLine } from '../../components/ApiStatusLine'
import { BrandMark } from '../../components/BrandMark'
import { errorMessage } from '../../lib/errors'

interface RedirectState {
  from?: string
}

/**
 * The sign-in gate.
 *
 * There is deliberately no self-sign-up, password reset, or role management.
 * Accounts are created by an administrator in Supabase, and FastAPI currently
 * treats every valid project user as a maintainer — so a public signup form
 * would hand maintainer access to anyone who found the URL.
 */
export function SignInPage() {
  const { status, notice, signIn } = useAuth()
  const routerLocation = useLocation()
  const emailId = useId()
  const passwordId = useId()
  const errorId = useId()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (status === 'signed-in') {
    const state = routerLocation.state as RedirectState | null
    return <Navigate to={state?.from ?? '/overview'} replace />
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) {
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await signIn(email, password)
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setSubmitting(false)
    }
  }

  const unconfigured = status === 'unconfigured'

  return (
    <main className="flex min-h-screen items-center justify-center bg-stone-100 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="rounded-t-xl bg-stone-950 px-7 py-6 text-stone-50">
          <BrandMark />
          <h1 className="mt-5 text-xl font-semibold tracking-tight">
            Supply planning workspace
          </h1>
          <p className="mt-1 text-sm text-stone-400">
            Internal proposal tool. It does not place supplier orders.
          </p>
        </div>

        <div className="rounded-b-xl border border-t-0 border-stone-200 bg-white px-7 py-6">
          {unconfigured ? (
            <div
              role="status"
              className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
            >
              <p className="font-semibold">Authentication is not configured</p>
              <p className="mt-2 leading-6">
                This build has no browser Supabase values, so there is no
                sign-in to attempt. Set{' '}
                <code className="rounded bg-amber-100 px-1">
                  VITE_SUPABASE_URL
                </code>{' '}
                and{' '}
                <code className="rounded bg-amber-100 px-1">
                  VITE_SUPABASE_PUBLISHABLE_KEY
                </code>{' '}
                in the environment, then reload.
              </p>
            </div>
          ) : (
            <>
              {notice !== null && (
                <div
                  role="status"
                  className="mb-5 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
                >
                  {notice}
                </div>
              )}

              <form onSubmit={(event) => void handleSubmit(event)} noValidate>
                <div>
                  <label
                    htmlFor={emailId}
                    className="block text-sm font-medium text-stone-800"
                  >
                    Email
                  </label>
                  <input
                    id={emailId}
                    type="email"
                    name="email"
                    autoComplete="username"
                    required
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value)
                    }}
                    className="mt-1.5 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-950 focus:border-lime-600 focus:ring-2 focus:ring-lime-600/30 focus:outline-none"
                  />
                </div>

                <div className="mt-4">
                  <label
                    htmlFor={passwordId}
                    className="block text-sm font-medium text-stone-800"
                  >
                    Password
                  </label>
                  <input
                    id={passwordId}
                    type="password"
                    name="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(event) => {
                      setPassword(event.target.value)
                    }}
                    aria-describedby={error === null ? undefined : errorId}
                    aria-invalid={error === null ? undefined : true}
                    className="mt-1.5 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-950 focus:border-lime-600 focus:ring-2 focus:ring-lime-600/30 focus:outline-none"
                  />
                </div>

                {error !== null && (
                  <p
                    id={errorId}
                    role="alert"
                    className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900"
                  >
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="mt-6 w-full rounded-lg bg-lime-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-lime-700 focus:ring-2 focus:ring-lime-600 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:bg-stone-300"
                >
                  {submitting ? 'Signing in…' : 'Sign in'}
                </button>
              </form>

              <p className="mt-5 text-xs leading-5 text-stone-500">
                Accounts are created by an administrator in Supabase. There is no
                self-service sign-up.
              </p>
            </>
          )}

          <div className="mt-6 border-t border-stone-200 pt-4">
            <ApiStatusLine />
          </div>
        </div>
      </div>
    </main>
  )
}
