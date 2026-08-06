import { describe, expect, it } from "vitest";
import {
  formatCompactCurrency,
  formatDate,
  formatDateTime,
  formatOrDash,
  formatPercent,
} from "./format";

describe("formatCompactCurrency", () => {
  it("formats billions", () => {
    expect(formatCompactCurrency("71340000000")).toBe("$71.3B");
  });

  it("formats millions", () => {
    expect(formatCompactCurrency("325000000")).toBe("$325.0M");
  });

  it("formats thousands", () => {
    expect(formatCompactCurrency("1500")).toBe("$1.5K");
  });

  it("formats small values without a suffix", () => {
    expect(formatCompactCurrency("500")).toBe("$500");
  });

  it("returns a dash for null", () => {
    expect(formatCompactCurrency(null)).toBe("—");
  });

  it("returns a dash for a non-numeric string rather than throwing", () => {
    expect(formatCompactCurrency("not-a-number")).toBe("—");
  });

  it("handles negative values", () => {
    expect(formatCompactCurrency("-2000000")).toBe("-$2.0M");
  });
});

describe("formatPercent", () => {
  it("formats to two decimal places", () => {
    expect(formatPercent("4.5")).toBe("4.50%");
  });

  it("returns a dash for null", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatDate", () => {
  it("formats an ISO date", () => {
    expect(formatDate("2029-06-15")).toBe("Jun 15, 2029");
  });

  it("returns a dash for null", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("returns a dash for an invalid date string", () => {
    expect(formatDate("not-a-date")).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("returns a dash for an invalid datetime string", () => {
    expect(formatDateTime("not-a-datetime")).toBe("—");
  });

  it("formats a valid ISO datetime without throwing", () => {
    expect(formatDateTime("2026-08-06T04:47:38.603954Z")).not.toBe("—");
  });
});

describe("formatOrDash", () => {
  it("passes through a non-null value", () => {
    expect(formatOrDash("Healthcare Services")).toBe("Healthcare Services");
  });

  it("returns a dash for null", () => {
    expect(formatOrDash(null)).toBe("—");
  });
});
