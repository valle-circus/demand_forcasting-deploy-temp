# Location planning — implementation notes

## The rule this feature exists to hold

`planning.ts` reads fields. It does not add, subtract, cap, or round anything.

Where the UI needs to say *why* a quantity came out as it did — a cap bound, an
order was raised to a supplier minimum, a case rounding applied — it quotes the
engine's `planning_exceptions` for that line rather than comparing numbers in
the browser. Comparing `capped_order_g` against `raw_order_g` to infer "the
max-cover cap bound here" would be reimplementing the engine's decision in
TypeScript, which is exactly what the handover forbids.

`planning.test.ts` pins this with a line whose fields are mutually inconsistent
(`gross × yield ≠ adjusted`). The drawer must still show the stored values. If
those numbers ever disagree in production, the bug is in the engine and it
should be visible, not quietly reconciled on screen.

## Why the projection chart is hand-drawn SVG

The `circus-ui` skill specifies Recharts via shadcn's `chart` for charts. This
one is a single series with no legend, no categorical colour, and no axis
labels beyond the two endpoints — the only thing that must be unmissable is
where the line crosses zero, because that is the stockout. Pulling in the
charting stack and following the `dataviz` skill for that was disproportionate.

Revisit if this ever needs more than one series, a real axis, or a tooltip.

## Data loading

- `planning-status` drives everything: readiness, blockers, freshness, and
  which run is the latest.
- The run is fetched separately by id. It is a large payload — every item
  across every horizon day — so the projection chart renders only the opened
  item's rows.
- Purchase orders load only when their tab is open. A maintainer may never
  look at it, and it is a separate request.
- A freshly computed run is held in local state and preferred over the
  persisted read until the next refetch, so the page does not flash empty
  between the POST returning and the status refetch landing.
