import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// React Testing Library's auto-cleanup relies on detecting a *global*
// `afterEach` (e.g. via vitest's `globals: true`). This project deliberately
// keeps `globals: false` (explicit imports in every test file, matching the
// project's explicitness-over-implicit-behavior preference — see
// vite.config.ts), so cleanup must be wired up explicitly here instead, or
// the DOM from one test leaks into the next.
afterEach(() => {
  cleanup();
});
