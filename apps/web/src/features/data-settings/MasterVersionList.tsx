import { useState } from 'react'

import { ConfirmDialog } from '../../components/ConfirmDialog'
import { StatusBadge } from '../../components/StatusBadge'
import { activateMasterVersion } from '../../lib/apiClient'
import { errorMessage } from '../../lib/errors'
import { formatDateTime } from '../../lib/formatting'
import type { MasterDataVersion } from '../../lib/types'
import { useMutation } from '../../lib/useMutation'

interface MasterVersionListProps {
  versions: MasterDataVersion[]
  timeZone: string
  onActivated: () => void
}

function versionTone(status: MasterDataVersion['status']) {
  if (status === 'active') {
    return { tone: 'ready' as const, label: 'Active' }
  }
  if (status === 'draft') {
    return { tone: 'neutral' as const, label: 'Draft' }
  }
  return { tone: 'neutral' as const, label: 'Archived' }
}

/**
 * Master-data versions and the explicit activation step.
 *
 * Importing a master workbook only ever creates a draft. Activation is
 * separate and deliberate because it changes what every other page reads — the
 * item set the planning workbook validates against, the locations that exist,
 * and the policies every recommendation is derived from.
 */
export function MasterVersionList({
  versions,
  timeZone,
  onActivated,
}: MasterVersionListProps) {
  const [pending, setPending] = useState<MasterDataVersion | null>(null)
  const active = versions.find((version) => version.status === 'active') ?? null

  const activation = useMutation(async (versionId: string) => {
    const result = await activateMasterVersion(versionId)
    onActivated()
    return result
  })

  return (
    <div className="rounded-xl border border-stone-200 bg-white">
      <header className="border-b border-stone-200 px-5 py-4">
        <h3 className="text-base font-semibold text-stone-950">
          Master-data versions
        </h3>
        <p className="mt-1 text-sm leading-6 text-stone-600">
          {active === null
            ? 'No version is active. Nothing else in the workspace can load until one is.'
            : `Active version: ${active.version_label}, activated ${formatDateTime(active.activated_at, timeZone)}.`}
        </p>
      </header>

      <div className="px-5 py-4">
        {activation.state.status === 'error' && (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs leading-5 text-rose-900"
          >
            <p className="font-semibold">Activation failed</p>
            <p className="mt-1">{errorMessage(activation.state.error)}</p>
          </div>
        )}

        {versions.length === 0 ? (
          <p className="text-sm text-stone-500">
            No versions yet. Import the master workbook above to create the
            first draft.
          </p>
        ) : (
          <ul className="space-y-2">
            {versions.map((version) => {
              const { tone, label } = versionTone(version.status)
              return (
                <li
                  key={version.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-stone-200 px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-stone-950">
                      {version.version_label}
                    </p>
                    <p className="mt-0.5 text-xs text-stone-500">
                      Created {formatDateTime(version.created_at, timeZone)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge tone={tone} label={label} />
                    {version.status === 'draft' && (
                      <button
                        type="button"
                        onClick={() => {
                          setPending(version)
                        }}
                        disabled={activation.isPending}
                        className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-semibold text-stone-800 transition hover:bg-stone-50 focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:outline-none disabled:opacity-50"
                      >
                        Activate
                      </button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {pending !== null && (
        <ConfirmDialog
          title={`Activate ${pending.version_label}?`}
          busy={activation.isPending}
          confirmLabel="Activate"
          body={
            <>
              <p>
                This becomes the master data every page reads: the item set, the
                locations, and the policies behind every recommendation.
              </p>
              <p className="mt-2">
                {active === null
                  ? 'No version is currently active.'
                  : `${active.version_label} will be replaced and can no longer be edited.`}
              </p>
              <p className="mt-2">
                Existing planning runs keep the version they were calculated
                with, so past results stay reproducible.
              </p>
            </>
          }
          onCancel={() => {
            setPending(null)
          }}
          onConfirm={() => {
            void activation.mutate(pending.id).then(() => {
              setPending(null)
            })
          }}
        />
      )}
    </div>
  )
}
