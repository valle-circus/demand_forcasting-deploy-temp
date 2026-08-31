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
