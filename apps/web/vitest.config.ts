import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Kept separate from vite.config.ts: tests render components but never need
// Tailwind's build pipeline, and excluding it keeps the suite fast. The `@`
// alias must be repeated here — a separate config does not inherit it.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
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
