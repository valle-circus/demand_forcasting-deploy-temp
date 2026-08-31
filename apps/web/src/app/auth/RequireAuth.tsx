import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './authContext'

/**
 * Gates every domain route. While the session is being restored it shows a
 * neutral wait rather than flashing the sign-in form on every page load for an
 * already-signed-in maintainer.
 */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'initializing') {
    return (
      <div
        role="status"
        className="grid min-h-screen place-items-center text-sm text-muted-foreground"
      >
        Restoring your session
      </div>
    )
  }

  if (status !== 'signed-in') {
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
