import { Info } from 'lucide-react'

/**
 * Persistent and undismissable.
 *
 * Nothing in this application places, approves, sends or tracks a supplier
 * order, and every quantity it shows is a proposal. That has to be true on
 * every screen, not only the ones showing recommendations.
 */
export function ProposalBanner() {
  return (
    <div className="flex items-center justify-center gap-1.5 border-b border-border bg-surface px-4 py-1.5 text-xs text-muted-foreground">
      <Info aria-hidden="true" className="size-3.5 shrink-0" />
      Proposals only — nothing here orders anything.
    </div>
  )
}
