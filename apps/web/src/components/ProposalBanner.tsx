/**
 * Persistent, non-dismissible.
 *
 * Nothing in this application places, approves, sends, or tracks a supplier
 * order, and every quantity it shows is a proposal awaiting maintainer
 * approval. That must be true on every screen, not only on the pages that
 * happen to show recommendations — so this lives in the shell and has no
 * close control by design.
 */
export function ProposalBanner() {
  return (
    <div className="border-b border-amber-300 bg-amber-100 px-4 py-2 text-center text-xs font-medium text-amber-950 sm:px-6">
      <span aria-hidden="true" className="mr-1.5">
        ⚑
      </span>
      Proposals only — nothing here places, approves, or sends a supplier order.
    </div>
  )
}
