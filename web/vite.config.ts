/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    // Default 5000ms is occasionally too tight for an async waitFor() under
    // full-suite parallel load in this environment (individual tests run in
    // 1-2s in isolation; observed real-machine contention pushed the same
    // assertion past 5000ms running alongside the other test files) — not a
    // logic bug, just insufficient headroom for this sandbox's variable
    // import/environment setup cost.
    testTimeout: 15000,
  },
});
