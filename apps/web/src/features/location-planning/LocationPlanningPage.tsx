import { useEffect } from 'react'
import { useParams } from 'react-router-dom'

import { useSelectedLocation } from '@/app/location/locationContext'
import { NotBuiltYet } from '@/components/NotBuiltYet'
import { LocationChooserPage } from './LocationChooserPage'

export function LocationPlanningPage() {
  const { locationId } = useParams<{ locationId: string }>()
  const { setLocationId } = useSelectedLocation()

  // Remember it so navigation and the location-scoped uploads come back here.
  useEffect(() => {
    if (locationId) {
      setLocationId(locationId)
    }
  }, [locationId, setLocationId])

  if (!locationId) {
    return <LocationChooserPage />
  }

  return (
    <div className="mx-auto max-w-[1280px] space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">
        Location planning
      </h1>
      <NotBuiltYet summary="Source freshness, what is blocking a run, the run itself, and how each proposed quantity was derived." />
    </div>
  )
}
