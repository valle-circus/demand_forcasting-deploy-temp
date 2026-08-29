/**
 * An explicit placeholder for a page that has not been implemented yet.
 *
 * It exists so an unfinished page is unmistakably unfinished. It never renders
 * sample numbers, mock tables, or synthetic charts — a screen that looks
 * populated but is not connected is worse than an empty one.
 */
export function NotBuiltYet({
  workPackage,
  summary,
}: {
  workPackage: string
  summary: string
}) {
  return (
    <div className="rounded-xl border border-dashed border-stone-300 bg-white p-6 sm:p-8">
      <p className="text-xs font-semibold tracking-wider text-stone-500 uppercase">
        Not built yet · {workPackage}
      </p>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-600">{summary}</p>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-500">
        Nothing is shown here rather than placeholder numbers, so this page
        cannot be mistaken for connected data.
      </p>
    </div>
  )
}
