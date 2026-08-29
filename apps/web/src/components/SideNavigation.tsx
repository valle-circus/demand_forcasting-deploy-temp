import { NavLink } from 'react-router-dom'

import { useSelectedLocation } from '../app/location/locationContext'

interface NavIconProps {
  path: string
}

function NavIcon({ path }: NavIconProps) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4.5 shrink-0"
    >
      <path d={path} />
    </svg>
  )
}

const ICONS = {
  overview: 'M3 12h4l3 8 4-16 3 8h4',
  location: 'M12 21s7-5.686 7-11a7 7 0 1 0-14 0c0 5.314 7 11 7 11Z M12 10h.01',
  data: 'M12 3v12m0 0-4-4m4 4 4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2',
} as const

/**
 * Exactly three primary destinations, per the journey document. Subsections
 * inside a page never become additional navigation items.
 */
export function SideNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { locationId } = useSelectedLocation()

  // Fall back to the chooser rather than guessing a location the maintainer
  // has not selected.
  const locationHref =
    locationId === null
      ? '/locations'
      : `/locations/${encodeURIComponent(locationId)}`

  const items = [
    { to: '/overview', label: 'Overview', icon: ICONS.overview },
    { to: locationHref, label: 'Location planning', icon: ICONS.location },
    { to: '/data', label: 'Data & settings', icon: ICONS.data },
  ]

  return (
    <nav aria-label="Primary">
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.label}>
            <NavLink
              to={item.to}
              onClick={onNavigate}
              // `/locations/:id` and `/locations` are the same destination.
              className={({ isActive }) =>
                [
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition',
                  'focus-visible:ring-2 focus-visible:ring-lime-400 focus-visible:outline-none',
                  isActive
                    ? 'bg-stone-800 font-semibold text-lime-300'
                    : 'font-medium text-stone-300 hover:bg-stone-800/60 hover:text-stone-50',
                ].join(' ')
              }
            >
              {({ isActive }) => (
                <>
                  <NavIcon path={item.icon} />
                  <span>{item.label}</span>
                  {/* Active state is announced, not only coloured. */}
                  {isActive && <span className="sr-only">(current page)</span>}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
