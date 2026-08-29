/**
 * Response shapes for the Supply Planning API.
 *
 * These mirror `apps/api/supply_planning_api/` and the Supabase migrations.
 * They are read models only: the browser formats these values, it never
 * recalculates planning or KPI semantics from them.
 *
 * Numeric columns arrive from PostgREST and Python `Decimal` serialization,
 * which can yield either a JSON number or a decimal string depending on the
 * path a value took. Use `toNumber()` from `formatting.ts` rather than
 * assuming one or the other.
 */

export type Numeric = number | string

/** ISO-8601 timestamp with a timezone offset, e.g. `2026-08-29T09:12:00+00:00`. */
export type IsoDateTime = string

/** ISO-8601 calendar date, e.g. `2026-08-29`. */
export type IsoDate = string

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------

export type DependencyStatus = 'ready' | 'not_configured' | 'unavailable'

export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
  environment: string
}

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

// ---------------------------------------------------------------------------
// Identity
// ---------------------------------------------------------------------------

export interface UserResponse {
  user_id: string
  email: string | null
  role: 'maintainer'
}

// ---------------------------------------------------------------------------
// Shared vocabulary
// ---------------------------------------------------------------------------

/**
 * Provenance of a value, per journey doc §8. Rendered as plain language with
 * the canonical value available in a tooltip.
 */
export type Provenance =
  | 'observed'
  | 'manual'
  | 'policy_default'
  | 'empty_placeholder'
  | 'unavailable'

export type IssueSeverity = 'blocker' | 'warning' | 'info'

/**
 * A validation or planning issue. `remedy` is always present, which is what
 * lets the UI guarantee that every surfaced problem carries an action.
 */
export interface ValidationIssue {
  code: string
  severity: IssueSeverity
  dataset: string | null
  record_ref: string | null
  message: string
  remedy: string
}

// ---------------------------------------------------------------------------
// Locations
// ---------------------------------------------------------------------------

export interface LocationSummary {
  location_id: string
  location_name: string
  timezone: string
  active: boolean
}

/**
 * Note: only *active* locations are returned. A 404 from this endpoint means
 * no active master-data version exists for the API's environment yet — the
 * first-run state, not an error.
 */
export interface LocationsResponse {
  master_data_version_id: string
  locations: LocationSummary[]
}

// ---------------------------------------------------------------------------
// Source imports
// ---------------------------------------------------------------------------

export type DatasetType =
  | 'master_data'
  | 'planning_input'
  | 'stock'
  | 'purchase_orders'

export type ImportStatus =
  | 'received'
  | 'validating'
  | 'accepted'
  | 'accepted_with_warnings'
  | 'rejected'

export interface SourceImport {
  id: string
  dataset_type: DatasetType
  location_id: string | null
  status: ImportStatus
  source_version: string
  /** When the source system produced the data — not when it was uploaded. */
  source_as_of_at: IsoDateTime | null
  coverage_start_date: IsoDate | null
  coverage_end_date: IsoDate | null
  file_names: string[]
  file_count: number
  total_bytes: number
  content_hash: string
  parser_version: string
  record_count: number
  warning_count: number
  error_count: number
  validation_issues: ValidationIssue[]
  metadata: Record<string, unknown>
  supersedes_import_id: string | null
  /** When this import was accepted by the API — not the source timestamp. */
  created_at: IsoDateTime
  created_by: string | null
}

// ---------------------------------------------------------------------------
// Master data versions
// ---------------------------------------------------------------------------

export type MasterVersionStatus = 'draft' | 'active' | 'archived'

export interface MasterDataVersion {
  id: string
  environment: string
  version_label: string
  status: MasterVersionStatus
  config_hash: string | null
  source_note: string | null
  created_at: IsoDateTime
  created_by: string | null
  activated_at: IsoDateTime | null
  activated_by: string | null
  source_import_id: string | null
}

export interface ActivationResponse {
  id: string
  environment: string
  version_label: string
  status: 'active'
  activated_at: IsoDateTime
  activated_by: string
}

// ---------------------------------------------------------------------------
// Planning runs
// ---------------------------------------------------------------------------

export type RunMode = 'fixture' | 'scenario' | 'shadow' | 'production'
export type RunStatus = 'started' | 'completed' | 'blocked' | 'failed'

export interface PlanningRun {
  run_id: string
  schema_version: number
  policy_profile: string
  policy_version: string
  run_mode: RunMode
  planning_as_of_at: IsoDateTime
  created_at: IsoDateTime
  input_hash: string
  config_hash: string
  code_version: string
  status: RunStatus
  master_data_version_id: string | null
  created_by: string | null
  location_id: string
  completed_at: IsoDateTime | null
  failure_summary: string | null
}

export interface PlanningRunInput {
  run_id: string
  dataset: string
  source_version: string
  content_hash: string
  provenance: Provenance
  record_count: number
  source_import_id: string | null
}

/**
 * One derivation chain. Every field the recommendation drawer shows is read
 * from here — the browser formats, it never recomputes.
 */
export interface PlanningLine {
  planning_line_id: string
  run_id: string
  location_id: string
  item_id: string
  supplier_id: string
  schedule_rule_id: string
  order_date: IsoDate
  expected_delivery_date: IsoDate
  coverage_start_date: IsoDate | null
  coverage_end_date: IsoDate | null
  protection_days: number
  gross_requirement_g: Numeric
  yield_factor: Numeric
  yield_factor_provenance: Provenance
  adjusted_requirement_g: Numeric
  safety_stock_g: Numeric
  safety_stock_provenance: Provenance
  usable_on_hand_g: Numeric
  open_po_due_g: Numeric
  raw_order_g: Numeric
  shelf_life_cap_g: Numeric | null
  max_cover_cap_g: Numeric | null
  capped_order_g: Numeric
  order_unit_size_g: Numeric
  moq_order_units: Numeric
  case_multiple_order_units: Numeric
  proposed_order_units: Numeric
  rounding_delta_g: Numeric
  data_status: string
}

export interface PlanningRecommendation {
  recommendation_id: string
  planning_line_id: string
  run_id: string
  location_id: string
  supplier_id: string
  item_id: string
  order_date: IsoDate
  expected_delivery_date: IsoDate
  proposed_qty_units: Numeric
}

export interface PlanningException {
  exception_id: string
  run_id: string
  planning_line_id: string | null
  code: string
  severity: IssueSeverity
  dataset: string | null
  record_ref: string | null
  message: string
  remedy: string
}

/** Item-level netting summary. `first_stockout_date` drives risk severity. */
export interface NettingResult {
  run_id: string
  location_id: string
  item_id: string
  projection_start_date: IsoDate
  projection_end_date: IsoDate
  opening_on_hand_g: Numeric
  gross_requirement_g: Numeric
  open_po_due_g: Numeric
  net_requirement_g: Numeric
  candidate_receipt_g: Numeric
  overdue_open_po_g: Numeric
  open_po_after_horizon_g: Numeric
  open_po_after_final_demand_g: Numeric
  ending_projected_balance_g: Numeric
  minimum_projected_balance_g: Numeric
  first_stockout_date: IsoDate | null
  unavoidable_pre_candidate_stockout_g: Numeric
}

export interface ProjectionDay {
  run_id: string
  location_id: string
  item_id: string
  projection_date: IsoDate
  opening_balance_g: Numeric
  demand_g: Numeric
  open_po_receipts_g: Numeric
  candidate_receipts_g: Numeric
  closing_balance_g: Numeric
  stockout_g: Numeric
}

export interface PlanningRunSummary {
  recommendation_count: number
  issue_count: number
  blocker_count: number
  items_at_risk: number
}

export interface PlanningRunResponse {
  run: PlanningRun
  summary: PlanningRunSummary
  inputs: PlanningRunInput[]
  planning_lines: PlanningLine[]
  recommendations: PlanningRecommendation[]
  exceptions: PlanningException[]
  netting_results: NettingResult[]
  /** Every item × every horizon day. Render lazily, per opened item only. */
  projection_days: ProjectionDay[]
  proposal_only: true
}

export interface CreatePlanningRunRequest {
  location_id: string
  /** Must include a timezone offset; the API rejects naive timestamps. */
  planning_as_of_at: IsoDateTime
  run_mode: 'scenario'
  master_data_version_id?: string
  planning_input_import_id?: string
  stock_import_id?: string
  purchase_orders_import_id?: string
}

// ---------------------------------------------------------------------------
// Location planning status
// ---------------------------------------------------------------------------

export type BlockerCode =
  | 'master_missing'
  | 'planning_input_missing'
  | 'stock_missing'
  | 'purchase_orders_missing'

export interface PlanningBlocker {
  code: BlockerCode | string
  message: string
}

export interface PlanningStatusSources {
  master_data_version: MasterDataVersion | null
  planning_input: SourceImport | null
  stock: SourceImport | null
  purchase_orders: SourceImport | null
}

export interface PlanningStatusResponse {
  location_id: string
  ready: boolean
  blockers: PlanningBlocker[]
  sources: PlanningStatusSources
  latest_run: PlanningRun | null
  /**
   * False when a newer accepted input exists than the one the latest run used.
   * Drives the "stale calculation" label — never recompute this in the browser.
   */
  latest_run_is_current: boolean
  proposal_only: true
}

// ---------------------------------------------------------------------------
// Inventory and purchase orders
// ---------------------------------------------------------------------------

export interface InventoryItem {
  import_id: string
  location_id: string
  item_id: string
  counted_at: IsoDateTime
  usable_on_hand_units: Numeric
  partial_pack_g: Numeric
  provenance: Provenance
  /** Joined from the active master version by the API. */
  item_name: string
  pack_size_g: Numeric
}

export interface InventoryResponse {
  source_import: SourceImport
  items: InventoryItem[]
}

export type PoDerivedStatus = 'open' | 'closed' | 'undated'

export type PoMappingStatus =
  | 'mapped'
  | 'unmapped'
  | 'description_mismatch'
  | 'ambiguous'

export interface PurchaseOrderLine {
  import_id: string
  po_line_id: string
  po_id: string
  location_id: string
  supplier_id: string
  supplier_article_number: string
  supplier_description: string
  item_id: string | null
  ordered_at: IsoDateTime
  /** The supplier's `Liefertag`. Null lines are quarantined from netting. */
  expected_receipt_at: IsoDateTime | null
  ordered_qty_order_units: Numeric
  open_qty_units: Numeric | null
  package_content_units: Numeric | null
  source_base_unit_code: string | null
  line_total_eur: Numeric | null
  derived_status: PoDerivedStatus
  mapping_status: PoMappingStatus
  mapping_message: string | null
  provenance: Provenance
}

export interface PurchaseOrdersResponse {
  source_import: SourceImport
  summary: {
    document_count: number
    open_line_count: number
    unmapped_line_count: number
  }
  lines: PurchaseOrderLine[]
  /** Always true: these lines come from imported PDFs, not live confirmation. */
  observed_not_supplier_confirmation: true
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

export interface OverviewKpis {
  locations_ready: number
  locations_total: number
  /** Only counted when the location's latest run is current. */
  items_at_risk: number
  /** Only counted when the location's latest run is current. */
  recommendations_due: number
  blocking_issues: number
  open_purchase_order_lines: number
}

export interface OverviewLocationRow {
  location_id: string
  ready: boolean
  items_at_risk: number
  latest_run: PlanningRun | null
  latest_run_is_current: boolean
  blockers: PlanningBlocker[]
}

export interface OverviewResponse {
  as_of_date: IsoDate
  kpis: OverviewKpis
  latest_run_at: IsoDateTime | null
  locations: OverviewLocationRow[]
  proposal_only: true
}
