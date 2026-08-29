import { fetchReadiness } from '../lib/apiClient'
import { errorMessage } from '../lib/errors'
import { useApiResource } from '../lib/useApiResource'

type Tone = 'ready' | 'warning' | 'error' | 'pending'

const toneDot: Record<Tone, string> = {
  ready: 'bg-emerald-500',
  warning: 'bg-amber-500',
  error: 'bg-rose-500',
  pending: 'bg-stone-400',
}

interface Presentation {
  tone: Tone
  label: string
  detail: string
}

/**
 * A compact, non-distracting dependency indicator, per the brief.
 *
 * It keeps three outcomes visibly distinct, because they need different
 * responses: the API is fine, the API is up but its database is not, and the
 * API cannot be reached at all.
 */
export function ApiStatusLine({ variant = 'light' }: { variant?: 'light' | 'dark' }) {
  const { state } = useApiResource((signal) => fetchReadiness(signal), [])

  let presentation: Presentation
  if (state.status === 'loading' || state.status === 'idle') {
    presentation = {
      tone: 'pending',
      label: 'Checking API',
      detail: 'Contacting the planning API.',
    }
  } else if (state.status === 'error') {
    presentation = {
      tone: 'error',
      label: 'API unreachable',
      detail: errorMessage(state.error),
    }
  } else {
    const { supabase, environment } = state.data
    presentation =
      supabase.status === 'ready'
        ? { tone: 'ready', label: `API ready · ${environment}`, detail: supabase.message }
        : {
            tone: supabase.status === 'unavailable' ? 'error' : 'warning',
            label:
              supabase.status === 'unavailable'
                ? 'Database unavailable'
                : 'Database not configured',
            detail: supabase.message,
          }
  }

  const textClass = variant === 'dark' ? 'text-stone-400' : 'text-stone-500'

  return (
    <p className={`flex items-start gap-2 text-xs leading-5 ${textClass}`}>
      <span
        aria-hidden="true"
        className={`mt-1.5 size-1.5 shrink-0 rounded-full ${toneDot[presentation.tone]}`}
      />
      <span>
        {/* Text carries the status; the dot only reinforces it. */}
        <span className="font-medium">{presentation.label}</span>
        <span className="sr-only">. </span>
        <span className="block">{presentation.detail}</span>
      </span>
    </p>
  )
}
