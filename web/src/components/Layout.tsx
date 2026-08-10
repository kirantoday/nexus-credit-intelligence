import type { ReactElement } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router";
import {
  AppBar,
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Toolbar,
  Typography,
} from "@mui/material";

const DRAWER_WIDTH = 260;

interface NavItem {
  label: string;
  path: string;
  enabled: boolean;
}

// Credit Universe is the landing page (ADR-008) — every other item is wired
// up for real as its milestone lands (PLAN.md section 18). The roadmap list
// itself is kept intact (nothing here is deleted, no routes/components
// removed) — only rendering of not-yet-built items is temporarily hidden
// from the nav for a clean demo presentation (PLAN.md Milestone 7.5.3
// CFO-demo pass). Re-enable by removing the `.filter` below when ready to
// show the roadmap again.
const NAV_ITEMS: NavItem[] = [
  { label: "Credit Universe", path: "/", enabled: true },
  { label: "Research Universes", path: "/research-universes", enabled: true },
  { label: "Morning Research Brief", path: "/research-brief", enabled: true },
  { label: "About Nexus", path: "/about", enabled: true },
  { label: "Dashboard", path: "/dashboard", enabled: false },
  { label: "Capital Structure", path: "/capital-structure", enabled: false },
  { label: "Watchlists", path: "/watchlists", enabled: false },
  { label: "Search", path: "/search", enabled: false },
  { label: "Research Workspace", path: "/research", enabled: false },
  { label: "Alerts", path: "/alerts", enabled: false },
  { label: "Research Assistant", path: "/assistant", enabled: false },
];

const VISIBLE_NAV_ITEMS: NavItem[] = NAV_ITEMS.filter((item) => item.enabled);

export function Layout(): ReactElement {
  const location = useLocation();

  return (
    <Box sx={{ display: "flex" }}>
      <AppBar position="fixed" sx={{ zIndex: (muiTheme) => muiTheme.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" noWrap component="div">
            Nexus Credit Intelligence
          </Typography>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          ["& .MuiDrawer-paper"]: { width: DRAWER_WIDTH, boxSizing: "border-box" },
        }}
      >
        <Toolbar />
        <List>
          {VISIBLE_NAV_ITEMS.map((item) => (
            <ListItemButton
              key={item.path}
              component={RouterLink}
              to={item.path}
              selected={location.pathname === item.path}
            >
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
