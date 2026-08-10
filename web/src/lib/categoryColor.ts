export type CategoryAccent = "error" | "warning" | "success" | "primary";

/**
 * A restrained accent by research/credit category — the same distress-
 * severity vocabulary used on the Distress Timeline and severity badges
 * (muted red for Chapter 11/default-type stress, amber for elevated/
 * restructuring-adjacent categories, muted green for post-emergence/
 * resolution) — so a category reads the same way everywhere it appears
 * (Research Universe cards, Issuer Detail membership chips) rather than
 * each page inventing its own color logic. Matches by name substring since
 * curated and system-detected names share vocabulary (e.g. "Chapter 11 /
 * Bankruptcy" and "System-Detected: Chapter 11").
 */
export function categoryAccentColor(name: string): CategoryAccent {
  if (/chapter 11|default|bankruptcy/i.test(name)) return "error";
  if (/going concern|refinancing|liability management|covenant/i.test(name)) return "warning";
  if (/post-emergence/i.test(name)) return "success";
  return "primary";
}
