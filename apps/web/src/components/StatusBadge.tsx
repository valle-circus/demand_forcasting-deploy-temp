import type { ImportStatus } from '@/lib/types'

/**
 * A status pill: a tinted fill, a dark label, and a matching dot.
 *
 * Colour never carries the status on its own — it survives greyscale, colour
 * blindness, and a photocopied screenshot of the screen. The fill is what makes
 * it readable at a glance: an outlined pill reduces the colour to a 1px stroke
 * at 12px, so every status ends up weighing the same.
 *
 * The fills come from the brand's own system pairs and are deliberately not the
 * accent hue — the accent means "act on this", and a status must never compete
 * with it.
 */

export type StatusTone = 'ready' | 'warning' | 'blocked' | 'running' | 'neutral'

const TONE: Record<StatusTone, string> = {
  ready: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  blocked: 'bg-danger-soft text-danger',
  running: 'bg-neutral-soft text-neutral',
  neutral: 'bg-neutral-soft text-neutral',
}

export function StatusBadge({
  tone,
  label,
}: {
  tone: StatusTone
  label: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${TONE[tone]}`}
    >
      {/* Hollow while work is in flight, filled once it has settled. A ring
          rather than a pulse: nothing in this app loops. */}
      <span
        aria-hidden="true"
        className={`size-1.5 shrink-0 rounded-full ${
          tone === 'running'
            ? 'border border-current'
            : 'bg-current'
        }`}
      />
      {label}
    </span>
  )
}

const IMPORT_PRESENTATION: Record<
  ImportStatus,
  { tone: StatusTone; label: string }
> = {
  received: { tone: 'neutral', label: 'Received' },
  validating: { tone: 'running', label: 'Validating' },
  accepted: { tone: 'ready', label: 'Accepted' },
  // Accepted, but with evidence worth reading. Never shown as a plain pass.
  accepted_with_warnings: { tone: 'warning', label: 'Warnings' },
  rejected: { tone: 'blocked', label: 'Rejected' },
}

export function ImportStatusBadge({ status }: { status: ImportStatus }) {
  const { tone, label } = IMPORT_PRESENTATION[status]
  return <StatusBadge tone={tone} label={label} />
}
