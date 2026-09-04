import type { ImportStatus } from '@/lib/types'

/**
 * A compact status pill with a text label and matching dot.
 *
 * Routine states stay outlined so dense tables remain calm. Only a genuinely
 * blocking state receives a tinted fill. Colour is never the only carrier of
 * meaning: every state also has a plain-language label and dot treatment.
 */

export type StatusTone = 'ready' | 'warning' | 'blocked' | 'running' | 'neutral'

const TONE: Record<StatusTone, string> = {
  ready: 'border-border bg-card text-success',
  warning: 'border-border bg-card text-warning',
  blocked: 'border-danger-soft bg-danger-soft text-danger',
  running: 'border-border bg-card text-neutral',
  neutral: 'border-border bg-card text-neutral',
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
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${TONE[tone]}`}
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
