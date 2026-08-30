import { NotBuiltYet } from '@/components/NotBuiltYet'

export function OverviewPage() {
  return (
    <div className="mx-auto max-w-[1280px] space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
      <NotBuiltYet summary="Readiness and risk across all locations, with the one thing that needs attention first." />
    </div>
  )
}
