import { useId, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '@/app/auth/authContext'
import { ApiStatusLine } from '@/components/ApiStatusLine'
import { BrandMark } from '@/components/BrandMark'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'

interface RedirectState {
  from?: string
}

const FIELD_CLASS =
  'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none'

/**
 * The sign-in gate.
 *
 * No self-sign-up, no password reset, no role management: accounts are created
 * by an administrator in Supabase, and the API currently treats every valid
 * project user as a maintainer.
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

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <BrandMark />

        {status === 'unconfigured' ? (
          <div role="status" className="mt-6 rounded-lg border border-border p-4">
            <h1 className="text-base font-medium">
              Authentication is not configured
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              This build has no Supabase values, so there is no sign-in to
              attempt.
            </p>
          </div>
        ) : (
          <>
            <h1 className="mt-6 text-3xl font-semibold tracking-tight">
              Sign in
            </h1>

            {notice !== null && (
              <p role="status" className="mt-3 text-sm text-warning">
                {notice}
              </p>
            )}

            <form
              className="mt-6 space-y-4"
              onSubmit={(event) => void handleSubmit(event)}
              noValidate
            >
              <div>
                <label htmlFor={emailId} className="mb-1 block text-sm font-medium">
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
                  className={FIELD_CLASS}
                />
              </div>

              <div>
                <label
                  htmlFor={passwordId}
                  className="mb-1 block text-sm font-medium"
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
                  className={FIELD_CLASS}
                />
              </div>

              {error !== null && (
                <p id={errorId} role="alert" className="text-sm text-danger">
                  {error}
                </p>
              )}

              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={submitting}
              >
                {submitting ? 'Signing in' : 'Sign in'}
              </Button>
            </form>

            <p className="mt-4 text-xs text-muted-foreground">
              Accounts are created by an administrator. There is no self-service
              sign-up.
            </p>
          </>
        )}

        <div className="mt-6 border-t border-border pt-3">
          <ApiStatusLine />
        </div>
      </div>
    </main>
  )
}
