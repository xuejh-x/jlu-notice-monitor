import { defineConfig, devices } from '@playwright/test'

const backendUrl = 'http://127.0.0.1:8010'
const frontendUrl = 'http://127.0.0.1:4173'
const isCI = Boolean(process.env.CI)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  failOnFlakyTests: isCI,
  forbidOnly: isCI,
  workers: 1,
  retries: isCI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: frontendUrl,
    trace: isCI ? 'on-first-retry' : 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], ...(isCI ? {} : { channel: 'chrome' as const }) } }],
  webServer: [
    {
      command: 'node e2e/backend-server.mjs',
      url: `${backendUrl}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      env: { VITE_API_BASE_URL: backendUrl },
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
