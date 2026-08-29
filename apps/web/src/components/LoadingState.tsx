export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-xl border border-stone-200 bg-white p-6 text-sm text-stone-600 sm:p-8"
    >
      {label}
    </div>
  )
}
