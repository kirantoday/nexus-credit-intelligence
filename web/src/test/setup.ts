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

// jsdom doesn't implement `window.matchMedia` at all — MUI's `useMediaQuery`
// (the mobile-responsive hook, `useIsMobile`) would throw without this.
// Defaults to "no match" (desktop/wide-viewport behavior), preserving every
// existing test's assumptions unchanged; a test that specifically needs to
// simulate a narrow viewport overrides `window.matchMedia` itself (see
// Layout.test.tsx for the pattern).
window.matchMedia =
  window.matchMedia ||
  function matchMediaMock(query: string): MediaQueryList {
    return {
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    } as MediaQueryList;
  };
