export type DependencyStatus = 'ready' | 'not_configured' | 'unavailable'

export interface ReadinessResponse {
  status: 'ready' | 'degraded'
  service: string
  version: string
  environment: string
  supabase: {
    status: DependencyStatus
    message: string
  }
}

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
export const apiBaseUrl = configuredBaseUrl?.replace(/\/$/, '') ?? ''

export async function fetchReadiness(
  signal?: AbortSignal,
): Promise<ReadinessResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/readiness`, { signal })
  if (!response.ok) {
    throw new Error(`API readiness returned HTTP ${response.status}.`)
  }
  return (await response.json()) as ReadinessResponse
}
