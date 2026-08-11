import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";

/**
 * The single mobile/tablet-vs-desktop-chrome breakpoint used throughout the
 * app (navigation collapse, table-to-card transformations, responsive
 * grids) — below MUI's default `md` (900px) covers both phone widths
 * (375/390/430) and tablet (768) as one "compact" bucket; `md` and above
 * (1024/1280/1440+) keeps the existing desktop chrome. One shared threshold
 * rather than a different breakpoint per component keeps the responsive
 * behavior predictable across the app.
 */
export function useIsMobile(): boolean {
  const theme = useTheme();
  return useMediaQuery(theme.breakpoints.down("md"));
}
