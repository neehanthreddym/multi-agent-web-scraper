import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 60_000 },
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: "/tmp/catalog-playwright-results",
  use: {
    baseURL: process.env.UI_BASE_URL || "http://127.0.0.1:5173",
    browserName: "chromium",
    viewport: { width: 1365, height: 900 },
  },
});
