import { Database, LayoutDashboard, MapPin } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { useSelectedLocation } from '@/app/location/locationContext'

/**
 * Exactly three primary destinations. Subsections inside a page never become
 * navigation items.
 */
export function SideNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { locationId } = useSelectedLocation()

  const items = [
    { to: '/overview', label: 'Overview', Icon: LayoutDashboard },
    {
      // Falls back to the chooser rather than guessing an unselected location.
      to:
        locationId === null
          ? '/locations'
          : `/locations/${encodeURIComponent(locationId)}`,
      label: 'Location planning',
      Icon: MapPin,
    },
    { to: '/data', label: 'Data & settings', Icon: Database },
  ]

  return (
    <nav aria-label="Primary">
      <ul className="space-y-0.5">
        {items.map(({ to, label, Icon }) => (
          <li key={label}>
            <NavLink
              to={to}
              onClick={onNavigate}
              className={({ isActive }) =>
                [
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
                  'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                  isActive
                    ? 'bg-accent-soft font-medium text-accent-text'
                    : 'text-muted-foreground hover:bg-surface hover:text-foreground',
                ].join(' ')
              }
            >
              {({ isActive }) => (
                <>
                  <Icon aria-hidden="true" className="size-4 shrink-0" />
                  <span>{label}</span>
                  {/* Announced, not only coloured. */}
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
