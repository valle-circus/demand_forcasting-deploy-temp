import { humanizeCode } from '../../lib/formatting'
import type { ValidationIssue } from '../../lib/types'

const SEVERITY_ORDER = { blocker: 0, warning: 1, info: 2 } as const

const SEVERITY_STYLES = {
  blocker: 'border-rose-300 bg-rose-50',
  warning: 'border-amber-300 bg-amber-50',
  info: 'border-stone-200 bg-stone-50',
} as const

const SEVERITY_LABELS = {
  blocker: 'Blocker',
  warning: 'Warning',
  info: 'Note',
} as const

/**
 * Validation issues, each with the remedy the API supplied.
 *
 * The API always sends a `remedy`, so there is never a reason to show a
 * maintainer a problem without telling them how to fix it. Blockers sort
 * first: when a file is rejected, the reason it was rejected is what matters,
 * not the warnings alongside it.
 */
export function ImportIssueList({ issues }: { issues: ValidationIssue[] }) {
  if (issues.length === 0) {
    return null
  }

  const sorted = [...issues].sort(
    (left, right) =>
      (SEVERITY_ORDER[left.severity] ?? 3) - (SEVERITY_ORDER[right.severity] ?? 3),
  )

  return (
    <ul className="space-y-2">
      {sorted.map((issue, index) => (
        <li
          key={`${issue.code}-${issue.record_ref ?? String(index)}`}
          className={`rounded-lg border p-3 text-xs ${SEVERITY_STYLES[issue.severity] ?? SEVERITY_STYLES.info}`}
        >
          <p className="font-semibold text-stone-900">
            {SEVERITY_LABELS[issue.severity] ?? 'Note'} ·{' '}
            {humanizeCode(issue.code)}
          </p>
          <p className="mt-1 leading-5 text-stone-700">{issue.message}</p>

          {(issue.dataset !== null || issue.record_ref !== null) && (
            <p className="mt-1 text-stone-500">
              {[issue.dataset, issue.record_ref].filter(Boolean).join(' · ')}
            </p>
          )}

          <p className="mt-2 leading-5 text-stone-700">
            <span className="font-medium">How to fix: </span>
            {issue.remedy}
          </p>
        </li>
      ))}
    </ul>
  )
}
