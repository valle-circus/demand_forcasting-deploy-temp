import { createContext, useContext } from 'react'

/**
 * Authentication states the UI must distinguish.
 *
 * `unconfigured` is deliberately separate from `signed-out`: without browser
 * Supabase values there is no sign-in to attempt, and showing a login form that
 * cannot possibly work would be dishonest.
 */
export type AuthStatus =
  | 'initializing'
  | 'unconfigured'
  | 'signed-out'
  | 'signed-in'

export interface AuthUser {
  id: string
  email: string | null
}

/**
 * What happened after a successful `signUp` call.
 *
 * `confirmation-sent` is also what a repeat sign-up with an already-registered
 * address returns. Supabase deliberately does not distinguish the two, so that
 * the form cannot be used to discover who has an account, and neither does
 * this application.
 */
export type SignUpOutcome = 'confirmation-sent' | 'signed-in'

export interface AuthValue {
  status: AuthStatus
  user: AuthUser | null
  /**
   * Explains an unexpected sign-out, e.g. an expired session, so the gate can
   * say why the maintainer is looking at it again.
   */
  notice: string | null
  /** Rejects with a readable message; the sign-in form renders it. */
  signIn: (email: string, password: string) => Promise<void>
  /** Rejects with a readable message; the sign-up form renders it. */
  signUp: (email: string, password: string) => Promise<SignUpOutcome>
  signOut: () => Promise<void>
  clearNotice: () => void
}

export const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (value === null) {
    throw new Error('useAuth must be used inside <AuthProvider>.')
  }
  return value
}
