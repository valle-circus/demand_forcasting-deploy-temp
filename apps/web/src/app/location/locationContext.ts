import { createContext, useContext } from 'react'

export interface SelectedLocationValue {
  /** The location the maintainer last worked with, if any. */
  locationId: string | null
  setLocationId: (locationId: string) => void
}

export const SelectedLocationContext =
  createContext<SelectedLocationValue | null>(null)

export function useSelectedLocation(): SelectedLocationValue {
  const value = useContext(SelectedLocationContext)
  if (value === null) {
    throw new Error(
      'useSelectedLocation must be used inside <SelectedLocationProvider>.',
    )
  }
  return value
}
