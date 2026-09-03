import { fetchReadiness } from '@/lib/apiClient'
import { resourceKeys } from '@/lib/resourceCache'
import { useApiResource } from '@/lib/useApiResource'

const DOT = {
  ready: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-danger',
  pending: 'bg-faint',
} as const

/**
 * A compact dependency indicator. It keeps three outcomes distinct because
 * they need different responses: the API is fine, the API is up but its
 * database is not, and the API cannot be reached at all.
 */
export function ApiStatusLine() {
  const { state } = useApiResource(resourceKeys.readiness, (signal) =>
    fetchReadiness(signal),
  )

  let tone: keyof typeof DOT = 'pending'
  let label = 'Checking'

  if (state.status === 'error') {
    tone = 'error'
    label = 'API unreachable'
  } else if (state.status === 'success') {
    const { supabase, environment } = state.data
    if (supabase.status === 'ready') {
      tone = 'ready'
      label = environment
    } else {
      tone = supabase.status === 'unavailable' ? 'error' : 'warning'
      label =
        supabase.status === 'unavailable'
          ? 'Database unavailable'
          : 'Database not configured'
    }
  }

  return (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <span aria-hidden="true" className={`size-1.5 rounded-full ${DOT[tone]}`} />
      {label}
    </p>
  )
}
