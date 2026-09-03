import type { DatasetType, SourceImport } from '../../lib/types'

/**
 * The four controlled upload groups, in the order the backend requires.
 *
 * They are numbered because they are a sequence, not four equal choices. The
 * API enforces the order: the planning workbook validates its locations and
 * items against the *active* master version, and a stock import is refused
 * with `planning_input_missing` until a planning workbook covers that
 * location. Presenting the cards as peers would walk a maintainer on a fresh
 * environment straight into a chain of conflicts.
 */
export interface DatasetDefinition {
  key: DatasetType
  step: number
  title: string
  scope: 'global' | 'location'
  /** `accept` attribute for the file input. Never treated as validation. */
  accept: string
  multiple: boolean
  fileDescription: string
  /** Dataset-specific instruction shown immediately before file selection. */
  uploadInstruction?: string
  purpose: string
  /** What accepting a new file does to what came before. */
  updateBehaviour: string
  /** What the source timestamp means for this dataset. */
  sourceTimeLabel: string
}

export const DATASETS: readonly DatasetDefinition[] = [
  {
    key: 'master_data',
    step: 1,
    title: 'Master data & rules',
    scope: 'global',
    accept: '.xlsx',
    multiple: false,
    fileDescription: 'Phase2_Master_Data_Template_v1.xlsx',
    purpose:
      'Items, item policies, locations and delivery rules. Everything else is validated against this.',
    updateBehaviour:
      'Creates a draft version. It changes nothing until you activate it below.',
    sourceTimeLabel: 'Source time',
  },
  {
    key: 'planning_input',
    step: 2,
    title: 'Forecast, menu & BOM',
    scope: 'global',
    accept: '.xlsx',
    multiple: false,
    fileDescription: 'Phase2_Planning_Input_Template_v1.xlsx',
    purpose:
      'Daily demand, the menu calendar, and the bill of materials for every dish.',
    updateBehaviour:
      'Creates a new immutable source version. It does not run planning.',
    sourceTimeLabel: 'Source time',
  },
  {
    key: 'stock',
    step: 3,
    title: 'Current stock',
    scope: 'location',
    accept: '.xlsx',
    multiple: false,
    fileDescription: 'Apicbase Stock Report export',
    purpose:
      'On-hand quantities for one location, used as the opening balance of the projection.',
    updateBehaviour:
      'Replaces the latest snapshot for this location. Earlier snapshots are kept as history.',
    // The count time comes from inside the export, not from when it was uploaded.
    sourceTimeLabel: 'Counted',
  },
  {
    key: 'purchase_orders',
    step: 4,
    title: 'Purchase-order PDFs',
    scope: 'location',
    accept: '.pdf',
    multiple: true,
    fileDescription: 'Cumulative Transgourmet Bestelldetails PDFs',
    uploadInstruction:
      'Select all still-relevant Transgourmet PDFs together, including files from previous order days. This upload replaces the previous PO snapshot, so files from earlier uploads are not carried forward. Exact duplicate files in this batch are ignored.',
    purpose:
      'Observed open supplier orders, so in-transit stock participates in netting.',
    updateBehaviour:
      'Replaces the previous PO snapshot for this location. Exact duplicate PDFs in the selected batch are de-duplicated.',
    sourceTimeLabel: 'Documents as of',
  },
]

// ---------------------------------------------------------------------------
// Prerequisites
// ---------------------------------------------------------------------------

export interface WorkspaceReadiness {
  hasActiveMasterVersion: boolean
  /** Whether any location can be selected at all. */
  hasLocations: boolean
  selectedLocationId: string | null
  /**
   * Whether an accepted planning workbook covers the selected location. The
   * server decides this (`planning-status.sources.planning_input`); the browser
   * only reads the answer.
   */
  planningInputCoversLocation: boolean
}

export interface Prerequisite {
  blocked: boolean
  reason?: string
  /** Where the maintainer goes to clear the block. */
  unblockedByStep?: number
}

const READY: Prerequisite = { blocked: false }

/**
 * Why a dataset cannot be uploaded yet, in the maintainer's own terms.
 *
 * This mirrors the conditions the API enforces; it does not invent new ones.
 * Its purpose is to explain a refusal before it happens rather than after.
 */
export function prerequisiteFor(
  key: DatasetType,
  readiness: WorkspaceReadiness,
): Prerequisite {
  if (key === 'master_data') {
    return READY
  }

  if (!readiness.hasActiveMasterVersion) {
    return {
      blocked: true,
      reason:
        'No master-data version is active yet. Import the master workbook and activate it first.',
      unblockedByStep: 1,
    }
  }

  if (key === 'planning_input') {
    return READY
  }

  // Both remaining datasets are scoped to one location.
  if (!readiness.hasLocations) {
    return {
      blocked: true,
      reason:
        'The active master version contains no active locations, so there is nothing to scope this upload to.',
      unblockedByStep: 1,
    }
  }

  if (readiness.selectedLocationId === null) {
    return {
      blocked: true,
      reason: 'Choose a location above before uploading this file.',
    }
  }

  if (key === 'stock' && !readiness.planningInputCoversLocation) {
    return {
      blocked: true,
      reason:
        'No accepted planning workbook covers this location yet. The stock export is validated against that item set, so it must be imported first.',
      unblockedByStep: 2,
    }
  }

  return READY
}

// ---------------------------------------------------------------------------
// Selecting what is current
// ---------------------------------------------------------------------------

const ACCEPTED_STATUSES = new Set(['accepted', 'accepted_with_warnings'])

/**
 * The newest accepted import for a dataset, matching how the API picks the
 * current source. `listImports` already returns newest-first, so this is a
 * selection over a sorted list, not a re-derivation of business rules.
 */
export function currentImport(
  imports: readonly SourceImport[],
  key: DatasetType,
  locationId: string | null,
): SourceImport | null {
  return (
    imports.find(
      (entry) =>
        entry.dataset_type === key &&
        ACCEPTED_STATUSES.has(entry.status) &&
        (locationId === null
          ? entry.location_id === null
          : entry.location_id === locationId),
    ) ?? null
  )
}

/** Every import for a dataset and scope, newest first, including rejections. */
export function importHistory(
  imports: readonly SourceImport[],
  key: DatasetType,
  locationId: string | null,
): SourceImport[] {
  return imports.filter(
    (entry) =>
      entry.dataset_type === key &&
      (locationId === null
        ? entry.location_id === null
        : entry.location_id === locationId),
  )
}
