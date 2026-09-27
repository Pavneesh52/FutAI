import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
// `vitest/config` re-exports Vite's defineConfig with the `test` block typed.
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // The default `forks` pool intermittently times out starting workers on Windows;
    // `threads` is faster to boot and behaves the same for these tests.
    pool: 'threads',
  },
})
