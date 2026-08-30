import type { ImportStatus } from '@/lib/types'

/**
 * A status pill: a coloured dot plus a word.
 *
 * Colour never carries the status on its own — it survives greyscale, colour
 * blindness, and a photocopied screenshot of the screen.
 */

export type StatusTone = 'ready' | 'warning' | 'blocked' | 'running' | 'neutral'

const DOT: Record<StatusTone, string> = {
  ready: 'bg-success',
  warning: 'bg-warning',
  blocked: 'bg-danger',
  running: 'bg-info',
  neutral: 'bg-faint',
}

const TEXT: Record<StatusTone, string> = {
  ready: 'text-foreground',
  warning: 'text-warning',
  blocked: 'text-danger',
  running: 'text-info',
  neutral: 'text-muted-foreground',
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
      className={`inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${TEXT[tone]}`}
    >
      <span
        aria-hidden="true"
        className={`size-1.5 shrink-0 rounded-full ${DOT[tone]} ${
          tone === 'running' ? 'animate-pulse' : ''
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
