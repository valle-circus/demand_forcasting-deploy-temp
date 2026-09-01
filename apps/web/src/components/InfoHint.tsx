import { Info } from 'lucide-react'
import { useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'

const PANEL_WIDTH = 256
const VIEWPORT_MARGIN = 8

/**
 * The definition layer: what a metric means and which window it uses.
 *
 * Focusable and toggled by click, not hover-only, so it works by keyboard and
 * on touch. It is strictly for nice-to-know explanation — a required warning,
 * blocker, approximation or remedy must never live only in here, because
 * anyone who does not open it would miss it.
 *
 * The panel renders in a portal because these triggers sit in table headers,
 * and a table lives inside an `overflow-x-auto` wrapper. Overflow on one axis
 * computes to `auto` on the other, so an in-flow popover is clipped by the
 * scroll container. The portal also escapes the header's `whitespace-nowrap`,
 * which otherwise forced the whole explanation onto one line.
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
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()

  useLayoutEffect(() => {
    if (!open || triggerRef.current === null) {
      return
    }
    const rect = triggerRef.current.getBoundingClientRect()
    // Keep the panel inside the viewport rather than letting it run off the
    // right edge, which is where most of these triggers sit.
    const maxLeft = window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN
    setPosition({
      top: rect.bottom + window.scrollY + 6,
      left: Math.max(VIEWPORT_MARGIN, Math.min(rect.left + window.scrollX, maxLeft)),
    })
  }, [open])

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
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

      {open &&
        createPortal(
          <span
            id={panelId}
            role="note"
            style={{
              top: position.top,
              left: position.left,
              width: PANEL_WIDTH,
            }}
            className="absolute z-50 block rounded-md border border-border bg-popover px-3 py-2 text-left text-xs leading-5 font-normal whitespace-normal text-muted-foreground shadow-md"
          >
            {children}
          </span>,
          document.body,
        )}
    </>
  )
}
