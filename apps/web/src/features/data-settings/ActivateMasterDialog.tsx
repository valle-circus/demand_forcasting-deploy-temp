import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { MasterDataVersion } from '@/lib/types'

interface ActivateMasterDialogProps {
  version: MasterDataVersion
  /** The version being replaced, if one is currently active. */
  replacing: MasterDataVersion | null
  pending: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Activation is confirmed because it is not reversible in place: it changes
 * the item set, locations and rules every other page reads from.
 */
export function ActivateMasterDialog({
  version,
  replacing,
  pending,
  onConfirm,
  onCancel,
}: ActivateMasterDialogProps) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) {
          onCancel()
        }
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Activate {version.version_label}?</DialogTitle>
          <DialogDescription>
            {replacing === null
              ? 'This becomes the item set, locations and rules every page uses.'
              : `This replaces ${replacing.version_label}. Existing runs keep the version they used.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel} disabled={pending}>
            Cancel
          </Button>
          <Button size="lg" onClick={onConfirm} disabled={pending}>
            {pending ? 'Activating' : 'Activate'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
