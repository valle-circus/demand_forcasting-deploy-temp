import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SelectedLocationProvider } from '@/app/location/SelectedLocationProvider'
import { NotFoundError, ValidationError } from '@/lib/errors'
import type { MasterDataVersion, SourceImport } from '@/lib/types'

vi.mock('@/lib/apiClient', () => ({
  listImports: vi.fn(),
  listMasterVersions: vi.fn(),
  fetchLocations: vi.fn(),
  fetchPlanningStatus: vi.fn(),
  importMasterData: vi.fn(),
  importPlanningInput: vi.fn(),
  importStock: vi.fn(),
  importPurchaseOrders: vi.fn(),
  activateMasterVersion: vi.fn(),
}))

const api = await import('@/lib/apiClient')
const { DataSettingsPage } = await import('./DataSettingsPage')

function sourceImport(overrides: Partial<SourceImport> = {}): SourceImport {
  return {
    id: 'import-1',
    dataset_type: 'master_data',
    location_id: null,
    status: 'accepted',
    source_version: 'master-v1',
    source_as_of_at: null,
    coverage_start_date: null,
    coverage_end_date: null,
    file_names: ['Phase2_Master_Data_Template_v1.xlsx'],
    file_count: 1,
    total_bytes: 12_000,
    content_hash: 'hash',
    parser_version: 'template_xlsx-v1',
    record_count: 42,
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

function masterVersion(
  overrides: Partial<MasterDataVersion> = {},
): MasterDataVersion {
  return {
    id: 'version-1',
    environment: 'development',
    version_label: 'master-v1',
    status: 'draft',
    config_hash: 'cfg',
    source_note: null,
    created_at: '2026-08-29T09:00:00+00:00',
    created_by: null,
    activated_at: null,
    activated_by: null,
    source_import_id: 'import-1',
    ...overrides,
  }
}

function renderPage() {
  return render(
    <MemoryRouter>
      <SelectedLocationProvider>
        <DataSettingsPage />
      </SelectedLocationProvider>
    </MemoryRouter>,
  )
}

/** A brand-new environment: nothing imported, nothing active. */
function freshWorkspace() {
  vi.mocked(api.listImports).mockResolvedValue([])
  vi.mocked(api.listMasterVersions).mockResolvedValue([])
  vi.mocked(api.fetchLocations).mockRejectedValue(
    new NotFoundError("Active master-data version 'development' was not found."),
  )
}

function stepOne() {
  return screen.findByRole('region', { name: 'Master data & rules' })
}

async function uploadInto(region: HTMLElement, user: ReturnType<typeof userEvent.setup>) {
  await user.upload(
    within(region).getByLabelText(/choose a file/i),
    new File(['x'], 'master.xlsx'),
  )
  await user.click(within(region).getByRole('button', { name: /upload and check/i }))
}

beforeEach(() => {
  vi.clearAllMocks()
  window.sessionStorage.clear()
})

describe('a brand-new environment', () => {
  it('still renders, because this page is where the missing master data is fixed', async () => {
    freshWorkspace()
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Data & settings' }),
    ).toBeInTheDocument()
    // The 404 from /locations is expected here and must not blank the page.
    expect(
      screen.queryByRole('heading', { name: /could not be loaded/i }),
    ).not.toBeInTheDocument()
  })

  it('offers step 1 and explains why the other three are not available', async () => {
    freshWorkspace()
    renderPage()

    expect(
      within(await stepOne()).getByRole('button', { name: /upload and check/i }),
    ).toBeInTheDocument()

    for (const title of [
      'Forecast, menu & BOM',
      'Current stock',
      'Purchase-order PDFs',
    ]) {
      const card = screen.getByRole('region', { name: title })
      expect(
        within(card).getByText(/master-data version is active/i),
      ).toBeInTheDocument()
      expect(
        within(card).queryByRole('button', { name: /upload and check/i }),
      ).not.toBeInTheDocument()
      // A blocked step points at the step that unblocks it.
      expect(
        within(card).getByRole('button', { name: /go to step 1/i }),
      ).toBeInTheDocument()
    }
  })

  it('cannot scope a location upload before any location exists', async () => {
    freshWorkspace()
    renderPage()

    await stepOne()
    expect(screen.getByRole('combobox')).toBeDisabled()
  })
})

describe('activation completes step 1', () => {
  it('offers activation inside step 1 once a draft exists', async () => {
    // Activation used to live only in the version list far below, where it was
    // easy to miss — the journey stalls until it happens.
    vi.mocked(api.listImports).mockResolvedValue([sourceImport()])
    vi.mocked(api.listMasterVersions).mockResolvedValue([masterVersion()])
    vi.mocked(api.fetchLocations).mockRejectedValue(new NotFoundError('none'))

    renderPage()

    const master = await stepOne()
    expect(
      within(master).getByRole('button', {
        name: /activate master data and continue/i,
      }),
    ).toBeInTheDocument()
    expect(within(master).getByText('Draft ready')).toBeInTheDocument()
  })

  it('shows step 1 as active once a version is activated', async () => {
    vi.mocked(api.listImports).mockResolvedValue([sourceImport()])
    vi.mocked(api.listMasterVersions).mockResolvedValue([
      masterVersion({ status: 'active', activated_at: '2026-08-29T10:00:00+00:00' }),
    ])
    vi.mocked(api.fetchLocations).mockResolvedValue({
      master_data_version_id: 'version-1',
      locations: [
        {
          location_id: 'LOC_A',
          location_name: 'Kitchen A',
          timezone: 'Europe/Berlin',
          active: true,
        },
      ],
    })

    renderPage()

    const master = await stepOne()
    expect(within(master).getByText('Active')).toBeInTheDocument()
    expect(
      within(master).queryByRole('button', {
        name: /activate master data and continue/i,
      }),
    ).not.toBeInTheDocument()
  })

  it('confirms before activating, naming what is replaced', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listImports).mockResolvedValue([sourceImport()])
    vi.mocked(api.listMasterVersions).mockResolvedValue([
      masterVersion({ id: 'v2', version_label: 'master-v2', status: 'draft' }),
      masterVersion({ id: 'v1', version_label: 'master-v1', status: 'active' }),
    ])
    vi.mocked(api.fetchLocations).mockRejectedValue(new NotFoundError('none'))

    renderPage()

    await user.click(
      within(await stepOne()).getByRole('button', {
        name: /activate master data and continue/i,
      }),
    )

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent(/master-v2/)
    expect(dialog).toHaveTextContent(/replaces master-v1/i)
    expect(api.activateMasterVersion).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole('button', { name: 'Activate' }))

    await waitFor(() => {
      expect(api.activateMasterVersion).toHaveBeenCalledWith('v2')
    })
    expect(api.activateMasterVersion).toHaveBeenCalledTimes(1)
  })

  it('abandons activation on cancel', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listImports).mockResolvedValue([sourceImport()])
    vi.mocked(api.listMasterVersions).mockResolvedValue([masterVersion()])
    vi.mocked(api.fetchLocations).mockRejectedValue(new NotFoundError('none'))

    renderPage()

    await user.click(
      within(await stepOne()).getByRole('button', {
        name: /activate master data and continue/i,
      }),
    )
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', {
        name: 'Cancel',
      }),
    )

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    expect(api.activateMasterVersion).not.toHaveBeenCalled()
  })
})

describe('import outcomes', () => {
  it('reports a rejection as changing nothing, and shows the reason', async () => {
    const user = userEvent.setup()
    freshWorkspace()
    vi.mocked(api.importMasterData).mockRejectedValue(
      new ValidationError(
        "Sheet 'Items' is missing the required column 'pack_size_g'.",
        'validation_failed',
        { import_id: 'rejected-123' },
      ),
    )

    renderPage()
    const master = await stepOne()
    await uploadInto(master, user)

    const alert = await within(master).findByRole('alert')
    expect(alert).toHaveTextContent(/missing the required column/i)
    expect(alert).toHaveTextContent(/nothing was changed/i)
    // The rejected attempt is persisted server-side, so it stays auditable.
    expect(alert).toHaveTextContent(/rejected-123/)
  })

  it('does not present accepted-with-warnings as a plain success', async () => {
    const user = userEvent.setup()
    freshWorkspace()
    vi.mocked(api.importMasterData).mockResolvedValue(
      sourceImport({ id: 'new-import', status: 'accepted_with_warnings' }),
    )

    renderPage()
    const master = await stepOne()
    await uploadInto(master, user)

    expect(
      await within(master).findByText(/with warnings/i),
    ).toBeInTheDocument()
  })

  it('says so when an identical file was already imported', async () => {
    const user = userEvent.setup()
    freshWorkspace()
    // The API de-duplicates on content hash and returns the existing row, so
    // reporting a fresh import here would be a lie.
    vi.mocked(api.listImports).mockResolvedValue([sourceImport()])
    vi.mocked(api.importMasterData).mockResolvedValue(sourceImport())

    renderPage()
    const master = await stepOne()
    await uploadInto(master, user)

    expect(
      await within(master).findByText(/already imported/i),
    ).toBeInTheDocument()
  })

  it('shows each validation issue with the remedy the API supplied', async () => {
    freshWorkspace()
    const user = userEvent.setup()
    vi.mocked(api.listImports).mockResolvedValue([
      sourceImport({
        status: 'accepted_with_warnings',
        warning_count: 1,
        validation_issues: [
          {
            code: 'ITEM_MAPPING_MISSING',
            severity: 'warning',
            dataset: 'items',
            record_ref: 'ITEM_0042',
            message: 'Supplier article 883310 has no maintained item mapping.',
            remedy: 'Add the supplier article to the item mapping sheet.',
          },
        ],
      }),
    ])

    renderPage()
    const master = await stepOne()

    // Detail lives behind a disclosure rather than filling the card.
    await user.click(within(master).getByRole('button', { name: /details/i }))

    expect(
      await within(master).findByText(/no maintained item mapping/i),
    ).toBeInTheDocument()
    // A problem without a fix is not actionable.
    expect(
      within(master).getByText(/add the supplier article/i),
    ).toBeInTheDocument()
  })
})

describe('boundaries stated on the page', () => {
  it('states that uploading never runs planning', async () => {
    freshWorkspace()
    renderPage()

    await screen.findByRole('heading', { name: 'Data & settings' })
    expect(
      screen.getByText(/uploading never runs planning/i),
    ).toBeInTheDocument()
  })

  it('offers no way to edit observed stock or purchase-order lines', async () => {
    freshWorkspace()
    renderPage()

    await screen.findByRole('heading', { name: 'Maintained data' })
    expect(screen.getByText(/not edited here/i)).toBeInTheDocument()
  })

  it('shows unbuilt editors as planned rather than as controls that would fail', async () => {
    freshWorkspace()
    renderPage()

    await screen.findByRole('heading', { name: 'Maintained data' })

    for (const title of [
      'Items and policies',
      'Menu calendar',
      'Bill of materials',
    ]) {
      const heading = screen.getByRole('heading', { name: title })
      expect(heading).toBeInTheDocument()
      // No control at all beats a disabled one that implies it might work.
      expect(
        within(heading.closest('div')?.parentElement ?? document.body).queryByRole(
          'button',
        ),
      ).not.toBeInTheDocument()
    }
  })
})
