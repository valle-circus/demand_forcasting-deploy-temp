import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { formatDate, formatDecimalUnits, formatGrams } from '@/lib/formatting'
import type { PlanningException, PlanningLine } from '@/lib/types'
import { derivationSteps, exceptionsForLine, provenanceLabel } from './planning'
import type { DerivationStep } from './planning'

const PREFIX: Record<DerivationStep['kind'], string> = {
  value: '',
  add: '+',
  subtract: '−',
  total: '',
  limit: '',
}

function stepValue(step: DerivationStep): string {
  if (step.absent === true || step.value === null) {
    return 'none'
  }
  if (step.unit === 'factor') {
    return `×${formatDecimalUnits(step.value)}`
  }
  if (step.unit === 'units') {
    return formatDecimalUnits(step.value)
  }
  return formatGrams(step.value)
}

/**
 * How one proposed quantity was produced, in the order the engine applies it.
 *
 * Every number here is a stored field. The browser does not add, subtract or
 * cap anything, and it does not decide which constraint bound — that claim
 * comes from the engine's own exceptions, listed underneath.
 */
export function DerivationDrawer({
  line,
  exceptions,
  itemName,
  onClose,
}: {
  line: PlanningLine | null
  exceptions: readonly PlanningException[]
  itemName: string
  onClose: () => void
}) {
  return (
    <Sheet
      open={line !== null}
      onOpenChange={(open) => {
        if (!open) {
          onClose()
        }
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        {line !== null && (
          <>
            <SheetHeader>
              <SheetTitle>{itemName}</SheetTitle>
              <SheetDescription>
                How this proposal was calculated. Nothing here is an order.
              </SheetDescription>
            </SheetHeader>

            <div className="px-4 pb-6">
              <ol className="text-xs">
                {derivationSteps(line).map((step, index) => {
                  const isTotal = step.kind === 'total'
                  return (
                    <li
                      key={`${step.label}-${String(index)}`}
                      className={[
                        'flex items-baseline justify-between gap-4 py-1.5',
                        isTotal ? 'border-t border-border font-medium' : '',
                        step.absent === true ? 'text-faint' : '',
                      ].join(' ')}
                    >
                      <span className="flex items-baseline gap-1.5">
                        {step.label}
                        {step.provenance !== undefined && (
                          <span className="text-faint">
                            {provenanceLabel(step.provenance)}
                          </span>
                        )}
                      </span>
                      <span className="shrink-0 tabular">
                        {PREFIX[step.kind]}
                        {stepValue(step)}
                      </span>
                    </li>
                  )
                })}
              </ol>

              <ExceptionList
                exceptions={exceptionsForLine(exceptions, line.planning_line_id)}
              />

              <dl className="mt-5 space-y-1.5 border-t border-border pt-4 text-xs">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Order on</dt>
                  <dd className="tabular">{formatDate(line.order_date)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Expected</dt>
                  <dd className="tabular">
                    {formatDate(line.expected_delivery_date)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Covers</dt>
                  <dd className="tabular">{line.protection_days} days</dd>
                </div>
              </dl>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

/**
 * The engine's own notes about this line — a bound cap, an order inflated to a
 * minimum, a rounding step. Quoted rather than inferred.
 */
function ExceptionList({
  exceptions,
}: {
  exceptions: readonly PlanningException[]
}) {
  if (exceptions.length === 0) {
    return null
  }

  return (
    <ul className="mt-4 space-y-2 border-t border-border pt-4">
      {exceptions.map((exception) => (
        <li key={exception.exception_id} className="text-xs">
          <p
            className={
              exception.severity === 'blocker' ? 'text-danger' : 'text-warning'
            }
          >
            {exception.message}
          </p>
          <p className="mt-0.5 text-muted-foreground">{exception.remedy}</p>
        </li>
      ))}
    </ul>
  )
}
