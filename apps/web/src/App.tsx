import { useEffect, useState } from 'react'

import { StatusCard } from './components/StatusCard'
import { apiBaseUrl, fetchReadiness, type ReadinessResponse } from './lib/api'
import { browserSupabaseConfigured } from './lib/supabase'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'loaded'; data: ReadinessResponse }
  | { kind: 'error'; message: string }

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'The API readiness check failed.'
}

function App() {
  const [loadState, setLoadState] = useState<LoadState>({ kind: 'loading' })

  async function refreshReadiness() {
    setLoadState({ kind: 'loading' })
    try {
      const data = await fetchReadiness()
      setLoadState({ kind: 'loaded', data })
    } catch (error) {
      setLoadState({
        kind: 'error',
        message: errorMessage(error),
      })
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    void fetchReadiness(controller.signal)
      .then((data) => setLoadState({ kind: 'loaded', data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setLoadState({ kind: 'error', message: errorMessage(error) })
      })
    return () => controller.abort()
  }, [])

  const apiReady = loadState.kind === 'loaded'
  const supabaseStatus =
    loadState.kind === 'loaded' ? loadState.data.supabase.status : null

  return (
    <main className="min-h-screen bg-stone-100 text-stone-950">
      <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8 lg:py-14">
        <header className="overflow-hidden rounded-[2rem] bg-stone-950 px-6 py-8 text-stone-50 shadow-xl sm:px-10 sm:py-12">
          <div className="flex flex-col gap-8 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-3xl">
              <div className="mb-8 flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-lime-300 text-sm font-black text-stone-950">
                  P2
                </span>
                <span className="text-sm font-medium text-stone-300">
                  Internal planning tool
                </span>
              </div>
              <p className="text-sm font-semibold tracking-[0.2em] text-lime-300 uppercase">
                Prototype foundation
              </p>
              <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
                Supply planning, with the calculation kept in one place.
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-7 text-stone-300">
                This shell verifies the React, Render API, and Supabase
                boundaries. Upload and master-data workflows come in the next
                product slice.
              </p>
            </div>
            <div className="rounded-2xl border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm text-amber-100 sm:max-w-xs">
              Demo and proposal values remain non-operational until the
              maintainer approval gate passes.
            </div>
          </div>
        </header>

        <section className="mt-10" aria-labelledby="connection-heading">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-lime-700">Foundation</p>
              <h2 id="connection-heading" className="mt-1 text-2xl font-semibold">
                Connection overview
              </h2>
            </div>
            <button
              type="button"
              onClick={() => void refreshReadiness()}
              className="w-fit rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-800 transition hover:border-stone-500 hover:bg-stone-50 focus:ring-2 focus:ring-lime-600 focus:ring-offset-2 focus:outline-none"
            >
              Refresh status
            </button>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <StatusCard
              eyebrow="Render boundary"
              title="Python API"
              status={
                loadState.kind === 'loading'
                  ? 'Checking'
                  : apiReady
                    ? 'Connected'
                    : 'Unavailable'
              }
              tone={loadState.kind === 'loading' ? 'pending' : apiReady ? 'ready' : 'error'}
            >
              {loadState.kind === 'loaded' ? (
                <p>
                  {loadState.data.service} v{loadState.data.version} is running
                  in {loadState.data.environment}.
                </p>
              ) : loadState.kind === 'error' ? (
                <p>
                  {loadState.message} Check{' '}
                  <code className="rounded bg-stone-100 px-1 py-0.5">
                    VITE_API_BASE_URL
                  </code>
                  .
                </p>
              ) : (
                <p>Waiting for the readiness response.</p>
              )}
              <p className="mt-3 text-xs text-stone-500">
                API base: {apiBaseUrl || 'local Vite proxy'}
              </p>
            </StatusCard>

            <StatusCard
              eyebrow="Server persistence"
              title="Supabase"
              status={
                supabaseStatus === 'ready'
                  ? 'Connected'
                  : supabaseStatus === 'unavailable'
                    ? 'Needs attention'
                    : 'Not configured'
              }
              tone={
                supabaseStatus === 'ready'
                  ? 'ready'
                  : supabaseStatus === 'unavailable'
                    ? 'error'
                    : 'pending'
              }
            >
              <p>
                {loadState.kind === 'loaded'
                  ? loadState.data.supabase.message
                  : 'The API will report the server-side Supabase connection here.'}
              </p>
            </StatusCard>

            <StatusCard
              eyebrow="Browser authentication"
              title="Supabase Auth"
              status={browserSupabaseConfigured ? 'Configured' : 'Not configured'}
              tone={browserSupabaseConfigured ? 'ready' : 'pending'}
            >
              <p>
                {browserSupabaseConfigured
                  ? 'Browser-safe Supabase values are available for the future maintainer login.'
                  : 'Add the publishable URL and key in the Vercel environment when authentication is implemented.'}
              </p>
            </StatusCard>
          </div>
        </section>

        <section className="mt-10 grid gap-6 rounded-[2rem] border border-stone-200 bg-white p-6 shadow-sm sm:p-8 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="text-sm font-semibold text-lime-700">Next product slice</p>
            <h2 className="mt-2 text-2xl font-semibold">Thin maintainer workflow</h2>
            <p className="mt-4 text-sm leading-6 text-stone-600">
              Page structure, components, and interaction design are intentionally
              deferred. These are the contract-level capabilities the later UI
              will expose.
            </p>
          </div>
          <ol className="grid gap-3 sm:grid-cols-3">
            {[
              ['01', 'Upload', 'Select a location and provide the controlled planning inputs.'],
              ['02', 'Maintain', 'Edit a validated draft master-data version and activate it.'],
              ['03', 'Review', 'Inspect recommendations, derivations, and visible exceptions.'],
            ].map(([number, title, description]) => (
              <li key={number} className="rounded-2xl bg-stone-100 p-5">
                <span className="text-xs font-bold text-lime-700">{number}</span>
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">{description}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </main>
  )
}

export default App
