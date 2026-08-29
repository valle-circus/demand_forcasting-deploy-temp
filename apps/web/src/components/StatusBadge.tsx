/**
 * The one status vocabulary for the whole application.
 *
 * Colour is never the carrier: every badge renders an icon and a text label as
 * well, so the status survives greyscale, colour blindness, and a screen
 * reader. Journey doc §8 requires this explicitly.
 */

import type { ImportStatus } from '../lib/types'

export type StatusTone = 'ready' | 'warning' | 'blocked' | 'running' | 'neutral'

const TONE_STYLES: Record<StatusTone, string> = {
  ready: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  warning: 'border-amber-300 bg-amber-50 text-amber-900',
  blocked: 'border-rose-300 bg-rose-50 text-rose-900',
  running: 'border-sky-300 bg-sky-50 text-sky-900',
  neutral: 'border-stone-300 bg-stone-50 text-stone-700',
}

const TONE_ICONS: Record<StatusTone, string> = {
  ready: 'M5 13l4 4L19 7',
  warning: 'M12 9v4m0 4h.01M10.3 4.3 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z',
  blocked: 'M12 9v4m0 4h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z',
  running: 'M12 3a9 9 0 1 0 9 9',
  neutral: 'M5 12h14',
}

interface StatusBadgeProps {
  tone: StatusTone
  label: string
  /** Optional clarification rendered beside the label, e.g. a timestamp. */
  detail?: string
}

export function StatusBadge({ tone, label, detail }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${TONE_STYLES[tone]}`}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`size-3.5 shrink-0 ${tone === 'running' ? 'animate-spin' : ''}`}
      >
        <path d={TONE_ICONS[tone]} />
      </svg>
      <span>{label}</span>
      {detail !== undefined && (
        <span className="font-normal opacity-80">· {detail}</span>
      )}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Import status
// ---------------------------------------------------------------------------

const IMPORT_PRESENTATION: Record<ImportStatus, { tone: StatusTone; label: string }> =
  {
    received: { tone: 'neutral', label: 'Received' },
    validating: { tone: 'running', label: 'Validating' },
    accepted: { tone: 'ready', label: 'Accepted' },
    // Accepted, but with evidence the maintainer needs to see. Never silently
    // downgraded to a plain "Accepted".
    accepted_with_warnings: { tone: 'warning', label: 'Accepted with warnings' },
    rejected: { tone: 'blocked', label: 'Rejected' },
  }

export function ImportStatusBadge({ status }: { status: ImportStatus }) {
  const { tone, label } = IMPORT_PRESENTATION[status]
  return <StatusBadge tone={tone} label={label} />
}
