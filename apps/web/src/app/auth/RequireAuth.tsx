import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './authContext'

/**
 * Gates every domain route. While the session is being restored it renders a
 * neutral waiting state rather than flashing the sign-in form, which would
 * otherwise appear on every page load for an already-signed-in maintainer.
 */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'initializing') {
    return (
      <div
        role="status"
        className="grid min-h-screen place-items-center bg-stone-100 text-sm text-stone-600"
      >
        Restoring your session…
      </div>
    )
  }

  if (status !== 'signed-in') {
    // Remember where they were headed so sign-in returns them there.
    return (
      <Navigate
        to="/sign-in"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }

  return <Outlet />
}
