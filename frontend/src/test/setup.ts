import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Mock ResizeObserver for Recharts ResponsiveContainer
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock scrollIntoView for chat panel
window.HTMLElement.prototype.scrollIntoView = vi.fn()

// Testing Library only auto-cleans when the test globals are enabled, and this project
// imports from 'vitest' explicitly instead. So clean up by hand.
afterEach(() => {
  cleanup()
})
