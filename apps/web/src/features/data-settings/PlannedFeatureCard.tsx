/**
 * A maintained-data editor that is planned but not built.
 *
 * The brief is explicit that field-level master, menu and BOM editing is a
 * later, separately scoped feature, and that the UI should show a clear
 * disabled state rather than invent an API for it. So these render as visibly
 * unavailable, with the reason, instead of as buttons that would fail.
 */
export function PlannedFeatureCard({
  title,
  description,
  reason,
}: {
  title: string
  description: string
  reason: string
}) {
  return (
    <div className="rounded-xl border border-dashed border-stone-300 bg-stone-50 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-stone-700">{title}</h3>
        <span className="rounded-full border border-stone-300 bg-white px-2.5 py-1 text-xs font-semibold text-stone-500">
          Planned
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-stone-600">{description}</p>
      <p className="mt-2 text-xs leading-5 text-stone-500">{reason}</p>
      <button
        type="button"
        disabled
        aria-disabled="true"
        className="mt-4 cursor-not-allowed rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs font-semibold text-stone-400"
      >
        Not available yet
      </button>
    </div>
  )
}
