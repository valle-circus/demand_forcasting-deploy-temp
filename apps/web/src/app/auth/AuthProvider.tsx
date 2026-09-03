import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import {
  configureAuthTokenProvider,
  configureUnauthorizedHandler,
} from '../../lib/apiClient'
import { clearResourceCache } from '../../lib/resourceCache'
import {
  allowedEmailDomainsLabel,
  emailDomainAllowed,
} from '../../lib/emailDomains'
import { browserSupabaseConfigured, getSupabaseClient } from '../../lib/supabase'
import { AuthContext } from './authContext'
import type { AuthUser, AuthValue, SignUpOutcome } from './authContext'

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
    return 'Confirm your email address first. Open the link in the message we sent when you created the account.'
  }
  if (normalized.includes('failed to fetch') || normalized.includes('network')) {
    return 'Supabase could not be reached. Check your connection and try again.'
  }
  return raw
}

/**
 * The domain rejection arrives from a database trigger, so Supabase reports it
 * as an opaque "database error saving new user" rather than as something the
 * person filling in the form can act on.
 */
function signUpMessage(raw: string): string {
  const normalized = raw.toLowerCase()
  if (
    normalized.includes('not approved') ||
    normalized.includes('database error') ||
    normalized.includes('email address is required')
  ) {
    return `Accounts are limited to ${allowedEmailDomainsLabel()} email addresses.`
  }
  if (normalized.includes('password')) {
    // Supabase's own password-policy text is already specific and useful.
    return raw
  }
  if (normalized.includes('rate limit') || normalized.includes('too many')) {
    return 'Too many attempts. Wait a few minutes and try again.'
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
      // Nothing to set: the client is null for exactly the reason `status`
      // already starts at 'unconfigured' - the same module-level flag.
      return
    }

    let active = true
    let activeUserId: string | null = null

    const applySession = (session: Awaited<ReturnType<typeof client.auth.getSession>>['data']['session']) => {
      const nextUserId = session?.user.id ?? null
      if (
        nextUserId === null ||
        (activeUserId !== null && activeUserId !== nextUserId)
      ) {
        clearResourceCache()
      }
      activeUserId = nextUserId
      setUser(
        session ? { id: session.user.id, email: session.user.email ?? null } : null,
      )
      setStatus(session ? 'signed-in' : 'signed-out')
    }

    void client.auth.getSession().then(({ data }) => {
      if (!active) {
        return
      }
      // The provider may remount while this module's memory cache survives.
      // Start every restored browser session from an explicit ownership gate.
      clearResourceCache()
      applySession(data.session)
    })

    const { data: subscription } = client.auth.onAuthStateChange(
      (_event, session) => {
        if (!active) {
          return
        }
        applySession(session)
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
      clearResourceCache()
      setUser(null)
      setStatus('signed-out')
      const client = getSupabaseClient()
      if (client !== null) {
        void client.auth.signOut()
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

  const signUp = useCallback(
    async (email: string, password: string): Promise<SignUpOutcome> => {
      const client = getSupabaseClient()
      if (client === null) {
        throw new Error(
          'Supabase authentication is not configured for this build.',
        )
      }
      // Checked again here rather than only in the form, so that every caller
      // gets the same refusal. Neither place is the actual gate.
      if (!emailDomainAllowed(email)) {
        throw new Error(
          `Accounts are limited to ${allowedEmailDomainsLabel()} email addresses.`,
        )
      }
      setNotice(null)
      const { data, error } = await client.auth.signUp({
        email,
        password,
        options: {
          // Must also be listed under Authentication -> URL Configuration in
          // Supabase, or the confirmation link falls back to the site URL.
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      })
      if (error) {
        throw new Error(signUpMessage(error.message))
      }
      return data.session ? 'signed-in' : 'confirmation-sent'
    },
    [],
  )

  const signOut = useCallback(async () => {
    setNotice(null)
    clearResourceCache()
    setUser(null)
    setStatus('signed-out')
    const client = getSupabaseClient()
    if (client === null) {
      return
    }
    await client.auth.signOut()
  }, [])

  const clearNotice = useCallback(() => {
    setNotice(null)
  }, [])

  const value = useMemo<AuthValue>(
    () => ({ status, user, notice, signIn, signUp, signOut, clearNotice }),
    [status, user, notice, signIn, signUp, signOut, clearNotice],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
