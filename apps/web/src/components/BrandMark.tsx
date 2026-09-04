/**
 * The product mark.
 *
 * Deliberately a plain accent tile rather than a glyph: the mark used to read
 * "P2", the internal name for this delivery phase, which means nothing to
 * anyone using the tool.
 */
export function BrandMark({ tone = 'dark' }: { tone?: 'dark' | 'light' }) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className="size-6 shrink-0 rounded-md bg-primary"
      />
      <span
        className={`text-sm font-semibold tracking-tight ${
          tone === 'dark' ? 'text-foreground' : 'text-white'
        }`}
      >
        Supply planning
      </span>
    </div>
  )
}
