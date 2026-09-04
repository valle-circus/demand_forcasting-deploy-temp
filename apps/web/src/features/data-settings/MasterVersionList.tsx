import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/formatting'
import type { MasterDataVersion } from '@/lib/types'

interface MasterVersionListProps {
  versions: MasterDataVersion[]
  timeZone: string
  onActivate: (version: MasterDataVersion) => void
  activating: boolean
}

/**
 * The audit and replacement surface for master-data versions.
 *
 * Activating a freshly imported draft happens inside step 1, where the upload
 * that produced it is. This list exists to see the history and to switch back
 * to an older version — not as the only route to continue the first-run
 * sequence, which is how it was easy to miss.
 */
export function MasterVersionList({
  versions,
  timeZone,
  onActivate,
  activating,
}: MasterVersionListProps) {
  if (versions.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No versions yet. Import the master workbook in step 1.
      </p>
    )
  }

  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-card">
      {versions.map((version) => {
        const active = version.status === 'active'
        return (
          <li
            key={version.id}
            className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">
                {version.version_label}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground tabular">
                {active && version.activated_at !== null
                  ? `Active since ${formatDateTime(version.activated_at, timeZone)}`
                  : formatDateTime(version.created_at, timeZone)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge
                tone={active ? 'ready' : 'neutral'}
                label={active ? 'Active' : 'Draft'}
              />
              {!active && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={activating}
                  onClick={() => {
                    onActivate(version)
                  }}
                >
                  Activate
                </Button>
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
