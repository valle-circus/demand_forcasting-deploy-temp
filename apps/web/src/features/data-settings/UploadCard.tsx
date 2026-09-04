import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'

import { FreshnessStamp } from '@/components/FreshnessStamp'
import { ImportStatusBadge, StatusBadge } from '@/components/StatusBadge'
import type { StatusTone } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import type { UploadOptions } from '@/lib/apiClient'
import { errorMessage, isApiError } from '@/lib/errors'
import { formatCount, formatDate, formatShortId } from '@/lib/formatting'
import type { SourceImport } from '@/lib/types'
import { FileDropzone } from './FileDropzone'
import { ImportIssueList } from './ImportIssueList'
import type { DatasetDefinition, Prerequisite } from './datasets'

type UploadPhase =
  | { kind: 'idle' }
  | { kind: 'uploading'; progress: number | null }
  | { kind: 'validating' }
  | { kind: 'done'; result: SourceImport; alreadyImported: boolean }
  | { kind: 'failed'; error: Error }

interface UploadCardProps {
  definition: DatasetDefinition
  prerequisite: Prerequisite
  current: SourceImport | null
  history: SourceImport[]
  timeZone: string
  scopeLabel: string
  knownImportIds: ReadonlySet<string>
  upload: (files: File[], options: UploadOptions) => Promise<SourceImport>
  onImported: () => void
  /** Replaces the derived header status, e.g. "Draft ready" for step 1. */
  statusOverride?: { tone: StatusTone; label: string }
  /**
   * Whether this is the step the maintainer should do next. Only that card's
   * action gets the accent: four accent buttons on one page means the page has
   * no primary action at all.
   */
  isNextStep: boolean
  /** Extra input this dataset needs, e.g. the purchase-order cutoff. */
  extraControls?: ReactNode
  /**
   * Rendered directly beneath the upload result. Step 1 puts its
   * "Activate master data and continue" action here, so activation reads as
   * the completion of the step rather than as a separate task further down
   * the page.
   */
  completionSlot?: ReactNode
}

/** Send the maintainer back to the step that unblocks this one. */
function goToStep(step: number): void {
  const card = document.getElementById(`step-${String(step)}`)
  card?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  card?.querySelector<HTMLElement>('label, button')?.focus({
    preventScroll: true,
  })
}

function rejectedImportId(error: Error): string | null {
  if (!isApiError(error)) {
    return null
  }
  const value = error.details.import_id
  return typeof value === 'string' ? value : null
}

export function UploadCard({
  definition,
  prerequisite,
  current,
  history,
  timeZone,
  scopeLabel,
  knownImportIds,
  upload,
  onImported,
  statusOverride,
  isNextStep,
  extraControls,
  completionSlot,
}: UploadCardProps) {
  const [files, setFiles] = useState<File[]>([])
  const [phase, setPhase] = useState<UploadPhase>({ kind: 'idle' })
  const [showDetails, setShowDetails] = useState(false)

  const busy = phase.kind === 'uploading' || phase.kind === 'validating'
  const issues = current?.validation_issues ?? []

  async function handleUpload() {
    if (files.length === 0 || busy) {
      return
    }
    setPhase({ kind: 'uploading', progress: 0 })
    try {
      const result = await upload(files, {
        onProgress: (fraction) => {
          // Once the bytes are sent the wait is server-side parsing, which is
          // a different thing and worth naming.
          setPhase(
            fraction !== null && fraction >= 1
              ? { kind: 'validating' }
              : { kind: 'uploading', progress: fraction },
          )
        },
      })
      setFiles([])
      setPhase({
        kind: 'done',
        result,
        alreadyImported: knownImportIds.has(result.id),
      })
      onImported()
    } catch (error) {
      setPhase({
        kind: 'failed',
        error: error instanceof Error ? error : new Error(String(error)),
      })
      // A rejected import is persisted too, so history should still refresh.
      onImported()
    }
  }

  return (
    <section
      id={`step-${String(definition.step)}`}
      aria-labelledby={`step-${String(definition.step)}-title`}
      className="scroll-mt-24 rounded-xl border border-border bg-card"
    >
      <header className="flex items-start justify-between gap-3 px-5 pt-5">
        <div className="flex min-w-0 items-start gap-3">
          {/* A plain ordinal, weighted rather than filled. A tinted circle here
              sat next to the tinted status pill on the same line, and two chip
              shapes in one card header is what makes a page look busy. */}
          <span
            aria-hidden="true"
            className={`w-3 shrink-0 pt-0.5 text-[13px] tabular ${
              isNextStep
                ? 'font-semibold text-foreground'
                : 'font-medium text-faint'
            }`}
          >
            {definition.step}
          </span>
          <div className="min-w-0">
            <h3
              id={`step-${String(definition.step)}-title`}
              className="text-base leading-tight font-semibold"
            >
              {definition.title}
            </h3>
            <p className="mt-0.5 text-xs text-muted-foreground">{scopeLabel}</p>
          </div>
        </div>
        {statusOverride ? (
          <StatusBadge {...statusOverride} />
        ) : current === null ? (
          <StatusBadge tone="neutral" label="Not imported" />
        ) : (
          <ImportStatusBadge status={current.status} />
        )}
      </header>

      <div className="space-y-4 p-5">
        {prerequisite.blocked ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-surface px-3 py-2.5">
            <p className="text-xs text-muted-foreground">
              {prerequisite.reason}
            </p>
            {prerequisite.unblockedByStep !== undefined && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  goToStep(prerequisite.unblockedByStep ?? 1)
                }}
              >
                Go to step {prerequisite.unblockedByStep}
              </Button>
            )}
          </div>
        ) : (
          <>
            {extraControls}

            {definition.uploadInstruction !== undefined && (
              <div className="rounded-md border border-border bg-surface px-3 py-2.5">
                <p className="text-xs font-medium text-foreground">
                  Select all PDFs together
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {definition.uploadInstruction}
                </p>
              </div>
            )}

            <FileDropzone
              accept={definition.accept}
              multiple={definition.multiple}
              disabled={busy}
              fileDescription={definition.fileDescription}
              files={files}
              onFilesSelected={(selected) => {
                setFiles(selected)
                setPhase({ kind: 'idle' })
              }}
            />

            {/* The action sits directly under the file it acts on, and only
                the next step in the sequence spends the accent. */}
            <Button
              size="lg"
              variant={isNextStep ? 'default' : 'outline'}
              className="w-full"
              disabled={busy || files.length === 0}
              onClick={() => void handleUpload()}
            >
              {phase.kind === 'uploading'
                ? `Uploading${
                    phase.progress === null
                      ? ''
                      : ` ${String(Math.round(phase.progress * 100))}%`
                  }`
                : phase.kind === 'validating'
                  ? 'Checking the file'
                  : 'Upload and check'}
            </Button>

            <p aria-live="polite" className="sr-only">
              {phase.kind === 'uploading' && 'Uploading.'}
              {phase.kind === 'validating' && 'Checking the file.'}
              {phase.kind === 'done' && 'Import finished.'}
              {phase.kind === 'failed' && 'Import rejected.'}
            </p>

            {phase.kind === 'done' && (
              <p
                className={`rounded-md px-3 py-2 text-xs ${
                  phase.result.status === 'accepted_with_warnings'
                    ? 'bg-surface text-warning'
                    : 'bg-accent-soft text-accent-text'
                }`}
              >
                {phase.alreadyImported
                  ? 'Already imported. The existing version was kept.'
                  : phase.result.status === 'accepted_with_warnings'
                    ? 'Accepted, with warnings below.'
                    : 'Accepted.'}
              </p>
            )}

            {phase.kind === 'failed' && (
              <div
                role="alert"
                className="rounded-md bg-surface px-3 py-2 text-xs text-danger"
              >
                <p>{errorMessage(phase.error)}</p>
                {isApiError(phase.error) &&
                  phase.error.fieldIssues.map((issue) => (
                    <p key={issue.field} className="mt-1">
                      {issue.field}: {issue.message}
                    </p>
                  ))}
                <p className="mt-1 text-muted-foreground">
                  Nothing was changed.
                  {rejectedImportId(phase.error) !== null &&
                    ` Recorded as ${formatShortId(rejectedImportId(phase.error))}.`}
                </p>
              </div>
            )}

            {completionSlot}
          </>
        )}

        {/* One line about what is in use; everything else is behind Details. */}
        {current !== null && (
          <div className="border-t border-border pt-4">
            <p className="text-xs text-muted-foreground tabular">
              {current.source_version} · {formatCount(current.record_count, 'record')}
            </p>

            <button
              type="button"
              onClick={() => {
                setShowDetails((open) => !open)
              }}
              aria-expanded={showDetails}
              className="mt-2 -ml-1 inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <ChevronRight
                aria-hidden="true"
                className={`size-3.5 transition-transform duration-150 ${
                  showDetails ? 'rotate-90' : ''
                }`}
              />
              Details
            </button>

            {showDetails && (
              <div className="mt-3 space-y-3">
                <FreshnessStamp
                  sourceAt={current.source_as_of_at}
                  importedAt={current.created_at}
                  timeZone={timeZone}
                  sourceLabel={definition.sourceTimeLabel}
                />

                {current.coverage_start_date !== null && (
                  <p className="text-xs tabular">
                    <span className="text-muted-foreground">Covers </span>
                    {formatDate(current.coverage_start_date)} –{' '}
                    {formatDate(current.coverage_end_date)}
                  </p>
                )}

                <p className="text-xs break-words text-muted-foreground">
                  {current.file_names.join(', ')}
                </p>

                {issues.length > 0 && <ImportIssueList issues={issues} />}

                {history.length > 1 && (
                  <ul className="space-y-1 border-t border-border pt-3">
                    {history.slice(0, 5).map((entry) => (
                      <li
                        key={entry.id}
                        className="flex items-center justify-between gap-2 text-xs"
                      >
                        <span className="truncate text-muted-foreground">
                          {entry.file_names.join(', ') || entry.source_version}
                        </span>
                        <ImportStatusBadge status={entry.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
