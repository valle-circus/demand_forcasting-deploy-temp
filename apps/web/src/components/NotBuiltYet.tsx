/**
 * An explicit placeholder. It never renders sample numbers or mock tables — a
 * screen that looks populated but is not connected is worse than an empty one.
 */
export function NotBuiltYet({ summary }: { summary: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border px-4 py-6 text-center">
      <p className="text-sm text-muted-foreground">Not built yet</p>
      <p className="mx-auto mt-1 max-w-md text-xs text-faint">{summary}</p>
    </div>
  )
}
