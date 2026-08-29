import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Kept separate from vite.config.ts: tests render components but never need
// Tailwind's build pipeline, and excluding it keeps the suite fast.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    // Worker threads spawn far faster than forks on Windows, where the default
    // fork pool intermittently timed out waiting for workers to come up.
    pool: 'threads',
  },
})
