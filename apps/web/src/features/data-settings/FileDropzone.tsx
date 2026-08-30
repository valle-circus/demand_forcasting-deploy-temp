import { Upload } from 'lucide-react'
import { useId, useState } from 'react'

import { formatBytes } from '@/lib/formatting'

interface FileDropzoneProps {
  accept: string
  multiple: boolean
  disabled: boolean
  fileDescription: string
  files: File[]
  onFilesSelected: (files: File[]) => void
}

/** Extension only. The real check happens on the server. */
function hasAcceptedExtension(file: File, accept: string): boolean {
  return accept
    .split(',')
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean)
    .some((suffix) => file.name.toLowerCase().endsWith(suffix))
}

/**
 * Drag-and-drop over a real file input, so it works by keyboard and with
 * assistive technology rather than by pointer alone.
 */
export function FileDropzone({
  accept,
  multiple,
  disabled,
  fileDescription,
  files,
  onFilesSelected,
}: FileDropzoneProps) {
  const inputId = useId()
  const [dragging, setDragging] = useState(false)
  const [wrongExtension, setWrongExtension] = useState(false)

  function selectFiles(incoming: FileList | null) {
    if (incoming === null || incoming.length === 0) {
      return
    }
    const selected = Array.from(incoming).slice(0, multiple ? undefined : 1)
    setWrongExtension(
      selected.some((file) => !hasAcceptedExtension(file, accept)),
    )
    onFilesSelected(selected)
  }

  return (
    <div>
      <label
        htmlFor={inputId}
        onDragOver={(event) => {
          if (disabled) return
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => {
          setDragging(false)
        }}
        onDrop={(event) => {
          if (disabled) return
          event.preventDefault()
          setDragging(false)
          selectFiles(event.dataTransfer.files)
        }}
        className={[
          'flex cursor-pointer items-center gap-2.5 rounded-md border border-dashed px-3 py-3 text-xs transition-colors',
          'focus-within:ring-2 focus-within:ring-ring focus-within:outline-none',
          disabled
            ? 'cursor-not-allowed border-border text-faint'
            : dragging
              ? 'border-primary bg-accent-soft text-accent-text'
              : 'border-border-strong text-muted-foreground hover:bg-surface',
        ].join(' ')}
      >
        <Upload aria-hidden="true" className="size-4 shrink-0" />
        <span>
          {multiple ? 'Choose files' : 'Choose a file'} or drop {fileDescription}
        </span>
        <input
          id={inputId}
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          className="sr-only"
          onChange={(event) => {
            selectFiles(event.target.files)
          }}
        />
      </label>

      {files.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs tabular">
          {files.map((file) => (
            <li key={`${file.name}-${String(file.size)}`} className="truncate">
              {file.name}
              <span className="text-muted-foreground">
                {' '}
                · {formatBytes(file.size)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {wrongExtension && (
        <p className="mt-2 text-xs text-warning">
          That does not look like {accept}. Upload to check it properly.
        </p>
      )}
    </div>
  )
}
