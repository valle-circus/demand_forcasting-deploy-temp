import { describe, expect, it } from 'vitest'

import {
  ApiError,
  ConflictError,
  NotFoundError,
  ServiceUnavailableError,
  UnauthorizedError,
  ValidationError,
  isNotFound,
  isUnauthorized,
  isUnavailable,
  parseApiError,
} from './errors'

describe('parseApiError — planner-facing envelope', () => {
  it('maps each status to its typed error and keeps the server message', () => {
    const cases: Array<[number, new (...args: never[]) => ApiError]> = [
      [401, UnauthorizedError],
      [404, NotFoundError],
      [409, ConflictError],
      [422, ValidationError],
      [503, ServiceUnavailableError],
    ]

    for (const [status, expected] of cases) {
      const error = parseApiError(status, {
        error: { code: 'some_code', message: 'Server said this.', details: {} },
      })
      expect(error).toBeInstanceOf(expected)
      expect(error.status).toBe(status)
      expect(error.code).toBe('some_code')
      expect(error.message).toBe('Server said this.')
    }
  })

  it('preserves conflict details so the UI can explain the conflict', () => {
    const error = parseApiError(409, {
      error: {
        code: 'master_source_not_accepted',
        message: 'Only a version backed by an accepted import can be activated.',
        details: { version_id: 'abc' },
      },
    })
    expect(error.details).toEqual({ version_id: 'abc' })
  })

  it('falls back to a generic status message when the body has none', () => {
    const error = parseApiError(500, null)
    expect(error.message).toBe('The planning service reported an error.')
    expect(error.code).toBe('http_error')
  })
})

describe('parseApiError — FastAPI request validation', () => {
  // FastAPI's RequestValidationError bypasses the ApiError handler entirely
  // and emits its own `detail` array, so both shapes reach the client.
  it('extracts field issues and drops the leading body/query segment', () => {
    const error = parseApiError(422, {
      detail: [
        {
          loc: ['body', 'planning_as_of_at'],
          msg: 'planning_as_of_at must include a timezone offset',
          type: 'value_error',
        },
      ],
    })

    expect(error).toBeInstanceOf(ValidationError)
    expect(error.fieldIssues).toEqual([
      {
        field: 'planning_as_of_at',
        message: 'planning_as_of_at must include a timezone offset',
        type: 'value_error',
      },
    ])
    expect(error.message).toContain('planning_as_of_at')
  })

  it('summarises rather than concatenating when several fields fail', () => {
    const error = parseApiError(422, {
      detail: [
        { loc: ['body', 'location_id'], msg: 'field required', type: 'missing' },
        { loc: ['body', 'as_of_at'], msg: 'field required', type: 'missing' },
      ],
    })
    expect(error.fieldIssues).toHaveLength(2)
    expect(error.message).toBe('2 fields failed validation.')
  })

  it('accepts a plain string detail', () => {
    const error = parseApiError(400, { detail: 'Unsupported file type.' })
    expect(error.message).toBe('Unsupported file type.')
  })
})

describe('parseApiError — hostile or unexpected bodies', () => {
  it.each([null, undefined, 'plain text', 42, []])(
    'does not throw while handling %p',
    (body) => {
      expect(() => parseApiError(500, body)).not.toThrow()
    },
  )

  it('ignores a non-object error field', () => {
    const error = parseApiError(404, { error: 'nope' })
    expect(error).toBeInstanceOf(NotFoundError)
    expect(error.message).toBe('The requested resource was not found.')
  })
})

describe('narrowing helpers', () => {
  it('identifies the statuses the UI branches on', () => {
    expect(isUnauthorized(parseApiError(401, null))).toBe(true)
    expect(isNotFound(parseApiError(404, null))).toBe(true)
    expect(isUnavailable(parseApiError(503, null))).toBe(true)

    // 503 is an unavailable dependency, never an empty result.
    expect(isNotFound(parseApiError(503, null))).toBe(false)
    expect(isUnauthorized(new Error('plain'))).toBe(false)
  })
})
