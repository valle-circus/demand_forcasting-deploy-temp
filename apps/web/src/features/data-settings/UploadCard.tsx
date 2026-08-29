import { useState } from 'react'
import type { ReactNode } from 'react'

import { FreshnessStamp } from '../../components/FreshnessStamp'
import { ImportStatusBadge, StatusBadge } from '../../components/StatusBadge'
import type { UploadOptions } from '../../lib/apiClient'
import { ApiError, errorMessage, isApiError } from '../../lib/errors'
import { formatCount, formatDate, formatShortId } from '../../lib/formatting'
import type { SourceImport, ValidationIssue } from '../../lib/types'
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
  /** The newest accepted import for this dataset and scope. */
  current: SourceImport | null
  history: SourceImport[]
  timeZone: string
  scopeLabel: string
  /** Ids already known before this upload, used to recognise a duplicate. */
  knownImportIds: ReadonlySet<string>
  upload: (files: File[], options: UploadOptions) => Promise<SourceImport>
  onImported: () => void
  /** Extra inputs this dataset needs, e.g. the purchase-order cutoff. */
  extraControls?: ReactNode
}

/** A 422 carries the rejected import's id, so the failure is still auditable. */
function rejectedImportId(error: Error): string | null {
  if (!isApiError(error)) {
    return null
  }
  const value = (error as ApiError).details.import_id
  return typeof value === 'string' ? value : null
}

function Detail({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-stone-500">{label}</dt>
      <dd className="mt-0.5 text-xs text-stone-800">{value}</dd>
    </div>
  )
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
  extraControls,
}: UploadCardProps) {
  const [files, setFiles] = useState<File[]>([])
  const [phase, setPhase] = useState<UploadPhase>({ kind: 'idle' })
  const [showIssues, setShowIssues] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  const busy = phase.kind === 'uploading' || phase.kind === 'validating'
  const disabled = prerequisite.blocked || busy

  async function handleUpload() {
    if (files.length === 0 || busy) {
      return
    }
    setPhase({ kind: 'uploading', progress: 0 })
    try {
      const result = await upload(files, {
        onProgress: (fraction) => {
          // Once the bytes are sent, the wait is server-side parsing and
          // validation — a different thing, and worth saying so.
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

  const issues: ValidationIssue[] = current?.validation_issues ?? []

  return (
    <section
      aria-labelledby={`dataset-${definition.key}`}
      className="flex flex-col rounded-xl border border-stone-200 bg-white"
    >
      <header className="border-b border-stone-200 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-wider text-stone-500 uppercase">
              Step {definition.step}
            </p>
            <h3
              id={`dataset-${definition.key}`}
              className="mt-1 text-base font-semibold text-stone-950"
            >
              {definition.title}
            </h3>
            <p className="mt-1 text-xs text-stone-500">{scopeLabel}</p>
          </div>
          {current === null ? (
            <StatusBadge tone="neutral" label="Not imported" />
          ) : (
            <ImportStatusBadge status={current.status} />
          )}
        </div>
        <p className="mt-3 text-sm leading-6 text-stone-600">
          {definition.purpose}
        </p>
      </header>

      <div className="flex-1 space-y-5 px-5 py-4">
        {prerequisite.blocked ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
            <p className="font-semibold">Not available yet</p>
            <p className="mt-1">{prerequisite.reason}</p>
            {prerequisite.unblockedByStep !== undefined && (
              <p className="mt-1">
                Complete step {prerequisite.unblockedByStep} first.
              </p>
            )}
          </div>
        ) : (
          <>
            {extraControls}

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

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void handleUpload()}
                disabled={disabled || files.length === 0}
                className="rounded-lg bg-lime-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-lime-700 focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-stone-300"
              >
                {busy ? 'Working…' : 'Upload and validate'}
              </button>

              {phase.kind === 'uploading' && (
                <StatusBadge
                  tone="running"
                  label="Uploading"
                  detail={
                    phase.progress === null
                      ? undefined
                      : `${String(Math.round(phase.progress * 100))}%`
                  }
                />
              )}
              {phase.kind === 'validating' && (
                <StatusBadge tone="running" label="Validating on the server" />
              )}
            </div>

            <p aria-live="polite" className="sr-only">
              {phase.kind === 'uploading' && 'Uploading file.'}
              {phase.kind === 'validating' && 'Validating on the server.'}
              {phase.kind === 'done' && 'Import finished.'}
              {phase.kind === 'failed' && 'Import failed.'}
            </p>

            {phase.kind === 'done' && (
              <div
                className={`rounded-lg border p-3 text-xs leading-5 ${
                  phase.result.status === 'accepted_with_warnings'
                    ? 'border-amber-300 bg-amber-50 text-amber-900'
                    : 'border-emerald-300 bg-emerald-50 text-emerald-900'
                }`}
              >
                <p className="font-semibold">
                  {phase.alreadyImported
                    ? 'This file was already imported'
                    : phase.result.status === 'accepted_with_warnings'
                      ? 'Accepted, with warnings to review'
                      : 'Accepted'}
                </p>
                <p className="mt-1">
                  {phase.alreadyImported
                    ? 'Its content matches an existing accepted import, so the existing version was kept rather than creating a duplicate.'
                    : definition.updateBehaviour}
                </p>
              </div>
            )}

            {phase.kind === 'failed' && (
              <div
                role="alert"
                className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs leading-5 text-rose-900"
              >
                <p className="font-semibold">Rejected — nothing was changed</p>
                <p className="mt-1">{errorMessage(phase.error)}</p>
                {isApiError(phase.error) &&
                  phase.error.fieldIssues.map((issue) => (
                    <p key={issue.field} className="mt-1">
                      <span className="font-medium">{issue.field}</span>:{' '}
                      {issue.message}
                    </p>
                  ))}
                {rejectedImportId(phase.error) !== null && (
                  <p className="mt-1 text-rose-800">
                    Recorded in history as{' '}
                    {formatShortId(rejectedImportId(phase.error))} so the attempt
                    stays auditable.
                  </p>
                )}
              </div>
            )}
          </>
        )}

        {/* Current accepted version */}
        <div className="border-t border-stone-200 pt-4">
          <h4 className="text-xs font-semibold tracking-wider text-stone-500 uppercase">
            Currently in use
          </h4>
          {current === null ? (
            <p className="mt-2 text-xs text-stone-500">
              Nothing accepted yet for this scope.
            </p>
          ) : (
            <>
              <div className="mt-2">
                <FreshnessStamp
                  sourceAt={current.source_as_of_at}
                  importedAt={current.created_at}
                  timeZone={timeZone}
                  sourceLabel={definition.sourceTimeLabel}
                />
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-3">
                <Detail label="Version" value={current.source_version} />
                <Detail
                  label="Records"
                  value={formatCount(current.record_count, 'record')}
                />
                <Detail
                  label="Coverage"
                  value={
                    current.coverage_start_date === null
                      ? 'not applicable'
                      : `${formatDate(current.coverage_start_date)} → ${formatDate(current.coverage_end_date)}`
                  }
                />
                <Detail
                  label="Files"
                  value={current.file_names.join(', ') || '—'}
                />
              </dl>

              {issues.length > 0 && (
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={() => {
                      setShowIssues((open) => !open)
                    }}
                    aria-expanded={showIssues}
                    className="text-xs font-semibold text-stone-700 underline underline-offset-2 hover:text-stone-950 focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:outline-none"
                  >
                    {showIssues ? 'Hide' : 'Review'}{' '}
                    {formatCount(issues.length, 'issue')}
                  </button>
                  {showIssues && (
                    <div className="mt-2">
                      <ImportIssueList issues={issues} />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Version history */}
        {history.length > 0 && (
          <div className="border-t border-stone-200 pt-4">
            <button
              type="button"
              onClick={() => {
                setShowHistory((open) => !open)
              }}
              aria-expanded={showHistory}
              className="text-xs font-semibold text-stone-700 underline underline-offset-2 hover:text-stone-950 focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:outline-none"
            >
              {showHistory ? 'Hide' : 'Show'} import history (
              {formatCount(history.length, 'entry', 'entries')})
            </button>
            {showHistory && (
              <ul className="mt-3 space-y-2">
                {history.map((entry) => (
                  <li
                    key={entry.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-stone-50 px-3 py-2 text-xs"
                  >
                    <span className="text-stone-700">
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

      <footer className="border-t border-stone-200 bg-stone-50 px-5 py-3">
        {/* The "uploading never runs planning" guarantee is stated once, at
            the top of the page. Repeating it on all four cards is noise. */}
        <p className="text-xs leading-5 text-stone-600">
          {definition.updateBehaviour}
        </p>
      </footer>
    </section>
  )
}
