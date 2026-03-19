import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests for DB Analyzer v7.
 * Prerequisites: start backend (python run_api.py) and frontend (npm run dev) before running.
 * Default: backend 8004, frontend 3000. Override with BASE_URL if needed.
 */
export default defineConfig({
  testDir: ".",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  timeout: 30_000,
  expect: { timeout: 10_000 },
});
