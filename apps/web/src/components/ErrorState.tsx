import { errorMessage, isApiError, isUnavailable } from '../lib/errors'

interface ErrorStateProps {
  error: Error
  onRetry?: () => void
  /** Overrides the derived heading when the caller has better context. */
  title?: string
}

/**
 * Renders a failed request as a failure.
 *
 * The one distinction that always matters: a 503 means a dependency is
 * unavailable or unconfigured, which is emphatically not "there is no data".
 * Collapsing the two would let a broken database read as an empty kitchen.
 */
export function ErrorState({ error, onRetry, title }: ErrorStateProps) {
  const unavailable = isUnavailable(error)

  const heading =
    title ??
    (unavailable
      ? 'A required service is unavailable'
      : 'This information could not be loaded')

  return (
    <div
      role="alert"
      className="rounded-xl border border-rose-300 bg-rose-50 p-6 sm:p-8"
    >
      <h2 className="text-base font-semibold text-rose-950">{heading}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-rose-900">
        {errorMessage(error)}
      </p>
      {unavailable && (
        <p className="mt-2 max-w-2xl text-sm leading-6 text-rose-900">
          This is a configuration or connection problem, not an empty result. No
          planning data can be trusted until it is resolved.
        </p>
      )}
      {isApiError(error) && error.fieldIssues.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-rose-900">
          {error.fieldIssues.map((issue) => (
            <li key={`${issue.field}-${issue.type}`}>
              <span className="font-medium">{issue.field}</span>: {issue.message}
            </li>
          ))}
        </ul>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 rounded-lg border border-rose-400 bg-white px-4 py-2 text-sm font-semibold text-rose-900 transition hover:bg-rose-100 focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:outline-none"
        >
          Try again
        </button>
      )}
    </div>
  )
}
