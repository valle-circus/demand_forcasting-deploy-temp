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
  workspace_id: string
  role: 'owner' | 'admin' | 'planner' | 'viewer'
  system_role: 'user' | 'system_admin'
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

  // --- v2 shelf-life and constraint evidence -------------------------------
  /** Which way pack/MOQ rounding moved the quantity. */
  rounding_direction: RoundingDirection
  /** When the proposed receipt is estimated to expire. */
  candidate_expiry_date: IsoDate | null
  /**
   * How that expiry was established. `policy_approximation` is a configured
   * anchor plus shelf-life days — it is **not** an exact lot MHD, and the UI
   * must never present it as one.
   */
  shelf_life_cap_basis: ShelfLifeCapBasis
  /** False when the forecast does not reach the candidate's expiry. */
  forecast_through_expiry: boolean
  /** Candidate quantity still on hand at expiry. Above zero implies waste risk. */
  projected_candidate_residual_at_expiry_g: Numeric | null
  max_cover_end_date: IsoDate | null
  forecast_through_max_cover: boolean
  binding_constraint: BindingConstraint
  /**
   * Whether a safe purchasable quantity exists. A hard cap may force a lower
   * multiple, or leave no safe positive order at all.
   */
  constraint_status: ConstraintStatus
}

export type RoundingDirection = 'none' | 'up' | 'down'

export type ShelfLifeCapBasis =
  | 'not_configured'
  | 'policy_approximation'
  | 'exact_lot_expiry'

export type BindingConstraint =
  | 'none'
  | 'shelf_life'
  | 'max_cover'
  | 'shelf_life_and_max_cover'

export type ConstraintStatus =
  | 'feasible'
  | 'reduced_to_safe_multiple'
  | 'no_safe_positive_order'

/**
 * Whether an item needs a decision **now**.
 *
 * This is the backend's classification against the item's own protection
 * horizon. A shortage after that horizon is a later replan, not current risk,
 * and `not_evaluated` means the evidence was incomplete — which is not the
 * same as covered.
 */
export type ActionableRiskStatus = 'at_risk' | 'covered' | 'not_evaluated'

/**
 * Whether accepted supply covers the item-specific protection window before
 * this run's unplaced proposal is counted. Computed by the Python backend.
 */
export type OrderRequirementStatus =
  | 'needs_order'
  | 'covered_without_order'
  | 'not_evaluated'

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

/** Item-level netting summary with separate pre- and post-proposal outcomes. */
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
  /**
   * First shortage anywhere in the uploaded forecast. Context only — a date
   * after the protection horizon is a later replan, not current risk. Use
   * `order_requirement_status` for the current ordering decision.
   */
  first_stockout_date: IsoDate | null
  unavoidable_pre_candidate_stockout_g: Numeric

  // --- v2 actionable risk ---------------------------------------------------
  /** End of the item's own protection horizon: lead time plus review cadence. */
  risk_horizon_end_date: IsoDate | null
  /** How far the evidence actually reached, which may fall short of the above. */
  risk_evaluated_through_date: IsoDate | null
  risk_horizon_fully_observed: boolean
  /** Historical name: this is the outcome after the proposal is included. */
  actionable_risk_status: ActionableRiskStatus
  first_stockout_within_horizon_date: IsoDate | null
  max_stockout_within_horizon_g: Numeric | null
  projected_balance_at_risk_horizon_end_g: Numeric | null

  // --- v3 event-aware supply coverage --------------------------------------
  //
  // Continuous calendar days from `projection_start_date`, counted against the
  // real dated forecast rather than an average. A day counts as covered only
  // when all of that day's demand is served; zero-demand days advance the
  // runway; same-day receipts arrive before demand; the first uncovered day is
  // excluded; and a receipt after an earlier gap does not heal the runway.
  //
  // Every field is null on a legacy v2 run. Null must never be coerced to zero.

  /** `1` for a row carrying this contract. Null or other means legacy. */
  coverage_contract_version: number | null

  /** Days served by usable opening stock alone. */
  on_hand_coverage_days: number | null
  on_hand_coverage_through_date: IsoDate | null
  on_hand_first_uncovered_date: IsoDate | null
  /** True means the day count is a lower bound: the forecast ended first. */
  on_hand_coverage_forecast_limited: boolean | null

  /** Same, after adding accepted open purchase orders. */
  with_open_po_coverage_days: number | null
  with_open_po_coverage_through_date: IsoDate | null
  with_open_po_first_uncovered_date: IsoDate | null
  with_open_po_coverage_forecast_limited: boolean | null

  /** Same, after also adding this run's proposed receipt. */
  with_proposal_coverage_days: number | null
  with_proposal_coverage_through_date: IsoDate | null
  with_proposal_first_uncovered_date: IsoDate | null
  with_proposal_coverage_forecast_limited: boolean | null

  /** Incremental segments — stack these directly, never subtract scenarios. */
  open_po_coverage_extension_days: number | null
  open_po_coverage_extension_status: CoverageExtensionStatus | null
  proposal_coverage_extension_days: number | null
  proposal_coverage_extension_status: CoverageExtensionStatus | null

  /** A receipt lands on or after an earlier gap, so it cannot bridge it. */
  open_po_receipts_at_or_after_gap: boolean | null
  proposal_receipts_at_or_after_gap: boolean | null

  /** Item-specific target span. Null when policy is not evaluable. */
  protection_horizon_days: number | null

  // --- backend read-model action classification ---------------------------
  /** Accepted stock + open POs only; the proposal is explicitly excluded. */
  order_requirement_status: OrderRequirementStatus
}

/**
 * How far an incremental coverage segment can be trusted.
 *
 * `not_observable` means the preceding scenario already covers the whole
 * uploaded forecast, so a stored zero must **not** be read as "adds nothing".
 */
export type CoverageExtensionStatus = 'exact' | 'lower_bound' | 'not_observable'

/**
 * The semantic contract for the coverage fields, returned once per run.
 *
 * The chart is gated on `available_for_all_items`; when
 * `requires_fresh_schema_v3_run` is true the run predates the contract and its
 * nulls are not zeroes.
 */
export interface CoverageContext {
  contract_version: number
  available_for_all_items: boolean
  requires_fresh_schema_v3_run: boolean
  calculation_owner: 'python_backend'
  unit: 'continuous_calendar_days'
  starts_on: string
  first_uncovered_day_is_excluded: boolean
  zero_closing_balance_is_covered: boolean
  same_day_receipts_arrive_before_demand: boolean
  forecast_limited_values_are_lower_bounds: boolean
  scenario_order: string[]
  proposal_is_not_an_order: boolean
  /** Both false today: lot-level MHD is not available for stock or open POs. */
  existing_inventory_lot_expiry_available: boolean
  open_po_lot_expiry_available: boolean
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
  /** Items that remain short after the proposed receipt is included. */
  items_at_risk: number
  /** Items whose accepted supply is insufficient before proposals are counted. */
  items_requiring_order: number
  /** Items whose evidence was incomplete. Distinct from covered. */
  items_risk_not_evaluated: number
  /** Covered now, but short later in the forecast. Context, not risk. */
  future_stockout_items: number
}

/**
 * The active policy behind one planning line, joined from the immutable master
 * version the run used. Supplied so the browser never has to infer lead time,
 * review cadence, or shelf-life settings from calculation dates.
 */
export interface PlanningLineExplanation {
  planning_line_id: string
  item: {
    item_id: string
    item_name: string
    storage_class: string
    pack_size_g: Numeric
    shelf_life_days: number | null
    min_safety_days: Numeric | null
    max_cover_days: Numeric | null
  } | null
  planning_policy: {
    item_type: string
    official_supplier: string | null
    ordering_channel: string | null
    supplier_id: string | null
    supplier_article_number: string | null
    packs_per_order_unit: Numeric | null
    order_unit: string | null
    lead_time_calendar_days: number | null
    shelf_life_anchor: string | null
    yield_factor: Numeric | null
    moq_order_units: Numeric | null
    case_multiple_order_units: Numeric | null
    data_status: string | null
    provenance: Provenance | null
  } | null
  delivery_rule: {
    delivery_rule_id: string
    ordering_channel: string | null
    storage_class: string
    delivery_weekday: number | null
    covered_service_weekdays: number[]
    order_weekday: number | null
    review_period_days: number | null
    effective_from: IsoDate
    effective_to: IsoDate | null
    data_status: string | null
    provenance: Provenance | null
  } | null
  protection_mode: string | null
  evidence_scope: Record<string, unknown>
}

/** Where each derived field came from, so the drawer can cite its sources. */
export interface ExplanationContext {
  calculation_owner: 'python_backend'
  master_data_version_id: string | null
  policy_version: string | null
  code_version: string | null
  field_lineage: Record<string, string[]>
  daily_projection_fields: string[]
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
  planning_line_explanations: PlanningLineExplanation[]
  explanation_context: ExplanationContext
  coverage_context: CoverageContext
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

export interface LocationViewResponse {
  locations: LocationsResponse
  status: PlanningStatusResponse
  inventory: InventoryResponse | null
  planning_run: PlanningRunResponse | null
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
  locations_at_risk: number
  /** Locations with at least one item still short after its proposal. */
  locations_requiring_order: number
  /** Items still short after the proposed receipt is included. */
  items_at_risk: number
  /** Items whose accepted supply is insufficient without the proposal. */
  items_requiring_order: number
  /** Incomplete evidence. Never fold this into risk, or into zero risk. */
  items_risk_not_evaluated: number
  recommendations_due: number
  blocking_issues: number
  open_purchase_order_lines: number
}

/**
 * One row per location, complete. The backend supplies names, timezones,
 * freshness and the earliest risk date, so Overview needs no per-location
 * follow-up requests and computes no dates of its own.
 */
export interface OverviewLocationRow {
  location_id: string
  location_name: string
  timezone: string
  ready: boolean
  items_at_risk: number
  items_requiring_order: number
  items_risk_not_evaluated: number
  earliest_risk_date: IsoDate | null
  earliest_order_required_date: IsoDate | null
  sources: PlanningStatusSources
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
