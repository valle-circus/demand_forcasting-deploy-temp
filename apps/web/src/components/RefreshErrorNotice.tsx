import { errorMessage } from '@/lib/errors'

export function RefreshErrorNotice({
  error,
  onRetry,
}: {
  error: Error | null
  onRetry: () => void
}) {
  if (error === null) {
    return null
  }

  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-xs text-warning"
    >
      <span>Showing previously loaded data. Refresh failed: {errorMessage(error)}</span>
      <button
        type="button"
        className="font-medium underline underline-offset-2"
        onClick={onRetry}
      >
        Try again
      </button>
    </div>
  )
}
