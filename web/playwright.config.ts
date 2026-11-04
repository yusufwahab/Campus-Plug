import { defineConfig } from "@playwright/test";

const widths = { mobile: 390, tablet: 768, desktop: 1440 } as const;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  // Journeys wait on the API, the job runner and page transitions; 5s is too tight on a busy laptop or CI runner.
  expect: { timeout: 15_000 },
  // Journeys share one seeded database, so run them one at a time for stable results.
  workers: 1,
  use: { baseURL: "http://localhost:3100" },
  webServer: [
    { command: "node scripts/start-e2e-api.mjs", url: "http://localhost:8100/healthz", reuseExistingServer: false, timeout: 120_000 },
    {
      // Built by scripts/e2e.mjs (npm run e2e) so the API URL is baked in.
      command: "npx next start -p 3100",
      url: "http://localhost:3100",
      reuseExistingServer: false,
      timeout: 300_000,
    },
  ],
  projects: Object.entries(widths).map(([name, width]) => ({
    name,
    use: { viewport: { width, height: name === "mobile" ? 844 : 900 }, browserName: "chromium" as const },
  })),
});
