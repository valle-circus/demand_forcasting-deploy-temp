import { Button } from '@/components/ui/button'
import { errorMessage, isApiError, isUnavailable } from '@/lib/errors'

interface ErrorStateProps {
  error: Error
  onRetry?: () => void
  title?: string
}

/**
 * A failed request, shown as a failure.
 *
 * The distinction that always matters: a 503 means a dependency is down or
 * unconfigured, which is not "there is no data". Collapsing the two would let
 * a broken database read as an empty kitchen.
 */
export function ErrorState({ error, onRetry, title }: ErrorStateProps) {
  const unavailable = isUnavailable(error)

  return (
    <div
      role="alert"
      className="rounded-xl border border-border bg-card px-5 py-4"
    >
      <h2 className="text-sm font-medium text-danger">
        {title ??
          (unavailable ? 'A service is unavailable' : 'Could not load this')}
      </h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
        {errorMessage(error)}
      </p>
      {unavailable && (
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          This is a connection problem, not an empty result.
        </p>
      )}
      {isApiError(error) && error.fieldIssues.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
          {error.fieldIssues.map((issue) => (
            <li key={`${issue.field}-${issue.type}`}>
              {issue.field}: {issue.message}
            </li>
          ))}
        </ul>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}
