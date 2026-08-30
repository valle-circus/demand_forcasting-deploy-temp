export function BrandMark({ tone = 'dark' }: { tone?: 'dark' | 'light' }) {
  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="grid size-6 place-items-center rounded-md bg-primary text-[10px] font-semibold text-primary-foreground"
      >
        P2
      </span>
      <span
        className={`text-sm font-medium ${
          tone === 'dark' ? 'text-foreground' : 'text-white'
        }`}
      >
        Supply planning
      </span>
    </div>
  )
}
