/**
 * Typed errors for the Supply Planning API.
 *
 * The API returns two different error shapes and the client must handle both:
 *
 * 1. Planner-facing errors from `ApiError` / `HTTPException` handlers:
 *      `{ "error": { "code": string, "message": string, "details": object } }`
 * 2. FastAPI request-validation errors, which bypass those handlers:
 *      `{ "detail": [ { "loc": [...], "msg": string, "type": string } ] }`
 *
 * Nothing here ever substitutes a fallback value for a failed request. An
 * error is surfaced as an error.
 */

/** One field-level problem from FastAPI's request validation. */
export interface FieldIssue {
  field: string
  message: string
  type: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly fieldIssues: FieldIssue[]

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    fieldIssues: FieldIssue[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.fieldIssues = fieldIssues
  }
}

/** 401 — no session, expired session, or a token the API rejected. */
export class UnauthorizedError extends ApiError {
  constructor(message: string, code = 'invalid_session') {
    super(401, code, message)
    this.name = 'UnauthorizedError'
  }
}

/** 403 — authenticated but not permitted. */
export class ForbiddenError extends ApiError {
  constructor(message: string, code = 'forbidden') {
    super(403, code, message)
    this.name = 'ForbiddenError'
  }
}

/**
 * 404 — the resource does not exist.
 *
 * Note that several endpoints use 404 to mean "nothing imported yet" rather
 * than "wrong URL". Callers that can distinguish those cases should catch this
 * and render a first-run or empty state instead of an error.
 */
export class NotFoundError extends ApiError {
  constructor(message: string, code = 'not_found') {
    super(404, code, message)
    this.name = 'NotFoundError'
  }
}

/** 409 — the request conflicts with current state, e.g. an inactive draft. */
export class ConflictError extends ApiError {
  constructor(
    message: string,
    code = 'conflict',
    details: Record<string, unknown> = {},
  ) {
    super(409, code, message, details)
    this.name = 'ConflictError'
  }
}

/** 422 — the payload or uploaded file failed validation. */
export class ValidationError extends ApiError {
  constructor(
    message: string,
    code = 'validation_failed',
    details: Record<string, unknown> = {},
    fieldIssues: FieldIssue[] = [],
  ) {
    super(422, code, message, details, fieldIssues)
    this.name = 'ValidationError'
  }
}

/**
 * 503 — a dependency is unavailable or unconfigured.
 *
 * This is emphatically not "no data". It must be presented as a broken
 * dependency with the server's own message, never as an empty result.
 */
export class ServiceUnavailableError extends ApiError {
  constructor(message: string, code = 'persistence_unavailable') {
    super(503, code, message)
    this.name = 'ServiceUnavailableError'
  }
}

/** The request never reached the API: offline, DNS, CORS, or aborted. */
export class NetworkError extends ApiError {
  constructor(message: string) {
    super(0, 'network_error', message)
    this.name = 'NetworkError'
  }
}

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

interface ErrorEnvelope {
  error?: {
    code?: unknown
    message?: unknown
    details?: unknown
  }
  detail?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Turn a FastAPI `detail` array into field-level issues. */
function parseFieldIssues(detail: unknown): FieldIssue[] {
  if (!Array.isArray(detail)) {
    return []
  }
  const issues: FieldIssue[] = []
  for (const entry of detail) {
    if (!isRecord(entry)) {
      continue
    }
    const location = Array.isArray(entry.loc) ? entry.loc : []
    // Drop the leading "body" / "query" segment; it is noise for the reader.
    const field =
      location
        .slice(1)
        .map((part) => String(part))
        .join('.') || String(location[0] ?? 'request')
    issues.push({
      field,
      message: typeof entry.msg === 'string' ? entry.msg : 'Invalid value.',
      type: typeof entry.type === 'string' ? entry.type : 'invalid',
    })
  }
  return issues
}

function defaultMessage(status: number): string {
  if (status >= 500) {
    return 'The planning service reported an error.'
  }
  if (status === 404) {
    return 'The requested resource was not found.'
  }
  return 'The request could not be completed.'
}

/**
 * Build a typed error from an HTTP status and a parsed response body.
 *
 * Bodies that are not one of the two known shapes still produce a usable
 * error rather than throwing while handling an error.
 */
export function parseApiError(status: number, body: unknown): ApiError {
  const envelope: ErrorEnvelope = isRecord(body) ? body : {}

  let code: string | undefined
  let message: string | undefined
  let details: Record<string, unknown> = {}
  let fieldIssues: FieldIssue[] = []

  if (isRecord(envelope.error)) {
    const { error } = envelope
    code = typeof error.code === 'string' ? error.code : undefined
    message = typeof error.message === 'string' ? error.message : undefined
    details = isRecord(error.details) ? error.details : {}
  } else if (envelope.detail !== undefined) {
    // FastAPI request validation, or a plain string detail.
    if (typeof envelope.detail === 'string') {
      message = envelope.detail
    } else {
      fieldIssues = parseFieldIssues(envelope.detail)
      if (fieldIssues.length > 0) {
        message =
          fieldIssues.length === 1
            ? `${fieldIssues[0].field}: ${fieldIssues[0].message}`
            : `${String(fieldIssues.length)} fields failed validation.`
      }
    }
  }

  const resolvedMessage = message ?? defaultMessage(status)

  switch (status) {
    case 401:
      return new UnauthorizedError(resolvedMessage, code)
    case 403:
      return new ForbiddenError(resolvedMessage, code)
    case 404:
      return new NotFoundError(resolvedMessage, code)
    case 409:
      return new ConflictError(resolvedMessage, code, details)
    case 422:
      return new ValidationError(resolvedMessage, code, details, fieldIssues)
    case 503:
      return new ServiceUnavailableError(resolvedMessage, code)
    default:
      return new ApiError(
        status,
        code ?? 'http_error',
        resolvedMessage,
        details,
        fieldIssues,
      )
  }
}

// ---------------------------------------------------------------------------
// Narrowing helpers
// ---------------------------------------------------------------------------

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function isUnauthorized(error: unknown): error is UnauthorizedError {
  return error instanceof ApiError && error.status === 401
}

export function isNotFound(error: unknown): error is NotFoundError {
  return error instanceof ApiError && error.status === 404
}

export function isConflict(error: unknown): error is ConflictError {
  return error instanceof ApiError && error.status === 409
}

export function isValidationFailure(error: unknown): error is ValidationError {
  return error instanceof ApiError && error.status === 422
}

export function isUnavailable(error: unknown): error is ServiceUnavailableError {
  return error instanceof ApiError && error.status === 503
}

/** True when the caller aborted the request, so it should be ignored. */
export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

/** A safe human-readable message for any thrown value. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred.'
}
