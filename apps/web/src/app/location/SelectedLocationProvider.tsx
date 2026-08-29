import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { SelectedLocationContext } from './locationContext'
import type { SelectedLocationValue } from './locationContext'

const STORAGE_KEY = 'supply-planning.selected-location'

/**
 * Session storage, not local storage: the remembered location is a
 * within-visit convenience, not a durable preference. Every access is guarded
 * because storage throws in private windows and when site data is blocked.
 */
function readStored(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStored(locationId: string): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, locationId)
  } catch {
    // A remembered selection is a nicety; losing it must never break a page.
  }
}

/**
 * Keeps the selected location stable while the maintainer moves between
 * Overview, Location planning, and Data & settings, so location-scoped upload
 * cards and the navigation link land on the location they were just working on.
 */
export function SelectedLocationProvider({ children }: { children: ReactNode }) {
  const [locationId, setLocationIdState] = useState<string | null>(readStored)

  const setLocationId = useCallback((next: string) => {
    setLocationIdState(next)
    writeStored(next)
  }, [])

  const value = useMemo<SelectedLocationValue>(
    () => ({ locationId, setLocationId }),
    [locationId, setLocationId],
  )

  return (
    <SelectedLocationContext value={value}>{children}</SelectedLocationContext>
  )
}
