import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { ApiStatusLine } from '../components/ApiStatusLine'
import { BrandMark } from '../components/BrandMark'
import { ProposalBanner } from '../components/ProposalBanner'
import { SideNavigation } from '../components/SideNavigation'
import { useAuth } from './auth/authContext'

function pageTitle(pathname: string): string {
  if (pathname.startsWith('/locations')) {
    return 'Location planning'
  }
  if (pathname.startsWith('/data')) {
    return 'Data & settings'
  }
  return 'Overview'
}

function SidebarFooter() {
  return (
    <div className="space-y-3 border-t border-stone-800 px-3 py-4">
      <ApiStatusLine variant="dark" />
    </div>
  )
}

function UserMenu() {
  const { user, signOut } = useAuth()

  return (
    <div className="flex items-center gap-3">
      <span
        className="hidden max-w-[16rem] truncate text-xs text-stone-600 sm:block"
        title={user?.email ?? undefined}
      >
        {user?.email ?? 'Signed in'}
      </span>
      <button
        type="button"
        onClick={() => void signOut()}
        className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-semibold text-stone-700 transition hover:border-stone-400 hover:bg-stone-50 focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:outline-none"
      >
        Sign out
      </button>
    </div>
  )
}

export function AppShell() {
  const location = useLocation()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const drawerRef = useRef<HTMLDivElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const mainRef = useRef<HTMLElement>(null)

  const title = pageTitle(location.pathname)

  // Close the drawer on navigation, and move focus to the new page content so
  // keyboard and screen-reader users are not left at the top of the shell.
  useEffect(() => {
    setDrawerOpen(false)
    mainRef.current?.focus()
  }, [location.pathname])

  // Escape closes the drawer and returns focus to the control that opened it.
  useEffect(() => {
    if (!drawerOpen) {
      return
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setDrawerOpen(false)
        menuButtonRef.current?.focus()
        return
      }
      if (event.key !== 'Tab') {
        return
      }
      // Keep Tab inside the drawer while it covers the page.
      const focusable = drawerRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled])',
      )
      if (!focusable || focusable.length === 0) {
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [drawerOpen])

  useEffect(() => {
    if (drawerOpen) {
      drawerRef.current?.querySelector<HTMLElement>('button, a[href]')?.focus()
    }
  }, [drawerOpen])

  return (
    <div className="min-h-screen bg-stone-100 text-stone-950">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-stone-950 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-stone-50"
      >
        Skip to main content
      </a>

      <ProposalBanner />

      <div className="lg:flex">
        {/* Persistent navigation on desktop. */}
        <aside className="hidden lg:flex lg:h-[calc(100vh-2.25rem)] lg:w-64 lg:shrink-0 lg:flex-col lg:justify-between lg:overflow-y-auto lg:border-r lg:border-stone-800 lg:bg-stone-950 lg:sticky lg:top-0">
          <div>
            <div className="px-5 py-5">
              <BrandMark />
            </div>
            <div className="px-3">
              <SideNavigation />
            </div>
          </div>
          <SidebarFooter />
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 border-b border-stone-200 bg-white/95 backdrop-blur">
            <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <button
                  type="button"
                  ref={menuButtonRef}
                  onClick={() => {
                    setDrawerOpen(true)
                  }}
                  aria-expanded={drawerOpen}
                  aria-controls="primary-navigation-drawer"
                  className="rounded-lg border border-stone-300 p-2 text-stone-700 transition hover:bg-stone-50 focus-visible:ring-2 focus-visible:ring-lime-600 focus-visible:outline-none lg:hidden"
                >
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    className="size-5"
                  >
                    <path d="M4 7h16M4 12h16M4 17h16" />
                  </svg>
                  <span className="sr-only">Open navigation</span>
                </button>
                <h1 className="truncate text-lg font-semibold tracking-tight">
                  {title}
                </h1>
              </div>
              <UserMenu />
            </div>
          </header>

          <main
            id="main-content"
            ref={mainRef}
            tabIndex={-1}
            className="px-4 py-6 focus:outline-none sm:px-6 lg:px-8"
          >
            <Outlet />
          </main>
        </div>
      </div>

      {/* Small-screen drawer. */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => {
              setDrawerOpen(false)
              menuButtonRef.current?.focus()
            }}
            className="absolute inset-0 h-full w-full bg-stone-950/50"
          />
          <div
            id="primary-navigation-drawer"
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Primary navigation"
            className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col justify-between bg-stone-950"
          >
            <div>
              <div className="flex items-center justify-between px-5 py-5">
                <BrandMark />
                <button
                  type="button"
                  onClick={() => {
                    setDrawerOpen(false)
                    menuButtonRef.current?.focus()
                  }}
                  className="rounded-lg p-1.5 text-stone-400 transition hover:bg-stone-800 hover:text-stone-100 focus-visible:ring-2 focus-visible:ring-lime-400 focus-visible:outline-none"
                >
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    className="size-5"
                  >
                    <path d="M6 6l12 12M18 6 6 18" />
                  </svg>
                  <span className="sr-only">Close navigation</span>
                </button>
              </div>
              <div className="px-3">
                <SideNavigation
                  onNavigate={() => {
                    setDrawerOpen(false)
                  }}
                />
              </div>
            </div>
            <SidebarFooter />
          </div>
        </div>
      )}
    </div>
  )
}
