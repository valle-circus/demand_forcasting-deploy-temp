import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { clearResourceCache } from '../lib/resourceCache'

afterEach(() => {
  cleanup()
  clearResourceCache()
})
