import { useEffect } from 'react'
import { useParams } from 'react-router-dom'

import { useSelectedLocation } from '../../app/location/locationContext'
import { NotBuiltYet } from '../../components/NotBuiltYet'
import { LocationChooserPage } from './LocationChooserPage'

export function LocationPlanningPage() {
  const { locationId } = useParams<{ locationId: string }>()
  const { setLocationId } = useSelectedLocation()

  // Remember the location so the navigation link and the location-scoped
  // upload cards land here again after visiting another page.
  useEffect(() => {
    if (locationId) {
      setLocationId(locationId)
    }
  }, [locationId, setLocationId])

  if (!locationId) {
    return <LocationChooserPage />
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-600">
        Location <span className="font-semibold text-stone-950">{locationId}</span>
      </p>
      <NotBuiltYet
        workPackage="WP4"
        summary="The operational working page: location header and source-freshness strip, preflight blockers with the run button disabled and its reason shown, one synchronous Compute latest recommendation action, and the Risk & stock, Open POs, and Recommendation views with the derivation drawer and server-generated CSV/JSON downloads."
      />
    </div>
  )
}
