import type { ReactNode } from 'react'

type StatusTone = 'ready' | 'pending' | 'error'

interface StatusCardProps {
  eyebrow: string
  title: string
  status: string
  tone: StatusTone
  children: ReactNode
}

const toneStyles: Record<StatusTone, string> = {
  ready: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  pending: 'border-amber-200 bg-amber-50 text-amber-900',
  error: 'border-rose-200 bg-rose-50 text-rose-900',
}

export function StatusCard({
  eyebrow,
  title,
  status,
  tone,
  children,
}: StatusCardProps) {
  return (
    <article className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">
            {eyebrow}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-stone-950">{title}</h2>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${toneStyles[tone]}`}
        >
          {status}
        </span>
      </div>
      <div className="mt-5 text-sm leading-6 text-stone-600">{children}</div>
    </article>
  )
}
