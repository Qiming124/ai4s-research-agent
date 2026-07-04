import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "on-first-retry",
  },
  webServer: {
    command:
      "cd ../.. && .venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000 --app-dir app",
    url: "http://127.0.0.1:8000/health",
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      DEEPSEEK_API_KEY: "sk-test-key-for-e2e",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
