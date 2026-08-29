import { useId, useState } from 'react'

import { formatBytes } from '../../lib/formatting'

interface FileDropzoneProps {
  accept: string
  multiple: boolean
  disabled: boolean
  fileDescription: string
  files: File[]
  onFilesSelected: (files: File[]) => void
}

/** Compares the file's extension only. Never presented as validation. */
function hasAcceptedExtension(file: File, accept: string): boolean {
  const allowed = accept
    .split(',')
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean)
  return allowed.some((suffix) => file.name.toLowerCase().endsWith(suffix))
}

/**
 * Drag-and-drop with a real file input behind it, so the control is operable
 * by keyboard and by assistive technology rather than by pointer only.
 *
 * The extension check here is a fast courtesy, and is labelled as such. All
 * actual validation happens in Python: the browser has no idea whether a
 * workbook has the right sheets, whether its items resolve, or whether its
 * horizon reaches far enough.
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
  const [extensionWarning, setExtensionWarning] = useState<string | null>(null)

  function selectFiles(incoming: FileList | null) {
    if (incoming === null || incoming.length === 0) {
      return
    }
    const selected = Array.from(incoming).slice(0, multiple ? undefined : 1)
    const wrongType = selected.filter(
      (file) => !hasAcceptedExtension(file, accept),
    )
    setExtensionWarning(
      wrongType.length === 0
        ? null
        : `${wrongType.map((file) => file.name).join(', ')} does not look like a ${accept} file.`,
    )
    onFilesSelected(selected)
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          if (disabled) {
            return
          }
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => {
          setDragging(false)
        }}
        onDrop={(event) => {
          if (disabled) {
            return
          }
          event.preventDefault()
          setDragging(false)
          selectFiles(event.dataTransfer.files)
        }}
        className={[
          'rounded-lg border-2 border-dashed p-4 text-center transition',
          disabled
            ? 'border-stone-200 bg-stone-50'
            : dragging
              ? 'border-lime-500 bg-lime-50'
              : 'border-stone-300 bg-white',
        ].join(' ')}
      >
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
        <label
          htmlFor={inputId}
          className={[
            'inline-flex cursor-pointer rounded-lg border px-3 py-1.5 text-sm font-semibold transition',
            'focus-within:ring-2 focus-within:ring-lime-600',
            disabled
              ? 'cursor-not-allowed border-stone-200 text-stone-400'
              : 'border-stone-300 text-stone-800 hover:bg-stone-50',
          ].join(' ')}
        >
          {multiple ? 'Choose files' : 'Choose file'}
        </label>
        <p className="mt-2 text-xs text-stone-500">
          {disabled ? 'Upload unavailable' : 'or drop here'} · {fileDescription}
        </p>
      </div>

      {files.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-stone-600">
          {files.map((file) => (
            <li key={`${file.name}-${String(file.size)}`}>
              <span className="font-medium text-stone-800">{file.name}</span> ·{' '}
              {formatBytes(file.size)}
            </li>
          ))}
        </ul>
      )}

      {extensionWarning !== null && (
        <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {extensionWarning} This is only a quick check on the file name — the
          file is still validated properly by the planning service when you
          upload it.
        </p>
      )}
    </div>
  )
}
