import type { ReactElement } from "react";
import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { CreditUniversePage } from "./pages/CreditUniversePage";
import { IssuerPage } from "./pages/IssuerPage";
import { MorningResearchBriefPage } from "./pages/MorningResearchBriefPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ResearchUniversesPage } from "./pages/ResearchUniversesPage";
import { WatchlistDetailPage } from "./pages/WatchlistDetailPage";
import { WatchlistsPage } from "./pages/WatchlistsPage";

export function App(): ReactElement {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<CreditUniversePage />} />
        <Route path="/issuers/:issuerId" element={<IssuerPage />} />
        <Route path="/research-universes" element={<ResearchUniversesPage />} />
        <Route path="/research-brief" element={<MorningResearchBriefPage />} />
        <Route path="/watchlists" element={<WatchlistsPage />} />
        <Route path="/watchlists/:watchlistId" element={<WatchlistDetailPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
