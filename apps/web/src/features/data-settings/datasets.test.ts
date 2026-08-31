import { describe, expect, it } from 'vitest'

import type { SourceImport } from '../../lib/types'
import {
  DATASETS,
  currentImport,
  importHistory,
  prerequisiteFor,
} from './datasets'
import type { WorkspaceReadiness } from './datasets'

const EVERYTHING_READY: WorkspaceReadiness = {
  hasActiveMasterVersion: true,
  hasLocations: true,
  selectedLocationId: 'LOC_KOELN',
  planningInputCoversLocation: true,
}

function sourceImport(overrides: Partial<SourceImport>): SourceImport {
  return {
    id: 'import-1',
    dataset_type: 'stock',
    location_id: null,
    status: 'accepted',
    source_version: 'v1',
    source_as_of_at: null,
    coverage_start_date: null,
    coverage_end_date: null,
    file_names: ['file.xlsx'],
    file_count: 1,
    total_bytes: 10,
    content_hash: 'hash',
    parser_version: 'p1',
    record_count: 1,
    warning_count: 0,
    error_count: 0,
    validation_issues: [],
    metadata: {},
    supersedes_import_id: null,
    created_at: '2026-08-29T09:00:00+00:00',
    created_by: null,
    ...overrides,
  }
}

describe('the upload sequence', () => {
  it('numbers the four datasets in the order the API requires', () => {
    expect(DATASETS.map((entry) => [entry.step, entry.key])).toEqual([
      [1, 'master_data'],
      [2, 'planning_input'],
      [3, 'stock'],
      [4, 'purchase_orders'],
    ])
  })

  it('lets the master workbook be imported on a completely empty workspace', () => {
    expect(
      prerequisiteFor('master_data', {
        hasActiveMasterVersion: false,
        hasLocations: false,
        selectedLocationId: null,
        planningInputCoversLocation: false,
      }),
    ).toEqual({ blocked: false })
  })

  it('blocks everything else until a master version is active', () => {
    const empty: WorkspaceReadiness = {
      hasActiveMasterVersion: false,
      hasLocations: false,
      selectedLocationId: null,
      planningInputCoversLocation: false,
    }

    for (const key of ['planning_input', 'stock', 'purchase_orders'] as const) {
      const result = prerequisiteFor(key, empty)
      expect(result.blocked).toBe(true)
      expect(result.reason).toMatch(/master-data version is active/i)
      // Points at the step that clears the block, not just "no".
      expect(result.unblockedByStep).toBe(1)
    }
  })

  it('blocks stock until a planning workbook covers the chosen location', () => {
    // The API refuses this with 409 planning_input_missing; explaining it
    // beforehand beats letting the maintainer discover it by failing.
    const result = prerequisiteFor('stock', {
      ...EVERYTHING_READY,
      planningInputCoversLocation: false,
    })

    expect(result.blocked).toBe(true)
    expect(result.reason).toMatch(/planning workbook/i)
    expect(result.unblockedByStep).toBe(2)
  })

  it('does not impose the planning-workbook rule on purchase orders', () => {
    // Only stock validates against the planning item set.
    expect(
      prerequisiteFor('purchase_orders', {
        ...EVERYTHING_READY,
        planningInputCoversLocation: false,
      }),
    ).toEqual({ blocked: false })
  })

  it('asks for a location before a location-scoped upload', () => {
    for (const key of ['stock', 'purchase_orders'] as const) {
      const result = prerequisiteFor(key, {
        ...EVERYTHING_READY,
        selectedLocationId: null,
      })
      expect(result.blocked).toBe(true)
      expect(result.reason).toMatch(/choose a location/i)
    }
  })

  it('explains an active master version that contains no locations', () => {
    const result = prerequisiteFor('stock', {
      ...EVERYTHING_READY,
      hasLocations: false,
      selectedLocationId: null,
    })
    expect(result.reason).toMatch(/no active locations/i)
  })

  it('clears every step once the chain is complete', () => {
    for (const definition of DATASETS) {
      expect(prerequisiteFor(definition.key, EVERYTHING_READY).blocked).toBe(
        false,
      )
    }
  })
})

describe('choosing what is currently in use', () => {
  const imports = [
    sourceImport({ id: 'newest-rejected', status: 'rejected' }),
    sourceImport({ id: 'newest-accepted', status: 'accepted_with_warnings' }),
    sourceImport({ id: 'older-accepted', status: 'accepted' }),
  ]

  it('picks the newest accepted import and ignores rejections', () => {
    expect(currentImport(imports, 'stock', null)?.id).toBe('newest-accepted')
  })

  it('treats accepted-with-warnings as in use, not as a failure', () => {
    expect(currentImport(imports, 'stock', null)?.status).toBe(
      'accepted_with_warnings',
    )
  })

  it('keeps location scopes apart', () => {
    const scoped = [
      sourceImport({ id: 'koeln', location_id: 'LOC_KOELN' }),
      sourceImport({ id: 'berlin', location_id: 'LOC_BERLIN' }),
    ]

    expect(currentImport(scoped, 'stock', 'LOC_BERLIN')?.id).toBe('berlin')
    // A global lookup must not pick up a location-scoped row.
    expect(currentImport(scoped, 'stock', null)).toBeNull()
  })

  it('returns null when nothing has been accepted', () => {
    expect(
      currentImport([sourceImport({ status: 'rejected' })], 'stock', null),
    ).toBeNull()
  })

  it('keeps rejected attempts in history so they stay auditable', () => {
    expect(importHistory(imports, 'stock', null).map((row) => row.id)).toEqual([
      'newest-rejected',
      'newest-accepted',
      'older-accepted',
    ])
  })
})
