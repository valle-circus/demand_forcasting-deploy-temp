import { describe, expect, it } from 'vitest'

import {
  NOT_AVAILABLE,
  daysFromNow,
  formatCount,
  formatDateTime,
  formatGrams,
  formatQuantity,
  formatRelativeAge,
  nowWithOffset,
  toNumber,
} from './formatting'

describe('toNumber', () => {
  it('accepts both shapes a numeric column can arrive as', () => {
    // PostgREST can emit a JSON number; Python Decimal serialization emits a
    // decimal string. Both reach the browser.
    expect(toNumber(1234.5)).toBe(1234.5)
    expect(toNumber('1234.50')).toBe(1234.5)
  })

  it('returns null rather than 0 for absent values', () => {
    // A missing value must not be rendered as zero — zero is a claim.
    expect(toNumber(null)).toBeNull()
    expect(toNumber(undefined)).toBeNull()
    expect(toNumber('')).toBeNull()
    expect(toNumber('not a number')).toBeNull()
  })
})

describe('quantity formatting', () => {
  it('always renders the unit alongside the number', () => {
    expect(formatQuantity(12, 'cartons')).toBe('12 cartons')
    expect(formatQuantity('3.5', 'packs')).toBe('3.5 packs')
  })

  it('renders absent quantities as unavailable, not zero', () => {
    expect(formatQuantity(null, 'cartons')).toBe(NOT_AVAILABLE)
  })

  it('scales grams to kilograms without changing the underlying unit', () => {
    expect(formatGrams(850)).toBe('850 g')
    expect(formatGrams(12_400)).toBe('12.4 kg')
    expect(formatGrams(null)).toBe(NOT_AVAILABLE)
  })

  it('pluralises counts', () => {
    expect(formatCount(1, 'location')).toBe('1 location')
    expect(formatCount(3, 'location')).toBe('3 locations')
    expect(formatCount(2, 'is', 'are')).toBe('2 are')
    expect(formatCount(null, 'location')).toBe(NOT_AVAILABLE)
  })
})

describe('timestamp formatting', () => {
  const instant = '2026-08-29T09:12:00+00:00'

  it('renders in the location timezone and names the zone', () => {
    const berlin = formatDateTime(instant, 'Europe/Berlin')
    // 09:12 UTC is 11:12 in Berlin during summer time.
    expect(berlin).toContain('11:12')
    expect(berlin).toContain('29 Aug 2026')
    // The zone must be visible so the reader never guesses which clock it is.
    expect(berlin).toMatch(/GMT|CEST|CET|UTC/)
  })

  it('shows a different wall-clock time for a different zone', () => {
    expect(formatDateTime(instant, 'Europe/Berlin')).not.toBe(
      formatDateTime(instant, 'America/New_York'),
    )
  })

  it('falls back to UTC instead of throwing on an unknown zone', () => {
    expect(() => formatDateTime(instant, 'Not/AZone')).not.toThrow()
    expect(formatDateTime(instant, 'Not/AZone')).toContain('09:12')
  })

  it('renders absent and malformed timestamps as unavailable', () => {
    expect(formatDateTime(null, 'Europe/Berlin')).toBe(NOT_AVAILABLE)
    expect(formatDateTime('not-a-date', 'Europe/Berlin')).toBe(NOT_AVAILABLE)
  })
})

describe('relative age', () => {
  const now = new Date('2026-08-29T12:00:00+00:00')

  it('describes recent and older timestamps', () => {
    expect(formatRelativeAge('2026-08-29T10:00:00+00:00', now)).toBe('2 hours ago')
    expect(formatRelativeAge('2026-08-26T12:00:00+00:00', now)).toBe('3 days ago')
  })

  it('counts whole days to a future date', () => {
    expect(daysFromNow('2026-09-01T12:00:00+00:00', now)).toBe(3)
    expect(daysFromNow(null, now)).toBeNull()
  })
})

describe('nowWithOffset', () => {
  it('produces the timezone-aware format the run endpoint requires', () => {
    // The API rejects a naive timestamp for planning_as_of_at.
    expect(nowWithOffset(new Date('2026-08-29T09:12:00Z'))).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/,
    )
  })

  it('round-trips to the same instant it was given', () => {
    const instant = new Date('2026-08-29T09:12:34Z')
    expect(new Date(nowWithOffset(instant)).getTime()).toBe(instant.getTime())
  })
})
