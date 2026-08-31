import { StatusBadge } from '@/components/StatusBadge'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { formatDate, formatDecimalUnits, formatGrams } from '@/lib/formatting'
import type {
  PlanningException,
  PlanningLine,
  PlanningLineExplanation,
} from '@/lib/types'
import {
  bindingConstraintLabel,
  capBasisLabel,
  constraintStatusPresentation,
  derivationSteps,
  exceptionsForLine,
  provenanceLabel,
  shelfLifeEvidence,
} from './planning'
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
 * comes from the engine's own `binding_constraint`, `constraint_status` and
 * exceptions, all quoted rather than inferred.
 */
export function DerivationDrawer({
  line,
  exceptions,
  explanation,
  itemName,
  onClose,
}: {
  line: PlanningLine | null
  exceptions: readonly PlanningException[]
  explanation: PlanningLineExplanation | null
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

              <ConstraintSummary line={line} />
              <ShelfLifeEvidencePanel line={line} />
              <ExceptionList
                exceptions={exceptionsForLine(exceptions, line.planning_line_id)}
              />
              {explanation !== null && <PolicyContext explanation={explanation} />}

              <dl className="mt-5 space-y-1.5 border-t border-border pt-4 text-xs">
                <Row label="Order on">{formatDate(line.order_date)}</Row>
                <Row label="Expected">
                  {formatDate(line.expected_delivery_date)}
                </Row>
                <Row label="Protects until">
                  {formatDate(line.coverage_end_date)}
                </Row>
              </dl>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function Row({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="tabular">{children}</dd>
    </div>
  )
}

/**
 * Whether a purchasable quantity exists at all.
 *
 * A hard cap can force a smaller multiple than the need, or leave nothing safe
 * to order. Both are the engine's verdict, shown rather than worked around —
 * React must never invent a proposal the backend declined to make.
 */
function ConstraintSummary({ line }: { line: PlanningLine }) {
  const status = constraintStatusPresentation(line.constraint_status)
  const limited = line.binding_constraint !== 'none'

  if (!limited && line.constraint_status === 'feasible') {
    return null
  }

  return (
    <div className="mt-4 border-t border-border pt-4">
      <StatusBadge tone={status.tone} label={status.label} />
      <p className="mt-2 text-xs text-muted-foreground">
        {bindingConstraintLabel(line.binding_constraint)}
        {line.rounding_direction !== 'none' &&
          `. Pack sizes rounded the quantity ${line.rounding_direction}.`}
      </p>
      {line.constraint_status === 'no_safe_positive_order' && (
        <p className="mt-1 text-xs text-danger">
          No quantity fits under the limit, so nothing is proposed. This needs a
          manual decision.
        </p>
      )}
    </div>
  )
}

/**
 * Whether the proposed delivery can realistically be used before it expires.
 *
 * The warnings here are rendered inline, never hidden behind a hover: an
 * estimate presented as a certainty, or a gap in forecast coverage, is exactly
 * the kind of thing someone must not be able to miss.
 */
function ShelfLifeEvidencePanel({ line }: { line: PlanningLine }) {
  const evidence = shelfLifeEvidence(line)

  if (evidence.expiryDate === null && evidence.basis === 'not_configured') {
    return null
  }

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="text-xs font-medium">Shelf life</p>
      <dl className="mt-2 space-y-1.5 text-xs">
        <Row label="Estimated expiry">{formatDate(evidence.expiryDate)}</Row>
        <Row label="Left over at expiry">
          {formatGrams(evidence.residualAtExpiryG)}
        </Row>
      </dl>

      <p className="mt-2 text-xs text-muted-foreground">
        {capBasisLabel(evidence.basis)}.
        {evidence.basis === 'policy_approximation' &&
          ' It is an estimate, not the actual date on the delivered goods.'}
      </p>

      {evidence.coverageIncomplete && (
        <p className="mt-1 text-xs text-warning">
          The forecast does not reach that date, so this check is incomplete.
        </p>
      )}

      {evidence.residualAtExpiryG !== null && evidence.residualAtExpiryG > 0 && (
        <p className="mt-1 text-xs text-warning">
          Some of this delivery is projected to still be there when it expires.
        </p>
      )}
    </div>
  )
}

/** The engine's own notes about this line, quoted rather than inferred. */
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

/**
 * The active policy behind this line, joined by the backend from the master
 * version the run actually used — so the numbers above can be traced to a rule
 * rather than guessed at from the dates.
 */
function PolicyContext({
  explanation,
}: {
  explanation: PlanningLineExplanation
}) {
  const { item, planning_policy: policy, delivery_rule: rule } = explanation

  if (item === null && policy === null && rule === null) {
    return null
  }

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="text-xs font-medium">Rules used</p>
      <dl className="mt-2 space-y-1.5 text-xs">
        {policy?.lead_time_calendar_days !== null &&
          policy?.lead_time_calendar_days !== undefined && (
            <Row label="Lead time">{policy.lead_time_calendar_days} days</Row>
          )}
        {rule?.review_period_days !== null &&
          rule?.review_period_days !== undefined && (
            <Row label="Reviewed every">{rule.review_period_days} days</Row>
          )}
        {item?.shelf_life_days !== null && item?.shelf_life_days !== undefined && (
          <Row label="Shelf life">{item.shelf_life_days} days</Row>
        )}
        {item?.max_cover_days !== null && item?.max_cover_days !== undefined && (
          <Row label="Max cover">
            {formatDecimalUnits(item.max_cover_days)} days
          </Row>
        )}
        {item !== null && (
          <Row label="Storage">{item.storage_class}</Row>
        )}
        {policy?.order_unit !== null && policy?.order_unit !== undefined && (
          <Row label="Ordered in">{policy.order_unit}</Row>
        )}
      </dl>
    </div>
  )
}
