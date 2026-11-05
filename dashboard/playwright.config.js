import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    channel: process.env.PLAYWRIGHT_CHANNEL,
  },
  webServer: [
    {
      command: "cd .. && python3 -m uvicorn self_improving_ai.dashboard.app:app --port 8000",
      port: 8000,
      reuseExistingServer: true,
    },
    {
      command: "npm run dev",
      port: 5173,
      reuseExistingServer: true,
    },
  ],
});
