import { createTheme } from "@mui/material/styles";

/**
 * Institutional credit-intelligence design system (CFO-demo visual polish
 * pass). Centralizing color/typography/component defaults here — rather
 * than per-page overrides — is what lets one palette change (e.g. a muted
 * "error" red) retint every severity badge, alert, and status chip across
 * the app consistently. Semantic colors below map onto MUI's own
 * `error`/`warning`/`success`/`info` palette keys deliberately: every
 * existing `color="error"` etc. call site (SeverityBadge, ProvenanceBadge,
 * Alert, RunDetailsPanel) already speaks this vocabulary, so retuning the
 * palette here cascades everywhere without touching those components.
 */

const NAVY = "#1F3A5F";
const NAVY_DARK = "#152A47";
const SLATE = "#5C6773";
const PAGE_BACKGROUND = "#F3F5F8";
const BORDER = "#DCE2E8";
const TEXT_PRIMARY = "#182634";
const TEXT_SECONDARY = "#5B6B7C";

/**
 * A restrained, muted violet-blue reserved for exactly two meanings across
 * the product — a system-suggested (not yet confirmed) classification, and
 * an AI-assisted determination — so the same accent always means "produced
 * by inference, not yet human-verified," wherever it appears. Not part of
 * the MUI palette proper (a one-off addition would force every consumer to
 * extend the Palette type for a single accent); exported here instead so
 * both call sites share one definition rather than inventing their own hex.
 */
export const SUGGESTED_ACCENT_COLOR = "#6B5FA8";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: NAVY, dark: NAVY_DARK },
    secondary: { main: SLATE },
    background: { default: PAGE_BACKGROUND, paper: "#FFFFFF" },
    divider: BORDER,
    text: { primary: TEXT_PRIMARY, secondary: TEXT_SECONDARY },
    // Muted, institutional versions of MUI's semantic colors — deliberately
    // not the bright default red/orange/blue, and deliberately reused for
    // every credit-severity/status signal in the product (Chapter 11 /
    // default, elevated stress, informational/source, verified/resolved)
    // rather than a separate one-off color system per component.
    error: { main: "#A13D3D" },
    warning: { main: "#B5730A" },
    success: { main: "#3F7A54" },
    info: { main: "#3A6EA5" },
    action: {
      hover: "rgba(31, 58, 95, 0.045)",
      selected: "rgba(31, 58, 95, 0.09)",
    },
  },
  shape: { borderRadius: 6 },
  typography: {
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: PAGE_BACKGROUND },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: "none",
          borderBottom: `1px solid ${NAVY_DARK}`,
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: "#EEF2F6",
          borderRight: `1px solid ${BORDER}`,
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          borderLeft: "3px solid transparent",
          paddingTop: 10,
          paddingBottom: 10,
          "&.Mui-selected": {
            borderLeftColor: NAVY,
            backgroundColor: "rgba(31, 58, 95, 0.09)",
            "& .MuiListItemText-primary": { fontWeight: 600, color: NAVY_DARK },
          },
          "&.Mui-selected:hover": {
            backgroundColor: "rgba(31, 58, 95, 0.12)",
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
        outlined: { borderColor: BORDER },
        elevation1: { boxShadow: "0 1px 2px rgba(24, 38, 52, 0.06)" },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 600,
          color: TEXT_SECONDARY,
          backgroundColor: "#FAFBFC",
          borderBottom: `1px solid ${BORDER}`,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          "&:last-child td": { borderBottom: 0 },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500 },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: NAVY_DARK,
          fontSize: "0.75rem",
        },
      },
    },
  },
});
