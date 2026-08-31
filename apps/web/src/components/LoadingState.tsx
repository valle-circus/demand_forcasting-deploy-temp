/**
 * Skeletons rather than a spinner, so the page does not jump when data lands.
 * The label is for assistive technology; sighted users see the shapes.
 */
export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      {[0, 1, 2].map((row) => (
        <div
          key={row}
          className="h-20 animate-pulse rounded-lg border border-border bg-surface"
        />
      ))}
    </div>
  )
}
