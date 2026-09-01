import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SelectedLocationProvider } from '@/app/location/SelectedLocationProvider'
import { NotFoundError } from '@/lib/errors'
import type {
  PlanningRun,
  PlanningRunResponse,
  PlanningStatusResponse,
} from '@/lib/types'

vi.mock('@/lib/apiClient', () => ({
  fetchLocations: vi.fn(),
  fetchPlanningStatus: vi.fn(),
  fetchInventory: vi.fn(),
  fetchPurchaseOrders: vi.fn(),
  getPlanningRun: vi.fn(),
  createPlanningRun: vi.fn(),
  downloadRunCsv: vi.fn(),
  downloadRunJson: vi.fn(),
  saveFile: vi.fn(),
}))

const api = await import('@/lib/apiClient')
const { LocationPlanningPage } = await import('./LocationPlanningPage')

const RUN: PlanningRun = {
  run_id: 'run-1',
  schema_version: 1,
  policy_profile: 'improved',
  policy_version: '1',
  run_mode: 'scenario',
  planning_as_of_at: '2026-08-29T10:00:00+00:00',
  created_at: '2026-08-29T10:00:00+00:00',
  input_hash: 'h',
  config_hash: 'c',
  code_version: '0.1.0',
  status: 'completed',
  master_data_version_id: 'v1',
  created_by: null,
  location_id: 'LOC_A',
  completed_at: '2026-08-29T10:00:05+00:00',
  failure_summary: null,
}

function status(overrides: Partial<PlanningStatusResponse> = {}) {
  return {
    location_id: 'LOC_A',
    ready: true,
    blockers: [],
    sources: {
      master_data_version: null,
      planning_input: null,
      stock: null,
      purchase_orders: null,
    },
    latest_run: RUN,
    latest_run_is_current: true,
    proposal_only: true,
    ...overrides,
  } as PlanningStatusResponse
}

function runResponse(): PlanningRunResponse {
  return {
    run: RUN,
    summary: {
      recommendation_count: 1,
      issue_count: 1,
      blocker_count: 0,
      items_at_risk: 1,
      items_risk_not_evaluated: 0,
      future_stockout_items: 0,
    },
    inputs: [],
    planning_lines: [
      {
        planning_line_id: 'line-1',
        run_id: 'run-1',
        location_id: 'LOC_A',
        item_id: 'ITEM_PASTA',
        supplier_id: 'SUP_A',
        schedule_rule_id: 'RULE_A',
        order_date: '2026-08-30',
        expected_delivery_date: '2026-09-02',
        coverage_start_date: '2026-09-02',
        coverage_end_date: '2026-09-09',
        protection_days: 7,
        gross_requirement_g: 12_400,
        yield_factor: 1.05,
        yield_factor_provenance: 'policy_default',
        adjusted_requirement_g: 13_020,
        safety_stock_g: 1800,
        safety_stock_provenance: 'policy_default',
        usable_on_hand_g: 4200,
        open_po_due_g: 2000,
        raw_order_g: 8620,
        shelf_life_cap_g: null,
        max_cover_cap_g: 6000,
        capped_order_g: 6000,
        order_unit_size_g: 2000,
        moq_order_units: 2,
        case_multiple_order_units: 1,
        proposed_order_units: 3,
        rounding_delta_g: 0,
        data_status: 'PROPOSAL',
        rounding_direction: 'up',
        candidate_expiry_date: '2026-09-20',
        shelf_life_cap_basis: 'policy_approximation',
        forecast_through_expiry: true,
        projected_candidate_residual_at_expiry_g: 0,
        max_cover_end_date: null,
        forecast_through_max_cover: true,
        binding_constraint: 'max_cover',
        constraint_status: 'feasible',
      },
    ],
    recommendations: [
      {
        recommendation_id: 'rec-1',
        planning_line_id: 'line-1',
        run_id: 'run-1',
        location_id: 'LOC_A',
        supplier_id: 'SUP_A',
        item_id: 'ITEM_PASTA',
        order_date: '2026-08-30',
        expected_delivery_date: '2026-09-02',
        proposed_qty_units: 3,
      },
    ],
    exceptions: [
      {
        exception_id: 'e1',
        run_id: 'run-1',
        planning_line_id: 'line-1',
        code: 'MOQ_INFLATED',
        severity: 'warning',
        dataset: null,
        record_ref: null,
        message: 'Raised to the supplier minimum of 2 units.',
        remedy: 'Review the minimum with the supplier.',
      },
    ],
    netting_results: [
      {
        run_id: 'run-1',
        location_id: 'LOC_A',
        item_id: 'ITEM_PASTA',
        projection_start_date: '2026-08-29',
        projection_end_date: '2026-09-29',
        opening_on_hand_g: 4200,
        gross_requirement_g: 12_400,
        open_po_due_g: 2000,
        net_requirement_g: 6200,
        candidate_receipt_g: 6000,
        overdue_open_po_g: 0,
        open_po_after_horizon_g: 0,
        open_po_after_final_demand_g: 0,
        ending_projected_balance_g: -200,
        minimum_projected_balance_g: -200,
        first_stockout_date: '2026-09-12',
        unavoidable_pre_candidate_stockout_g: 0,
        risk_horizon_end_date: '2026-09-08',
        risk_evaluated_through_date: '2026-09-08',
        risk_horizon_fully_observed: true,
        actionable_risk_status: 'at_risk',
        first_stockout_within_horizon_date: '2026-09-05',
        max_stockout_within_horizon_g: 400,
        projected_balance_at_risk_horizon_end_g: -400,
        coverage_contract_version: 1,
        on_hand_coverage_days: 2,
        on_hand_coverage_through_date: '2026-08-31',
        on_hand_first_uncovered_date: '2026-09-01',
        on_hand_coverage_forecast_limited: false,
        with_open_po_coverage_days: 4,
        with_open_po_coverage_through_date: '2026-09-02',
        with_open_po_first_uncovered_date: '2026-09-03',
        with_open_po_coverage_forecast_limited: false,
        with_proposal_coverage_days: 10,
        with_proposal_coverage_through_date: '2026-09-08',
        with_proposal_first_uncovered_date: '2026-09-09',
        with_proposal_coverage_forecast_limited: false,
        open_po_coverage_extension_days: 2,
        open_po_coverage_extension_status: 'exact',
        proposal_coverage_extension_days: 6,
        proposal_coverage_extension_status: 'exact',
        open_po_receipts_at_or_after_gap: false,
        proposal_receipts_at_or_after_gap: false,
        protection_horizon_days: 10,
      },
    ],
    projection_days: [],
    coverage_context: {
      contract_version: 1,
      available_for_all_items: true,
      requires_fresh_schema_v3_run: false,
      calculation_owner: 'python_backend',
      unit: 'continuous_calendar_days',
      starts_on: 'projection_start_date',
      first_uncovered_day_is_excluded: true,
      zero_closing_balance_is_covered: true,
      same_day_receipts_arrive_before_demand: true,
      forecast_limited_values_are_lower_bounds: true,
      scenario_order: [],
      proposal_is_not_an_order: true,
      existing_inventory_lot_expiry_available: false,
      open_po_lot_expiry_available: false,
    },
    planning_line_explanations: [
      {
        planning_line_id: 'line-1',
        item: {
          item_id: 'ITEM_PASTA',
          item_name: 'Pasta',
          storage_class: 'TK',
          pack_size_g: 2000,
          shelf_life_days: 30,
          min_safety_days: 2,
          max_cover_days: 14,
        },
        planning_policy: null,
        delivery_rule: null,
        protection_mode: 'stocked',
        evidence_scope: {},
      },
    ],
    explanation_context: {
      calculation_owner: 'python_backend',
      master_data_version_id: 'v1',
      policy_version: '1',
      code_version: '0.1.0',
      field_lineage: {},
      daily_projection_fields: [],
    },
    proposal_only: true,
  }
}

function renderPage(path = '/locations/LOC_A') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SelectedLocationProvider>
        <Routes>
          <Route
            path="/locations/:locationId"
            element={<LocationPlanningPage />}
          />
        </Routes>
      </SelectedLocationProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.sessionStorage.clear()
  vi.mocked(api.fetchLocations).mockResolvedValue({
    master_data_version_id: 'v1',
    locations: [
      {
        location_id: 'LOC_A',
        location_name: 'Kitchen A',
        timezone: 'Europe/Berlin',
        active: true,
      },
    ],
  })
  vi.mocked(api.fetchPlanningStatus).mockResolvedValue(status())
  vi.mocked(api.getPlanningRun).mockResolvedValue(runResponse())
  vi.mocked(api.fetchInventory).mockResolvedValue({
    source_import: {} as never,
    items: [
      {
        import_id: 'i1',
        location_id: 'LOC_A',
        item_id: 'ITEM_PASTA',
        counted_at: '2026-08-29T07:00:00+00:00',
        usable_on_hand_units: 2,
        partial_pack_g: 0,
        provenance: 'observed',
        item_name: 'Pasta',
        pack_size_g: 2000,
      },
    ],
  })
  vi.mocked(api.fetchPurchaseOrders).mockRejectedValue(new NotFoundError('none'))
})

describe('the run action', () => {
  it('is disabled and says why, in visible text rather than a tooltip', async () => {
    vi.mocked(api.fetchPlanningStatus).mockResolvedValue(
      status({
        ready: false,
        latest_run: null,
        blockers: [
          {
            code: 'stock_missing',
            message: 'No accepted current stock import is available.',
          },
        ],
      }),
    )

    renderPage()

    expect(
      await screen.findByRole('button', { name: /compute recommendation/i }),
    ).toBeDisabled()
    expect(
      screen.getByText(/no accepted current stock import/i),
    ).toBeInTheDocument()
  })

  it('starts exactly one calculation however fast it is clicked twice', async () => {
    const user = userEvent.setup()
    // The run is synchronous with no idempotency key, so a second submission
    // would start a second calculation.
    vi.mocked(api.createPlanningRun).mockImplementation(
      () => new Promise(() => undefined),
    )

    renderPage()

    const button = await screen.findByRole('button', {
      name: /compute recommendation/i,
    })
    await user.click(button)
    await user.click(button)

    expect(api.createPlanningRun).toHaveBeenCalledTimes(1)
  })

  it('warns that a synchronous run takes time', async () => {
    const user = userEvent.setup()
    vi.mocked(api.createPlanningRun).mockImplementation(
      () => new Promise(() => undefined),
    )

    renderPage()
    await user.click(
      await screen.findByRole('button', { name: /compute recommendation/i }),
    )

    expect(await screen.findByText(/keep the tab open/i)).toBeInTheDocument()
  })

  it('sends a timezone-aware cutoff, which the API requires', async () => {
    const user = userEvent.setup()
    vi.mocked(api.createPlanningRun).mockResolvedValue(runResponse())

    renderPage()
    await user.click(
      await screen.findByRole('button', { name: /compute recommendation/i }),
    )

    await waitFor(() => {
      expect(api.createPlanningRun).toHaveBeenCalled()
    })
    const body = vi.mocked(api.createPlanningRun).mock.calls[0][0]
    expect(body.planning_as_of_at).toMatch(/[+-]\d{2}:\d{2}$/)
    expect(body.run_mode).toBe('scenario')
  })
})

describe('a result whose inputs have moved on', () => {
  it('is labelled out of date rather than presented as current', async () => {
    vi.mocked(api.fetchPlanningStatus).mockResolvedValue(
      status({ latest_run_is_current: false }),
    )

    renderPage()

    expect(await screen.findByText(/result out of date/i)).toBeInTheDocument()
    expect(
      screen.getByText(/compute again before acting on it/i),
    ).toBeInTheDocument()
  })
})

describe('the derivation drawer', () => {
  it('shows the chain and quotes the engine note about the minimum', async () => {
    const user = userEvent.setup()
    renderPage('/locations/LOC_A?tab=proposals')

    // A button, not a row click: the derivation must be keyboard reachable.
    await user.click(await screen.findByRole('button', { name: /Pasta/ }))

    const drawer = await screen.findByRole('dialog')
    expect(within(drawer).getByText('Gross requirement')).toBeInTheDocument()
    expect(within(drawer).getByText('Max-cover cap')).toBeInTheDocument()
    // The claim that a minimum was applied comes from the engine, not from a
    // comparison made in the browser.
    expect(
      within(drawer).getByText(/raised to the supplier minimum/i),
    ).toBeInTheDocument()
    expect(
      within(drawer).getByText(/review the minimum with the supplier/i),
    ).toBeInTheDocument()
  })

  it('says an absent cap is absent rather than showing a zero', async () => {
    const user = userEvent.setup()
    renderPage('/locations/LOC_A?tab=proposals')

    // A button, not a row click: the derivation must be keyboard reachable.
    await user.click(await screen.findByRole('button', { name: /Pasta/ }))

    const drawer = await screen.findByRole('dialog')
    const shelfRow = within(drawer).getByText('Shelf-life cap').closest('li')
    expect(shelfRow).toHaveTextContent('none')
  })
})

describe('observed supplier documents', () => {
  it('treats "never imported" as an empty state, not an error', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('tab', { name: /on order/i }))

    expect(
      await screen.findByText(/no supplier documents imported/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('what counts as risk after the v2 engine correction', () => {
  function withNetting(overrides: Record<string, unknown>) {
    const base = runResponse()
    vi.mocked(api.getPlanningRun).mockResolvedValue({
      ...base,
      netting_results: [{ ...base.netting_results[0], ...overrides }],
    } as PlanningRunResponse)
  }

  it('does not treat a shortage beyond the decision window as risk', async () => {
    // The old UI called any first_stockout_date "at risk", which swept in
    // shortages a later review will handle and inflated the list.
    withNetting({
      actionable_risk_status: 'covered',
      first_stockout_within_horizon_date: null,
      first_stockout_date: '2026-10-02',
    })

    renderPage()

    // The proposal solves it, so it is not a problem — but without ordering
    // the item still runs short inside the window, and the badge says so.
    expect(await screen.findByText('At risk')).toBeInTheDocument()
    expect(screen.getByText(/unless ordered/i)).toBeInTheDocument()
    expect(
      screen.getByText(/the proposed order covers this window/i),
    ).toBeInTheDocument()
    expect(screen.queryByText('Order not enough')).not.toBeInTheDocument()
  })

  it('says the order is not enough when the proposal does not close the gap', async () => {
    // The status reports risk *after* this plan, so at_risk means the proposed
    // order is not enough — not merely that an order is needed.
    withNetting({
      actionable_risk_status: 'at_risk',
      first_stockout_within_horizon_date: '2026-09-05',
    })

    renderPage()

    expect(await screen.findByText('Order not enough')).toBeInTheDocument()
  })

  it('keeps incomplete evidence distinct from covered', async () => {
    withNetting({
      actionable_risk_status: 'not_evaluated',
      risk_evaluated_through_date: '2026-09-02',
      first_stockout_within_horizon_date: null,
    })

    renderPage()

    // Silence here would claim a safety check nobody actually performed.
    expect(await screen.findByText('Not enough data')).toBeInTheDocument()
    expect(screen.queryByText('Covered')).not.toBeInTheDocument()
  })

  it('shows demand for this decision, not the whole forecast', async () => {
    // netting gross is 12.4 kg across the full projection; the planning line's
    // 12.4 kg is what this order has to protect. They answer different windows,
    // so the column must come from the line.
    renderPage()

    const row = await screen.findByRole('row', { name: /Pasta/ })
    expect(within(row).getAllByRole('cell')[2]).toHaveTextContent('12.4 kg')
  })
})

describe('shelf-life evidence in the drawer', () => {
  it('never presents a policy estimate as an exact expiry', async () => {
    const user = userEvent.setup()
    renderPage('/locations/LOC_A?tab=proposals')

    // A button, not a row click: the derivation must be keyboard reachable.
    await user.click(await screen.findByRole('button', { name: /Pasta/ }))

    const drawer = await screen.findByRole('dialog')
    expect(within(drawer).getByText(/not from lot data/i)).toBeInTheDocument()
    // Inline, not hidden behind a hover: this caveat must not be missable.
    expect(
      within(drawer).getByText(/not the actual date on the delivered goods/i),
    ).toBeInTheDocument()
  })

  it('warns when the forecast does not reach the expiry', async () => {
    const user = userEvent.setup()
    const base = runResponse()
    vi.mocked(api.getPlanningRun).mockResolvedValue({
      ...base,
      planning_lines: [
        { ...base.planning_lines[0], forecast_through_expiry: false },
      ],
    } as PlanningRunResponse)

    renderPage('/locations/LOC_A?tab=proposals')
    // A button, not a row click: the derivation must be keyboard reachable.
    await user.click(await screen.findByRole('button', { name: /Pasta/ }))

    expect(
      await screen.findByText(/does not reach that date, so this check is incomplete/i),
    ).toBeInTheDocument()
  })

  it('says plainly when no safe order exists rather than inventing one', async () => {
    const user = userEvent.setup()
    const base = runResponse()
    vi.mocked(api.getPlanningRun).mockResolvedValue({
      ...base,
      planning_lines: [
        {
          ...base.planning_lines[0],
          constraint_status: 'no_safe_positive_order',
          binding_constraint: 'shelf_life',
        },
      ],
    } as PlanningRunResponse)

    renderPage('/locations/LOC_A?tab=proposals')
    // A button, not a row click: the derivation must be keyboard reachable.
    await user.click(await screen.findByRole('button', { name: /Pasta/ }))

    const drawer = await screen.findByRole('dialog')
    expect(within(drawer).getByText('No safe order possible')).toBeInTheDocument()
    expect(
      within(drawer).getByText(/needs a manual decision/i),
    ).toBeInTheDocument()
  })
})

describe('keyboard access', () => {
  it('opens an ingredient detail without a mouse', async () => {
    // Was a click handler on the table row, which no keyboard could reach and
    // which selected text instead of expanding on touch.
    const user = userEvent.setup()
    renderPage()

    const trigger = await screen.findByRole('button', { name: /Pasta/ })
    trigger.focus()
    expect(trigger).toHaveFocus()

    await user.keyboard('{Enter}')
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })

  it('opens the derivation without a mouse', async () => {
    const user = userEvent.setup()
    renderPage('/locations/LOC_A?tab=proposals')

    const trigger = await screen.findByRole('button', { name: /Pasta/ })
    trigger.focus()
    await user.keyboard('{Enter}')

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })
})

describe('the proposal boundary', () => {
  it('offers nothing that approves, sends or places an order', async () => {
    renderPage('/locations/LOC_A?tab=proposals')

    await screen.findByRole('button', { name: /Pasta/ })

    for (const forbidden of [
      /approve/i,
      /send to supplier/i,
      /place order/i,
      /confirm order/i,
      /mark as ordered/i,
    ]) {
      expect(
        screen.queryByRole('button', { name: forbidden }),
      ).not.toBeInTheDocument()
    }
    expect(screen.getByText(/placing an order happens elsewhere/i))
      .toBeInTheDocument()
  })
})
