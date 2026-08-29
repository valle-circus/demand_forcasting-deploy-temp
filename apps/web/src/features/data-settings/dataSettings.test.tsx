import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SelectedLocationProvider } from '../../app/location/SelectedLocationProvider'
import { NotFoundError, ValidationError } from '../../lib/errors'
import type { MasterDataVersion, SourceImport } from '../../lib/types'

vi.mock('../../lib/apiClient', () => ({
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

const api = await import('../../lib/apiClient')
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

/** The state of a brand-new environment: nothing imported, nothing active. */
function freshWorkspace() {
  vi.mocked(api.listImports).mockResolvedValue([])
  vi.mocked(api.listMasterVersions).mockResolvedValue([])
  vi.mocked(api.fetchLocations).mockRejectedValue(
    new NotFoundError("Active master-data version 'development' was not found."),
  )
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
      await screen.findByRole('heading', { name: 'Planning inputs' }),
    ).toBeInTheDocument()
    // The 404 from /locations is expected here and must not blank the page.
    expect(
      screen.queryByRole('heading', { name: /could not be loaded/i }),
    ).not.toBeInTheDocument()
  })

  it('offers step 1 and explains why the other three are not available', async () => {
    freshWorkspace()
    renderPage()

    const master = await screen.findByRole('region', {
      name: 'Master data & rules',
    })
    expect(
      within(master).getByRole('button', { name: /upload and validate/i }),
    ).toBeInTheDocument()

    for (const title of [
      'Forecast, menu & BOM',
      'Current stock',
      'Purchase-order PDFs',
    ]) {
      const card = screen.getByRole('region', { name: title })
      expect(within(card).getByText(/not available yet/i)).toBeInTheDocument()
      expect(
        within(card).getByText(/master-data version is active/i),
      ).toBeInTheDocument()
      expect(
        within(card).queryByRole('button', { name: /upload and validate/i }),
      ).not.toBeInTheDocument()
    }
  })

  it('says the location selector is empty because no master version is active', async () => {
    freshWorkspace()
    renderPage()

    const select = await screen.findByLabelText(/location for steps 3 and 4/i)
    expect(select).toBeDisabled()
    expect(select).toHaveTextContent(/no locations until a master version/i)
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

    const master = await screen.findByRole('region', {
      name: 'Master data & rules',
    })
    const input = within(master).getByLabelText(/choose file/i)
    await user.upload(
      input,
      new File(['x'], 'master.xlsx', { type: 'application/vnd.ms-excel' }),
    )
    await user.click(
      within(master).getByRole('button', { name: /upload and validate/i }),
    )

    const alert = await within(master).findByRole('alert')
    expect(alert).toHaveTextContent(/rejected — nothing was changed/i)
    expect(alert).toHaveTextContent(/missing the required column/i)
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

    const master = await screen.findByRole('region', {
      name: 'Master data & rules',
    })
    await user.upload(
      within(master).getByLabelText(/choose file/i),
      new File(['x'], 'master.xlsx'),
    )
    await user.click(
      within(master).getByRole('button', { name: /upload and validate/i }),
    )

    expect(
      await within(master).findByText(/accepted, with warnings to review/i),
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

    const master = await screen.findByRole('region', {
      name: 'Master data & rules',
    })
    await user.upload(
      within(master).getByLabelText(/choose file/i),
      new File(['x'], 'master.xlsx'),
    )
    await user.click(
      within(master).getByRole('button', { name: /upload and validate/i }),
    )

    expect(
      await within(master).findByText(/already imported/i),
    ).toBeInTheDocument()
  })

  it('shows every validation issue with the remedy the API supplied', async () => {
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

    const master = await screen.findByRole('region', {
      name: 'Master data & rules',
    })
    await user.click(within(master).getByRole('button', { name: /review 1 issue/i }))

    expect(
      await within(master).findByText(/no maintained item mapping/i),
    ).toBeInTheDocument()
    // A problem without a fix is not actionable.
    expect(within(master).getByText(/how to fix/i)).toBeInTheDocument()
    expect(
      within(master).getByText(/add the supplier article/i),
    ).toBeInTheDocument()
  })
})

describe('uploading versus running', () => {
  it('states that uploading never runs planning', async () => {
    freshWorkspace()
    renderPage()

    await screen.findByRole('heading', { name: 'Planning inputs' })
    expect(
      screen.getAllByText(/uploading never runs planning/i).length,
    ).toBeGreaterThan(0)
  })

  it('offers no way to edit observed stock or purchase-order lines', async () => {
    freshWorkspace()
    renderPage()

    await screen.findByRole('heading', { name: 'Maintained data & rules' })
    expect(
      screen.getByText(/never edited here/i),
    ).toBeInTheDocument()
  })
})

describe('activating a master version', () => {
  beforeEach(() => {
    vi.mocked(api.listImports).mockResolvedValue([sourceImport()])
    vi.mocked(api.fetchLocations).mockRejectedValue(new NotFoundError('none'))
    vi.mocked(api.listMasterVersions).mockResolvedValue([
      masterVersion({ id: 'v2', version_label: 'master-v2', status: 'draft' }),
      masterVersion({
        id: 'v1',
        version_label: 'master-v1',
        status: 'active',
        activated_at: '2026-08-28T09:00:00+00:00',
      }),
    ])
  })

  it('requires confirmation and names the version being replaced', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(
      await screen.findByRole('button', { name: 'Activate' }),
    )

    const dialog = await screen.findByRole('dialog', {
      name: /activate master-v2/i,
    })
    // The maintainer must see what they are displacing before confirming.
    expect(dialog).toHaveTextContent(/master-v1 will be replaced/i)
    expect(dialog).toHaveTextContent(/past results stay reproducible/i)
    expect(api.activateMasterVersion).not.toHaveBeenCalled()
  })

  it('activates only the confirmed version', async () => {
    const user = userEvent.setup()
    vi.mocked(api.activateMasterVersion).mockResolvedValue({
      id: 'v2',
      environment: 'development',
      version_label: 'master-v2',
      status: 'active',
      activated_at: '2026-08-29T10:00:00+00:00',
      activated_by: 'user-1',
    })

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Activate' }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', {
        name: 'Activate',
      }),
    )

    await waitFor(() => {
      expect(api.activateMasterVersion).toHaveBeenCalledWith('v2')
    })
    expect(api.activateMasterVersion).toHaveBeenCalledTimes(1)
  })

  it('abandons activation on cancel', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Activate' }))
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

  it('offers no activate control for the version already active', async () => {
    renderPage()

    await screen.findByRole('heading', { name: /master-data versions/i })
    // Only the draft can be activated.
    expect(screen.getAllByRole('button', { name: 'Activate' })).toHaveLength(1)
  })
})

describe('maintained-data editors that are not built', () => {
  it('shows them as planned rather than offering controls that would fail', async () => {
    freshWorkspace()
    renderPage()

    await screen.findByRole('heading', { name: 'Maintained data & rules' })

    for (const title of [
      'Items & item policies',
      'Menu calendar',
      'Bill of materials',
    ]) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    }
    for (const button of screen.getAllByRole('button', {
      name: /not available yet/i,
    })) {
      expect(button).toBeDisabled()
    }
  })
})
