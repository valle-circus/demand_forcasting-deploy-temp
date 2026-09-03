import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from './AppShell'
import { RequireAuth } from './auth/RequireAuth'
import { AuthCallbackPage } from '../features/auth/AuthCallbackPage'
import { SignInPage } from '../features/auth/SignInPage'
import { SignUpPage } from '../features/auth/SignUpPage'
import { DataSettingsPage } from '../features/data-settings/DataSettingsPage'
import { LocationChooserPage } from '../features/location-planning/LocationChooserPage'
import { LocationPlanningPage } from '../features/location-planning/LocationPlanningPage'
import { OverviewPage } from '../features/overview/OverviewPage'

/**
 * Three primary destinations behind the sign-in gate, plus the gate itself and
 * the two public routes that create an account.
 *
 * `/locations` without an id is the same destination as `/locations/:id`, not
 * a fourth one — it is what the navigation link points at before a location
 * has been chosen.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/sign-up" element={<SignUpPage />} />
      {/* Target of the emailed confirmation link. Also needs to be listed as a
          redirect URL in the Supabase project. */}
      <Route path="/auth/callback" element={<AuthCallbackPage />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/locations" element={<LocationChooserPage />} />
          <Route path="/locations/:locationId" element={<LocationPlanningPage />} />
          <Route path="/data" element={<DataSettingsPage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}
