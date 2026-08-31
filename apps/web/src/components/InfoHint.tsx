import { Info } from 'lucide-react'
import { useId, useState } from 'react'
import type { ReactNode } from 'react'

/**
 * The definition layer: what a metric means and which window it uses.
 *
 * Focusable and toggled by click, not hover-only, so it works by keyboard and
 * on touch. It is strictly for nice-to-know explanation — a required warning,
 * blocker, approximation or remedy must never live only in here, because
 * anyone who does not open it would miss it.
 */
export function InfoHint({
  label,
  children,
}: {
  /** Accessible name for the trigger, phrased as the question it answers. */
  label: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const panelId = useId()

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={(event) => {
          // Rows around these are clickable; explaining a column should not
          // also open the row.
          event.stopPropagation()
          setOpen((value) => !value)
        }}
        onBlur={() => {
          setOpen(false)
        }}
        className="inline-grid size-4 place-items-center rounded-full text-faint transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <Info aria-hidden="true" className="size-3.5" />
      </button>

      {open && (
        <span
          id={panelId}
          role="note"
          className="absolute top-6 left-0 z-30 w-60 rounded-md border border-border bg-popover px-3 py-2 text-xs leading-5 font-normal text-muted-foreground shadow-md"
        >
          {children}
        </span>
      )}
    </span>
  )
}
