import type { ReactElement } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router";
import {
  AppBar,
  Box,
  Chip,
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

// Placeholder navigation for Milestone 1. Each item is wired up for real as
// its milestone lands (PLAN.md section 18) — disabled items are visible now
// so the eventual product surface is legible from day one.
const NAV_ITEMS: NavItem[] = [
  { label: "Home", path: "/", enabled: true },
  { label: "Credit Universe", path: "/credit-universe", enabled: false },
  { label: "Dashboard", path: "/dashboard", enabled: false },
  { label: "Capital Structure", path: "/capital-structure", enabled: false },
  { label: "Watchlists", path: "/watchlists", enabled: false },
  { label: "Search", path: "/search", enabled: false },
  { label: "Research Workspace", path: "/research", enabled: false },
  { label: "Alerts", path: "/alerts", enabled: false },
  { label: "Research Assistant", path: "/assistant", enabled: false },
];

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
          {NAV_ITEMS.map((item) =>
            item.enabled ? (
              <ListItemButton
                key={item.path}
                component={RouterLink}
                to={item.path}
                selected={location.pathname === item.path}
              >
                <ListItemText primary={item.label} />
              </ListItemButton>
            ) : (
              <ListItemButton key={item.path} disabled>
                <ListItemText primary={item.label} />
                <Chip label="Soon" size="small" variant="outlined" />
              </ListItemButton>
            ),
          )}
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
