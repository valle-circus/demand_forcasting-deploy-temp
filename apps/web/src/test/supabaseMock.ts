import { vi } from 'vitest'

/**
 * A minimal stand-in for the parts of supabase-js the application uses: reading
 * the current session, subscribing to session changes, signing in, and signing
 * out. Tests drive it directly rather than talking to a real project.
 */

export interface FakeSession {
  access_token: string
  user: { id: string; email?: string }
}

type AuthCallback = (event: string, session: FakeSession | null) => void

export interface FakeSupabase {
  client: {
    auth: {
      getSession: () => Promise<{ data: { session: FakeSession | null } }>
      onAuthStateChange: (callback: AuthCallback) => {
        data: { subscription: { unsubscribe: () => void } }
      }
      signInWithPassword: (credentials: {
        email: string
        password: string
      }) => Promise<{ error: { message: string } | null }>
      signUp: (credentials: {
        email: string
        password: string
        options?: { emailRedirectTo?: string }
      }) => Promise<{
        data: { session: FakeSession | null }
        error: { message: string } | null
      }>
      signOut: () => Promise<{ error: null }>
    }
  }
  /** Push a new session (or `null` for signed out) to every subscriber. */
  emit: (session: FakeSession | null) => void
  /** Fail the next `signInWithPassword` call with this Supabase message. */
  failSignInWith: (message: string) => void
  /** Fail the next `signUp` call with this Supabase message. */
  failSignUpWith: (message: string) => void
  /**
   * Return a session from the next `signUp`, i.e. the project has email
   * confirmation switched off.
   */
  signUpReturnsSession: () => void
  signInWithPassword: ReturnType<typeof vi.fn>
  signUp: ReturnType<typeof vi.fn>
}

export const TEST_SESSION: FakeSession = {
  access_token: 'test-access-token',
  user: { id: 'user-1', email: 'maintainer@example.com' },
}

export function createFakeSupabase(
  initialSession: FakeSession | null = null,
): FakeSupabase {
  let session = initialSession
  let nextSignInError: string | null = null
  let nextSignUpError: string | null = null
  let signUpYieldsSession = false
  const subscribers = new Set<AuthCallback>()

  const emit = (next: FakeSession | null): void => {
    session = next
    for (const callback of subscribers) {
      callback(next ? 'SIGNED_IN' : 'SIGNED_OUT', next)
    }
  }

  const signInWithPassword = vi.fn(async () => {
    if (nextSignInError !== null) {
      const message = nextSignInError
      nextSignInError = null
      return { error: { message } }
    }
    emit(TEST_SESSION)
    return { error: null }
  })

  /**
   * Mirrors the real default: with email confirmation on, a successful sign-up
   * returns no session, because the account is not usable until the emailed
   * link is opened.
   */
  const signUp = vi.fn(async () => {
    if (nextSignUpError !== null) {
      const message = nextSignUpError
      nextSignUpError = null
      return { data: { session: null }, error: { message } }
    }
    if (signUpYieldsSession) {
      emit(TEST_SESSION)
      return { data: { session: TEST_SESSION }, error: null }
    }
    return { data: { session: null }, error: null }
  })

  return {
    client: {
      auth: {
        getSession: async () => ({ data: { session } }),
        onAuthStateChange: (callback: AuthCallback) => {
          subscribers.add(callback)
          return {
            data: {
              subscription: {
                unsubscribe: () => {
                  subscribers.delete(callback)
                },
              },
            },
          }
        },
        signInWithPassword,
        signUp,
        signOut: async () => {
          emit(null)
          return { error: null }
        },
      },
    },
    emit,
    failSignInWith: (message: string) => {
      nextSignInError = message
    },
    failSignUpWith: (message: string) => {
      nextSignUpError = message
    },
    signUpReturnsSession: () => {
      signUpYieldsSession = true
    },
    signInWithPassword,
    signUp,
  }
}

/** A readiness body for the shell's dependency indicator. */
export function readinessResponse(
  supabaseStatus: 'ready' | 'not_configured' | 'unavailable' = 'ready',
): Response {
  return new Response(
    JSON.stringify({
      status: supabaseStatus === 'ready' ? 'ready' : 'degraded',
      service: 'supply-planning-api',
      version: '0.1.0',
      environment: 'development',
      supabase: { status: supabaseStatus, message: 'Test readiness message.' },
    }),
    { status: 200, headers: { 'content-type': 'application/json' } },
  )
}
