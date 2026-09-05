export const RESOURCE_FRESH_TIME_MS = 10 * 60 * 1_000

export const resourceKeys = {
  readiness: 'system:readiness',
  overview: 'planning:overview',
  locations: 'planning:locations',
  imports: (datasetType = 'all', locationId = 'all') =>
    `imports:${datasetType}:${locationId}`,
  masterVersions: 'master:versions',
  planningStatus: (locationId: string) => `planning-status:${locationId}`,
  locationView: (locationId: string) => `location-view:${locationId}`,
  inventory: (locationId: string) => `inventory:${locationId}`,
  purchaseOrders: (locationId: string) => `purchase-orders:${locationId}`,
  planningRun: (runId: string) => `planning-run:${runId}`,
} as const

interface CacheEntry {
  hasData: boolean
  data: unknown
  fetchedAt: number
  invalidated: boolean
  error: Error | null
  inFlight: Promise<unknown> | null
  controller: AbortController | null
  revision: number
  listeners: Set<() => void>
}

export interface ResourceSnapshot<T> {
  hasData: boolean
  data: T | null
  fetchedAt: number | null
  invalidated: boolean
  error: Error | null
  isRefreshing: boolean
}

interface LoadResourceOptions<T> {
  key: string
  fetcher: (signal: AbortSignal) => Promise<T>
  staleTimeMs?: number
  force?: boolean
}

const entries = new Map<string, CacheEntry>()
let activeOwner = 'anonymous'

function ownedKey(key: string): string {
  return `${activeOwner}\u0000${key}`
}

/**
 * Partition every in-memory resource by the authenticated account. The API's
 * current contract resolves each account to exactly one default workspace, so
 * the user ID is also the browser-visible workspace ownership boundary.
 */
export function setResourceCacheOwner(userId: string | null): void {
  const nextOwner = userId ?? 'anonymous'
  if (nextOwner === activeOwner) {
    return
  }
  clearResourceCache()
  activeOwner = nextOwner
}

function cacheEntry(key: string): CacheEntry {
  const storageKey = ownedKey(key)
  const existing = entries.get(storageKey)
  if (existing !== undefined) {
    return existing
  }
  const created: CacheEntry = {
    hasData: false,
    data: undefined,
    fetchedAt: 0,
    invalidated: false,
    error: null,
    inFlight: null,
    controller: null,
    revision: 0,
    listeners: new Set(),
  }
  entries.set(storageKey, created)
  return created
}

function notify(entry: CacheEntry): void {
  for (const listener of entry.listeners) {
    listener()
  }
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error))
}

export function readResource<T>(key: string): ResourceSnapshot<T> {
  const entry = cacheEntry(key)
  return {
    hasData: entry.hasData,
    data: entry.hasData ? (entry.data as T) : null,
    fetchedAt: entry.hasData ? entry.fetchedAt : null,
    invalidated: entry.invalidated,
    error: entry.error,
    isRefreshing: entry.inFlight !== null,
  }
}

export function subscribeResource(key: string, listener: () => void): () => void {
  const entry = cacheEntry(key)
  entry.listeners.add(listener)
  return () => {
    entry.listeners.delete(listener)
  }
}

export function loadResource<T>({
  key,
  fetcher,
  staleTimeMs = RESOURCE_FRESH_TIME_MS,
  force = false,
}: LoadResourceOptions<T>): Promise<T> {
  const entry = cacheEntry(key)
  if (entry.inFlight !== null) {
    return entry.inFlight as Promise<T>
  }
  const fresh =
    entry.hasData && Date.now() - entry.fetchedAt <= Math.max(0, staleTimeMs)
  if (!force && !entry.invalidated && fresh) {
    return Promise.resolve(entry.data as T)
  }

  const revision = entry.revision
  const controller = new AbortController()
  entry.controller = controller
  entry.error = null

  const request = Promise.resolve().then(() => fetcher(controller.signal))
  const settled = request
    .then((data) => {
      if (entry.revision === revision) {
        entry.hasData = true
        entry.data = data
        entry.fetchedAt = Date.now()
        entry.invalidated = false
        entry.error = null
      }
      return data
    })
    .catch((error: unknown) => {
      if (entry.revision === revision) {
        // One failed refresh is visible, but it must not trigger an automatic
        // retry loop through the invalidation subscriber.
        entry.invalidated = false
        entry.error = asError(error)
      }
      throw error
    })
    .finally(() => {
      if (entry.inFlight === settled) {
        entry.inFlight = null
        entry.controller = null
        notify(entry)
      }
    })

  entry.inFlight = settled
  notify(entry)
  return settled
}

export function invalidateResource(key: string): void {
  const entry = entries.get(ownedKey(key))
  if (entry === undefined) {
    return
  }
  entry.revision += 1
  entry.invalidated = true
  entry.error = null
  entry.controller?.abort()
  entry.controller = null
  entry.inFlight = null
  notify(entry)
}

export function invalidateResourcePrefix(prefix: string): void {
  const ownedPrefix = ownedKey(prefix)
  for (const [key, entry] of entries) {
    if (key.startsWith(ownedPrefix)) {
      entry.revision += 1
      entry.invalidated = true
      entry.error = null
      entry.controller?.abort()
      entry.controller = null
      entry.inFlight = null
      notify(entry)
    }
  }
}

export function primeResource<T>(key: string, data: T): void {
  const entry = cacheEntry(key)
  entry.revision += 1
  entry.controller?.abort()
  entry.controller = null
  entry.inFlight = null
  entry.hasData = true
  entry.data = data
  entry.fetchedAt = Date.now()
  entry.invalidated = false
  entry.error = null
  notify(entry)
}

export function clearResourceCache(): void {
  for (const entry of entries.values()) {
    entry.revision += 1
    entry.controller?.abort()
    entry.controller = null
    entry.inFlight = null
    entry.hasData = false
    entry.data = undefined
    entry.error = null
    entry.invalidated = false
  }
  entries.clear()
}
