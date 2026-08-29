/**
 * The single typed client for the Supply Planning API.
 *
 * Boundaries this file enforces:
 * - Every `/api/v1` domain request carries `Authorization: Bearer <token>`
 *   from the live Supabase session. Health and readiness stay unauthenticated.
 * - Failures become typed errors from `errors.ts`. Nothing here ever returns a
 *   synthetic or fallback value when a request fails.
 * - The browser never talks to Supabase domain tables; Supabase is Auth only.
 */

import {
  ApiError,
  NetworkError,
  UnauthorizedError,
  isAbort,
  parseApiError,
} from './errors'
import type {
  ActivationResponse,
  CreatePlanningRunRequest,
  DatasetType,
  HealthResponse,
  InventoryResponse,
  IsoDateTime,
  LocationsResponse,
  MasterDataVersion,
  OverviewResponse,
  PlanningRunResponse,
  PlanningStatusResponse,
  PurchaseOrdersResponse,
  ReadinessResponse,
  SourceImport,
  UserResponse,
} from './types'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

/** Empty in local development, where Vite proxies `/api` to the API process. */
export const apiBaseUrl = configuredBaseUrl?.replace(/\/$/, '') ?? ''

// ---------------------------------------------------------------------------
// Session wiring
//
// The client needs an access token but must not import the auth provider,
// which would create a cycle. The provider registers callbacks at startup.
// ---------------------------------------------------------------------------

type TokenProvider = () => Promise<string | null>

let tokenProvider: TokenProvider = async () => null
let unauthorizedHandler: (() => void) | null = null

/** Called once by `AuthProvider` so requests can read the current token. */
export function configureAuthTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider
}

/**
 * Called once by `AuthProvider`. Fires whenever the API rejects a token so the
 * session can be cleared and the sign-in gate shown. It never retries the
 * request — a retry loop against an invalid session is worse than one failure.
 */
export function configureUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler
}

// ---------------------------------------------------------------------------
// Core request plumbing
// ---------------------------------------------------------------------------

interface RequestOptions {
  method?: 'GET' | 'POST'
  /** JSON body. Mutually exclusive with `formData`. */
  json?: unknown
  formData?: FormData
  signal?: AbortSignal
  /** Health and readiness are public; everything else requires a token. */
  authenticated?: boolean
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    const text = await response.text().catch(() => '')
    return text ? { detail: text } : null
  }
  return response.json().catch(() => null)
}

function reportUnauthorized(error: ApiError): void {
  if (error instanceof UnauthorizedError && unauthorizedHandler !== null) {
    unauthorizedHandler()
  }
}

async function authorizationHeader(): Promise<Record<string, string>> {
  const token = await tokenProvider()
  if (token === null) {
    // Fail closed and locally: do not send an unauthenticated domain request
    // just to receive a 401 from the server.
    const error = new UnauthorizedError(
      'You are not signed in. Sign in to load planning data.',
      'no_session',
    )
    reportUnauthorized(error)
    throw error
  }
  return { Authorization: `Bearer ${token}` }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', json, formData, signal, authenticated = true } = options

  const headers: Record<string, string> = {}
  if (authenticated) {
    Object.assign(headers, await authorizationHeader())
  }
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : formData,
      signal,
    })
  } catch (cause) {
    if (isAbort(cause)) {
      throw cause
    }
    throw new NetworkError(
      'The planning API could not be reached. Check your connection and that the API is running.',
    )
  }

  if (!response.ok) {
    const error = parseApiError(response.status, await parseBody(response))
    reportUnauthorized(error)
    throw error
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await parseBody(response)) as T
}

// ---------------------------------------------------------------------------
// Uploads
//
// `fetch` cannot report upload progress, and the purchase-order card accepts
// several multi-megabyte PDFs. XMLHttpRequest is the only browser API that
// exposes progress, so uploads use it while everything else uses fetch.
// ---------------------------------------------------------------------------

export interface UploadOptions {
  /** Fraction between 0 and 1, or null while the total size is unknown. */
  onProgress?: (fraction: number | null) => void
  signal?: AbortSignal
}

async function upload<T>(
  path: string,
  formData: FormData,
  options: UploadOptions = {},
): Promise<T> {
  const headers = await authorizationHeader()

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${apiBaseUrl}${path}`)
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value)
    }
    xhr.responseType = 'text'

    const abort = (): void => {
      xhr.abort()
    }
    options.signal?.addEventListener('abort', abort, { once: true })

    const settle = (): void => {
      options.signal?.removeEventListener('abort', abort)
    }

    xhr.upload.onprogress = (event) => {
      options.onProgress?.(
        event.lengthComputable ? event.loaded / event.total : null,
      )
    }

    xhr.onload = () => {
      settle()
      let body: unknown = null
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch {
        body = xhr.responseText ? { detail: xhr.responseText } : null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T)
        return
      }
      const error = parseApiError(xhr.status, body)
      reportUnauthorized(error)
      reject(error)
    }

    xhr.onerror = () => {
      settle()
      reject(
        new NetworkError(
          'The upload could not reach the planning API. Check your connection and try again.',
        ),
      )
    }

    xhr.onabort = () => {
      settle()
      reject(new DOMException('Upload aborted', 'AbortError'))
    }

    xhr.send(formData)
  })
}

// ---------------------------------------------------------------------------
// Downloads
//
// Export endpoints require the bearer header, so a plain `<a href>` cannot be
// used. The response is fetched, turned into a Blob, and handed to the browser.
// The file is generated by the API; it is never reconstructed here.
// ---------------------------------------------------------------------------

export interface DownloadedFile {
  blob: Blob
  fileName: string
}

function fileNameFromDisposition(header: string | null, fallback: string): string {
  if (header === null) {
    return fallback
  }
  const quoted = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header)
  return quoted?.[1] ? decodeURIComponent(quoted[1]) : fallback
}

async function download(
  path: string,
  fallbackFileName: string,
  signal?: AbortSignal,
): Promise<DownloadedFile> {
  const headers = await authorizationHeader()

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { headers, signal })
  } catch (cause) {
    if (isAbort(cause)) {
      throw cause
    }
    throw new NetworkError('The download could not reach the planning API.')
  }

  if (!response.ok) {
    const error = parseApiError(response.status, await parseBody(response))
    reportUnauthorized(error)
    throw error
  }

  return {
    blob: await response.blob(),
    fileName: fileNameFromDisposition(
      response.headers.get('content-disposition'),
      fallbackFileName,
    ),
  }
}

/** Hand a downloaded file to the browser's save flow. */
export function saveFile(file: DownloadedFile): void {
  const url = URL.createObjectURL(file.blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = file.fileName
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// System endpoints (public)
// ---------------------------------------------------------------------------

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/api/v1/health', {
    authenticated: false,
    signal,
  })
}

export function fetchReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return request<ReadinessResponse>('/api/v1/readiness', {
    authenticated: false,
    signal,
  })
}

// ---------------------------------------------------------------------------
// Identity and locations
// ---------------------------------------------------------------------------

export function fetchMe(signal?: AbortSignal): Promise<UserResponse> {
  return request<UserResponse>('/api/v1/me', { signal })
}

/**
 * Active locations for the current master version.
 *
 * A 404 here is the first-run state — no active master-data version exists for
 * this environment yet — not a broken request. Callers render the
 * upload-the-master-workbook state.
 */
export function fetchLocations(signal?: AbortSignal): Promise<LocationsResponse> {
  return request<LocationsResponse>('/api/v1/locations', { signal })
}

export function fetchOverview(signal?: AbortSignal): Promise<OverviewResponse> {
  return request<OverviewResponse>('/api/v1/overview', { signal })
}

export function fetchPlanningStatus(
  locationId: string,
  signal?: AbortSignal,
): Promise<PlanningStatusResponse> {
  return request<PlanningStatusResponse>(
    `/api/v1/locations/${encodeURIComponent(locationId)}/planning-status`,
    { signal },
  )
}

/** 404 means no accepted stock import for this location yet. */
export function fetchInventory(
  locationId: string,
  signal?: AbortSignal,
): Promise<InventoryResponse> {
  return request<InventoryResponse>(
    `/api/v1/locations/${encodeURIComponent(locationId)}/inventory`,
    { signal },
  )
}

/** 404 means no accepted purchase-order import for this location yet. */
export function fetchPurchaseOrders(
  locationId: string,
  signal?: AbortSignal,
): Promise<PurchaseOrdersResponse> {
  return request<PurchaseOrdersResponse>(
    `/api/v1/locations/${encodeURIComponent(locationId)}/purchase-orders`,
    { signal },
  )
}

// ---------------------------------------------------------------------------
// Source imports
// ---------------------------------------------------------------------------

export function listImports(
  filters: { datasetType?: DatasetType; locationId?: string } = {},
  signal?: AbortSignal,
): Promise<SourceImport[]> {
  const query = new URLSearchParams()
  if (filters.datasetType) {
    query.set('dataset_type', filters.datasetType)
  }
  if (filters.locationId) {
    query.set('location_id', filters.locationId)
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return request<SourceImport[]>(`/api/v1/imports${suffix}`, { signal })
}

export function getImport(
  importId: string,
  signal?: AbortSignal,
): Promise<SourceImport> {
  return request<SourceImport>(
    `/api/v1/imports/${encodeURIComponent(importId)}`,
    { signal },
  )
}

/** Creates a master-data *draft*. Activation is a separate explicit action. */
export function importMasterData(
  file: File,
  options?: UploadOptions,
): Promise<SourceImport> {
  const form = new FormData()
  form.append('file', file)
  return upload<SourceImport>('/api/v1/imports/master-data', form, options)
}

export function importPlanningInput(
  file: File,
  options?: UploadOptions,
): Promise<SourceImport> {
  const form = new FormData()
  form.append('file', file)
  return upload<SourceImport>('/api/v1/imports/planning-input', form, options)
}

export function importStock(
  file: File,
  locationId: string,
  options?: UploadOptions,
): Promise<SourceImport> {
  const form = new FormData()
  form.append('file', file)
  form.append('location_id', locationId)
  return upload<SourceImport>('/api/v1/imports/stock', form, options)
}

/**
 * Cumulative Transgourmet PDFs. `asOfAt` must include a timezone offset; the
 * API rejects a naive timestamp.
 */
export function importPurchaseOrders(
  files: File[],
  locationId: string,
  asOfAt: IsoDateTime,
  options?: UploadOptions,
): Promise<SourceImport> {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  form.append('location_id', locationId)
  form.append('as_of_at', asOfAt)
  return upload<SourceImport>('/api/v1/imports/purchase-orders', form, options)
}

// ---------------------------------------------------------------------------
// Master-data versions
// ---------------------------------------------------------------------------

export function listMasterVersions(
  signal?: AbortSignal,
): Promise<MasterDataVersion[]> {
  return request<MasterDataVersion[]>('/api/v1/master-data/versions', { signal })
}

export function activateMasterVersion(
  versionId: string,
  signal?: AbortSignal,
): Promise<ActivationResponse> {
  return request<ActivationResponse>(
    `/api/v1/master-data/versions/${encodeURIComponent(versionId)}/activate`,
    { method: 'POST', signal },
  )
}

// ---------------------------------------------------------------------------
// Planning runs
// ---------------------------------------------------------------------------

/**
 * Runs the calculation synchronously and returns the persisted result.
 *
 * There is no job id and no idempotency key, so callers must prevent duplicate
 * submission themselves. No `signal` is accepted on purpose: aborting the
 * request would not stop the server-side run, and could leave the maintainer
 * believing nothing happened when a run had in fact been persisted.
 */
export function createPlanningRun(
  body: CreatePlanningRunRequest,
): Promise<PlanningRunResponse> {
  return request<PlanningRunResponse>('/api/v1/planning-runs', {
    method: 'POST',
    json: body,
  })
}

export function getPlanningRun(
  runId: string,
  signal?: AbortSignal,
): Promise<PlanningRunResponse> {
  return request<PlanningRunResponse>(
    `/api/v1/planning-runs/${encodeURIComponent(runId)}`,
    { signal },
  )
}

export function downloadRunCsv(
  runId: string,
  signal?: AbortSignal,
): Promise<DownloadedFile> {
  return download(
    `/api/v1/planning-runs/${encodeURIComponent(runId)}/export.csv`,
    `recommendations-${runId}.csv`,
    signal,
  )
}

export function downloadRunJson(
  runId: string,
  signal?: AbortSignal,
): Promise<DownloadedFile> {
  return download(
    `/api/v1/planning-runs/${encodeURIComponent(runId)}/export.json`,
    `recommendations-${runId}.json`,
    signal,
  )
}
