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
      },
    ],
    projection_days: [],
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

    await user.click(await screen.findByRole('cell', { name: 'Pasta' }))

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

    await user.click(await screen.findByRole('cell', { name: 'Pasta' }))

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

describe('the proposal boundary', () => {
  it('offers nothing that approves, sends or places an order', async () => {
    renderPage('/locations/LOC_A?tab=proposals')

    await screen.findByRole('cell', { name: 'Pasta' })

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
