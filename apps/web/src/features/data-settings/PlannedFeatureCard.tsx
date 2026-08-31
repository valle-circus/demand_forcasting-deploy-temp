/**
 * A maintained-data editor that is planned but not built.
 *
 * Rendered as visibly unavailable rather than as a control that would fail.
 * The reason each one is deferred lives in the backlog, not on the screen.
 */
export function PlannedFeatureCard({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="rounded-lg border border-dashed border-border px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
        <span className="text-xs text-faint">Planned</span>
      </div>
      <p className="mt-1 text-xs text-faint">{description}</p>
    </div>
  )
}
