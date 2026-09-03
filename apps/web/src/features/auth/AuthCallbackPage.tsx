import { Link, Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '@/app/auth/authContext'
import { ApiStatusLine } from '@/components/ApiStatusLine'
import { BrandMark } from '@/components/BrandMark'

/**
 * Where the emailed confirmation link lands.
 *
 * There is nothing to submit here. `createClient` runs with supabase-js's
 * default implicit flow and `detectSessionInUrl`, so the tokens in the URL
 * fragment have already been exchanged for a session by the time
 * `AuthProvider` finishes its first `getSession()` call. This page only has to
 * report which of the three outcomes happened.
 */
export function AuthCallbackPage() {
  const { status } = useAuth()
  const location = useLocation()

  // GoTrue reports a dead link in the fragment, not the query string.
  const fragment = new URLSearchParams(location.hash.replace(/^#/, ''))
  const failure =
    fragment.get('error_description') ?? fragment.get('error') ?? null

  if (failure === null && status === 'signed-in') {
    return <Navigate to="/overview" replace />
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <BrandMark />

        {failure === null && status === 'initializing' ? (
          <p role="status" className="mt-6 text-sm text-muted-foreground">
            Confirming your account
          </p>
        ) : (
          <div role="status">
            <h1 className="mt-6 text-3xl font-semibold tracking-tight">
              This link did not work
            </h1>
            <p className="mt-3 text-sm text-muted-foreground">
              Confirmation links expire and can only be used once. Sign in if
              you already confirmed, or create the account again.
            </p>
            <p className="mt-4 text-sm text-muted-foreground">
              <Link to="/sign-in" className="underline underline-offset-4">
                Sign in
              </Link>
              {' or '}
              <Link to="/sign-up" className="underline underline-offset-4">
                create account
              </Link>
            </p>
          </div>
        )}

        <div className="mt-6 border-t border-border pt-3">
          <ApiStatusLine />
        </div>
      </div>
    </main>
  )
}
