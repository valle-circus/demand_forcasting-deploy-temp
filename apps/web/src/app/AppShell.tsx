import { Menu, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { ApiStatusLine } from '@/components/ApiStatusLine'
import { BrandMark } from '@/components/BrandMark'
import { ProposalBanner } from '@/components/ProposalBanner'
import { SideNavigation } from '@/components/SideNavigation'
import { Button } from '@/components/ui/button'
import { useAuth } from './auth/authContext'

function UserMenu() {
  const { user, signOut } = useAuth()

  return (
    <div className="flex items-center gap-3">
      <span
        className="hidden max-w-[16rem] truncate text-xs text-muted-foreground sm:block"
        title={user?.email ?? undefined}
      >
        {user?.email ?? 'Signed in'}
      </span>
      <Button variant="outline" size="sm" onClick={() => void signOut()}>
        Sign out
      </Button>
    </div>
  )
}

export function AppShell() {
  const location = useLocation()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const drawerRef = useRef<HTMLDivElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const mainRef = useRef<HTMLElement>(null)

  // Close the drawer on navigation and move focus to the new page, so keyboard
  // users are not left at the top of the shell.
  useEffect(() => {
    setDrawerOpen(false)
    mainRef.current?.focus()
  }, [location.pathname])

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
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-foreground focus:px-3 focus:py-2 focus:text-sm focus:text-background"
      >
        Skip to content
      </a>

      <ProposalBanner />

      <div className="lg:flex">
        <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col justify-between border-r border-border lg:flex">
          <div>
            <div className="px-4 py-4">
              <BrandMark />
            </div>
            <div className="px-2">
              <SideNavigation />
            </div>
          </div>
          <div className="border-t border-border px-3 py-3">
            <ApiStatusLine />
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-border bg-background/95 px-4 py-2.5 backdrop-blur sm:px-6">
            <Button
              ref={menuButtonRef}
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-expanded={drawerOpen}
              aria-controls="primary-navigation-drawer"
              onClick={() => {
                setDrawerOpen(true)
              }}
            >
              <Menu aria-hidden="true" />
              <span className="sr-only">Open navigation</span>
            </Button>
            <div className="lg:hidden">
              <BrandMark />
            </div>
            <div className="ml-auto">
              <UserMenu />
            </div>
          </header>

          <main
            id="main-content"
            ref={mainRef}
            tabIndex={-1}
            className="px-4 py-6 focus:outline-none sm:px-6"
          >
            <Outlet />
          </main>
        </div>
      </div>

      <AnimatePresence>
        {drawerOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.button
              type="button"
              aria-label="Close navigation"
              onClick={() => {
                setDrawerOpen(false)
                menuButtonRef.current?.focus()
              }}
              className="absolute inset-0 h-full w-full bg-foreground/20"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
            />
            <motion.div
              id="primary-navigation-drawer"
              ref={drawerRef}
              role="dialog"
              aria-modal="true"
              aria-label="Primary navigation"
              className="absolute inset-y-0 left-0 flex w-64 max-w-[85%] flex-col justify-between border-r border-border bg-background"
              // Small travel and a fast exit: leaving should get out of the way.
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            >
              <div>
                <div className="flex items-center justify-between px-4 py-4">
                  <BrandMark />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => {
                      setDrawerOpen(false)
                      menuButtonRef.current?.focus()
                    }}
                  >
                    <X aria-hidden="true" />
                    <span className="sr-only">Close navigation</span>
                  </Button>
                </div>
                <div className="px-2">
                  <SideNavigation
                    onNavigate={() => {
                      setDrawerOpen(false)
                    }}
                  />
                </div>
              </div>
              <div className="border-t border-border px-3 py-3">
                <ApiStatusLine />
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
