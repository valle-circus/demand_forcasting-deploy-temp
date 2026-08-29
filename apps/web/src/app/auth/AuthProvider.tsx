import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import {
  configureAuthTokenProvider,
  configureUnauthorizedHandler,
} from '../../lib/apiClient'
import { browserSupabaseConfigured, getSupabaseClient } from '../../lib/supabase'
import { AuthContext } from './authContext'
import type { AuthUser, AuthValue } from './authContext'

/**
 * Registered at module scope rather than in an effect so that a request issued
 * during the first render still finds a token provider. Reads the session from
 * supabase-js on every call, which returns a refreshed token when the previous
 * one has expired.
 */
configureAuthTokenProvider(async () => {
  const client = getSupabaseClient()
  if (client === null) {
    return null
  }
  const { data } = await client.auth.getSession()
  return data.session?.access_token ?? null
})

/** Supabase's own messages are terse and sometimes leak internals. */
function signInMessage(raw: string): string {
  const normalized = raw.toLowerCase()
  if (normalized.includes('invalid login credentials')) {
    return 'That email and password combination was not recognised.'
  }
  if (normalized.includes('email not confirmed')) {
    return 'This account has not been confirmed yet. Ask an administrator to confirm it in Supabase.'
  }
  if (normalized.includes('failed to fetch') || normalized.includes('network')) {
    return 'Supabase could not be reached. Check your connection and try again.'
  }
  return raw
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthValue['status']>(
    browserSupabaseConfigured ? 'initializing' : 'unconfigured',
  )
  const [user, setUser] = useState<AuthUser | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    const client = getSupabaseClient()
    if (client === null) {
      setStatus('unconfigured')
      return
    }

    let active = true

    void client.auth.getSession().then(({ data }) => {
      if (!active) {
        return
      }
      const session = data.session
      setUser(
        session ? { id: session.user.id, email: session.user.email ?? null } : null,
      )
      setStatus(session ? 'signed-in' : 'signed-out')
    })

    const { data: subscription } = client.auth.onAuthStateChange(
      (_event, session) => {
        if (!active) {
          return
        }
        setUser(
          session
            ? { id: session.user.id, email: session.user.email ?? null }
            : null,
        )
        setStatus(session ? 'signed-in' : 'signed-out')
      },
    )

    return () => {
      active = false
      subscription.subscription.unsubscribe()
    }
  }, [])

  /**
   * The API rejected our token. Clear the session rather than retrying, and
   * explain why the sign-in gate reappeared.
   */
  useEffect(() => {
    configureUnauthorizedHandler(() => {
      setNotice('Your session has expired. Sign in again to continue.')
      const client = getSupabaseClient()
      if (client !== null) {
        void client.auth.signOut()
      } else {
        setUser(null)
        setStatus('signed-out')
      }
    })
    return () => {
      configureUnauthorizedHandler(() => undefined)
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const client = getSupabaseClient()
    if (client === null) {
      throw new Error(
        'Supabase authentication is not configured for this build.',
      )
    }
    setNotice(null)
    const { error } = await client.auth.signInWithPassword({ email, password })
    if (error) {
      throw new Error(signInMessage(error.message))
    }
  }, [])

  const signOut = useCallback(async () => {
    setNotice(null)
    const client = getSupabaseClient()
    if (client === null) {
      setUser(null)
      setStatus('signed-out')
      return
    }
    await client.auth.signOut()
  }, [])

  const clearNotice = useCallback(() => {
    setNotice(null)
  }, [])

  const value = useMemo<AuthValue>(
    () => ({ status, user, notice, signIn, signOut, clearNotice }),
    [status, user, notice, signIn, signOut, clearNotice],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
