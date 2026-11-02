import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = fileURLToPath(new URL(process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python", import.meta.url));

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:5174",
    headless: true,
    ...(process.platform === "win32" ? { channel: "chrome" } : {}),
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn self_improving_ai.dashboard.app:app --host 127.0.0.1 --port 8002`,
      env: {PYTHONPATH: `${root}/src`, PYTHONUTF8: "1"},
      url: "http://127.0.0.1:8002/api/health",
      reuseExistingServer: false,
    },
    {
      command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort`,
      env: {COMPONENT_A_API_TARGET:"http://127.0.0.1:8002"},
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
    },
  ],
});
