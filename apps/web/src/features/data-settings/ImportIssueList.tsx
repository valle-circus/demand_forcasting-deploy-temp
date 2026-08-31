import { humanizeCode } from '@/lib/formatting'
import type { ValidationIssue } from '@/lib/types'

const SEVERITY_ORDER = { blocker: 0, warning: 1, info: 2 } as const

const SEVERITY_TEXT = {
  blocker: 'text-danger',
  warning: 'text-warning',
  info: 'text-muted-foreground',
} as const

/**
 * What went wrong, then what to do about it — in that order.
 *
 * The API always supplies a remedy, so there is never a reason to show a
 * problem without the fix. Blockers sort first: when a file is rejected, the
 * reason it was rejected matters more than the warnings beside it.
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
    <ul className="space-y-2 border-t border-border pt-3">
      {sorted.map((issue, index) => (
        <li
          key={`${issue.code}-${issue.record_ref ?? String(index)}`}
          className="text-xs"
        >
          <p className={SEVERITY_TEXT[issue.severity] ?? SEVERITY_TEXT.info}>
            {issue.message}
          </p>
          <p className="mt-0.5 text-muted-foreground">{issue.remedy}</p>
          {issue.record_ref !== null && (
            <p className="mt-0.5 text-faint tabular">
              {humanizeCode(issue.code)} · {issue.record_ref}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
