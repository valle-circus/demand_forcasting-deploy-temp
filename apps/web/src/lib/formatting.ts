/**
 * Display formatting.
 *
 * Two rules are enforced here rather than by code review:
 *
 * 1. **Quantities require an explicit unit.** There is no `formatQuantity(n)`
 *    overload, so a mixed-unit total cannot be produced by accident. Journey
 *    doc §2.5 and the master backlog both forbid summing heterogeneous item
 *    quantities into one number.
 * 2. **Timestamps require a timezone.** Every location carries its own IANA
 *    zone and the maintainer reads times in the location's local time, not the
 *    browser's.
 */

import type { IsoDate, IsoDateTime, Numeric } from './types'

const FALLBACK_TIME_ZONE = 'UTC'

/** Rendered in place of a value that is absent rather than zero. */
export const NOT_AVAILABLE = '—'

// ---------------------------------------------------------------------------
// Numbers
// ---------------------------------------------------------------------------

/**
 * Normalize an API numeric, which may arrive as a JSON number or as a decimal
 * string. Returns `null` for absent or unparseable values so callers render
 * `NOT_AVAILABLE` instead of a misleading `0`.
 */
export function toNumber(value: Numeric | null | undefined): number | null {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatDecimal(value: number, maximumFractionDigits: number): string {
  return new Intl.NumberFormat('en-GB', {
    maximumFractionDigits,
    minimumFractionDigits: 0,
  }).format(value)
}

// ---------------------------------------------------------------------------
// Quantities — a unit is always required
// ---------------------------------------------------------------------------

/**
 * Format a quantity with its unit. The unit is mandatory: an unlabelled
 * quantity is meaningless in this domain, where packs, cartons, order units
 * and grams all appear on the same screen.
 */
export function formatQuantity(
  value: Numeric | null | undefined,
  unit: string,
  options: { maximumFractionDigits?: number } = {},
): string {
  const parsed = toNumber(value)
  if (parsed === null) {
    return NOT_AVAILABLE
  }
  const digits = options.maximumFractionDigits ?? 2
  return `${formatDecimal(parsed, digits)} ${unit}`
}

/**
 * Format a gram value, switching to kilograms above 1000 g for readability.
 * The underlying unit is always grams; only the presentation scales.
 */
export function formatGrams(value: Numeric | null | undefined): string {
  const parsed = toNumber(value)
  if (parsed === null) {
    return NOT_AVAILABLE
  }
  if (Math.abs(parsed) >= 1000) {
    return `${formatDecimal(parsed / 1000, 2)} kg`
  }
  return `${formatDecimal(parsed, 0)} g`
}

/** Format a proposed order quantity in its own order unit (carton, pack, …). */
export function formatOrderUnits(
  value: Numeric | null | undefined,
  orderUnit: string,
): string {
  return formatQuantity(value, orderUnit, { maximumFractionDigits: 2 })
}

/** Format a plain count with a singular/plural noun. */
export function formatCount(
  value: number | null | undefined,
  singular: string,
  plural = `${singular}s`,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return NOT_AVAILABLE
  }
  return `${formatDecimal(value, 0)} ${value === 1 ? singular : plural}`
}

/** Format a multiplier such as a yield factor. */
export function formatFactor(value: Numeric | null | undefined): string {
  const parsed = toNumber(value)
  return parsed === null ? NOT_AVAILABLE : `×${formatDecimal(parsed, 4)}`
}

// ---------------------------------------------------------------------------
// Dates and times — a timezone is always required
// ---------------------------------------------------------------------------

function safeDate(value: IsoDateTime | IsoDate | null | undefined): Date | null {
  if (!value) {
    return null
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function withTimeZone(
  options: Intl.DateTimeFormatOptions,
  timeZone: string,
): Intl.DateTimeFormatOptions {
  try {
    // Throws for an unknown zone; fall back rather than crash a whole page.
    new Intl.DateTimeFormat('en-GB', { timeZone }).format(new Date())
    return { ...options, timeZone }
  } catch {
    return { ...options, timeZone: FALLBACK_TIME_ZONE }
  }
}

/**
 * Format a timestamp in a location's timezone, including the zone name so the
 * reader is never guessing which clock a value refers to.
 */
export function formatDateTime(
  value: IsoDateTime | null | undefined,
  timeZone: string,
): string {
  const date = safeDate(value)
  if (date === null) {
    return NOT_AVAILABLE
  }
  return new Intl.DateTimeFormat(
    'en-GB',
    withTimeZone(
      {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZoneName: 'short',
      },
      timeZone,
    ),
  ).format(date)
}

/** Format a calendar date. Dates carry no time, so no zone shift is applied. */
export function formatDate(value: IsoDate | null | undefined): string {
  const date = safeDate(value)
  if (date === null) {
    return NOT_AVAILABLE
  }
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

/** Short calendar date for dense tables, e.g. `28 Aug`. */
export function formatDateShort(value: IsoDate | null | undefined): string {
  const date = safeDate(value)
  if (date === null) {
    return NOT_AVAILABLE
  }
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    timeZone: 'UTC',
  }).format(date)
}

const RELATIVE = new Intl.RelativeTimeFormat('en-GB', { numeric: 'auto' })

const RELATIVE_STEPS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['second', 60],
  ['minute', 60],
  ['hour', 24],
  ['day', 7],
  ['week', 4.348],
  ['month', 12],
  ['year', Number.POSITIVE_INFINITY],
]

/**
 * Human-readable age, e.g. `2 hours ago`. Used beside — never instead of —
 * an absolute timestamp, because "3 days ago" alone hides which day.
 */
export function formatRelativeAge(
  value: IsoDateTime | null | undefined,
  now: Date = new Date(),
): string {
  const date = safeDate(value)
  if (date === null) {
    return NOT_AVAILABLE
  }
  let delta = (date.getTime() - now.getTime()) / 1000
  for (const [unit, step] of RELATIVE_STEPS) {
    if (Math.abs(delta) < step) {
      return RELATIVE.format(Math.round(delta), unit)
    }
    delta /= step
  }
  return RELATIVE.format(Math.round(delta), 'year')
}

/** Whole days between a timestamp and now; negative when the date is past. */
export function daysFromNow(
  value: IsoDate | IsoDateTime | null | undefined,
  now: Date = new Date(),
): number | null {
  const date = safeDate(value)
  if (date === null) {
    return null
  }
  const msPerDay = 86_400_000
  return Math.round((date.getTime() - now.getTime()) / msPerDay)
}

/**
 * The current instant as a timezone-aware ISO string, which is what
 * `POST /planning-runs` requires for `planning_as_of_at`. The offset is the
 * browser's, which is correct: it is the real instant the maintainer acted.
 */
export function nowWithOffset(now: Date = new Date()): IsoDateTime {
  const offsetMinutes = -now.getTimezoneOffset()
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const absolute = Math.abs(offsetMinutes)
  const pad = (part: number): string => String(part).padStart(2, '0')
  const offset = `${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`
  const local = new Date(now.getTime() + offsetMinutes * 60_000)
  return `${local.toISOString().slice(0, 19)}${offset}`
}

// ---------------------------------------------------------------------------
// Files and identifiers
// ---------------------------------------------------------------------------

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return NOT_AVAILABLE
  }
  if (value < 1024) {
    return `${formatDecimal(value, 0)} B`
  }
  if (value < 1024 * 1024) {
    return `${formatDecimal(value / 1024, 1)} KB`
  }
  return `${formatDecimal(value / (1024 * 1024), 1)} MB`
}

/** Shorten a content hash or run id for display without losing recognisability. */
export function formatShortId(value: string | null | undefined): string {
  if (!value) {
    return NOT_AVAILABLE
  }
  return value.length <= 12 ? value : `${value.slice(0, 12)}…`
}

/** Turn a snake_case code into sentence case for a label. */
export function humanizeCode(value: string): string {
  const spaced = value.replace(/[_-]+/g, ' ').trim().toLowerCase()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
