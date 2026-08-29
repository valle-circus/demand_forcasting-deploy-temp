import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface EmptyStateProps {
  title: string
  description: ReactNode
  /**
   * Required. Journey doc §2.2: every risk or gap leads to an action. An
   * empty state that leaves the maintainer with nowhere to go is a dead end,
   * so the type does not allow one.
   */
  action: { label: string; to: string }
  tone?: 'neutral' | 'attention'
}

export function EmptyState({
  title,
  description,
  action,
  tone = 'neutral',
}: EmptyStateProps) {
  const attention = tone === 'attention'

  return (
    <div
      className={[
        'rounded-xl border p-6 sm:p-8',
        attention
          ? 'border-amber-300 bg-amber-50'
          : 'border-stone-200 bg-white',
      ].join(' ')}
    >
      <h2
        className={[
          'text-base font-semibold',
          attention ? 'text-amber-950' : 'text-stone-950',
        ].join(' ')}
      >
        {title}
      </h2>
      <div
        className={[
          'mt-2 max-w-2xl text-sm leading-6',
          attention ? 'text-amber-900' : 'text-stone-600',
        ].join(' ')}
      >
        {description}
      </div>
      <Link
        to={action.to}
        className="mt-5 inline-flex rounded-lg bg-lime-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-lime-700 focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:ring-offset-2 focus-visible:outline-none"
      >
        {action.label}
      </Link>
    </div>
  )
}
