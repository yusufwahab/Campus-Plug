import { defineConfig } from "@playwright/test";

const widths = { mobile: 390, tablet: 768, desktop: 1440 } as const;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  use: { baseURL: "http://localhost:3100" },
  webServer: {
    command: "npm run build && npx next start -p 3100",
    url: "http://localhost:3100",
    reuseExistingServer: true,
    timeout: 300_000,
  },
  projects: Object.entries(widths).map(([name, width]) => ({
    name,
    use: { viewport: { width, height: name === "mobile" ? 844 : 900 }, browserName: "chromium" as const },
  })),
});
