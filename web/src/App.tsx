import type { ReactElement } from "react";
import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { AlertsPage } from "./pages/AlertsPage";
import { CreditUniversePage } from "./pages/CreditUniversePage";
import { IssuerPage } from "./pages/IssuerPage";
import { MorningResearchBriefPage } from "./pages/MorningResearchBriefPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ResearchDocumentUploadPage } from "./pages/ResearchDocumentUploadPage";
import { ResearchDocumentsWorkspacePage } from "./pages/ResearchDocumentsWorkspacePage";
import { ResearchNoteEditorPage } from "./pages/ResearchNoteEditorPage";
import { ResearchNotePage } from "./pages/ResearchNotePage";
import { ResearchNotesWorkspacePage } from "./pages/ResearchNotesWorkspacePage";
import { ResearchUniversesPage } from "./pages/ResearchUniversesPage";
import { SearchPage } from "./pages/SearchPage";
import { WatchlistDetailPage } from "./pages/WatchlistDetailPage";
import { WatchlistsPage } from "./pages/WatchlistsPage";

export function App(): ReactElement {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<CreditUniversePage />} />
        <Route path="/issuers/:issuerId" element={<IssuerPage />} />
        <Route path="/issuers/:issuerId/research-notes/new" element={<ResearchNoteEditorPage />} />
        <Route
          path="/issuers/:issuerId/research-documents/new"
          element={<ResearchDocumentUploadPage />}
        />
        <Route path="/research-notes" element={<ResearchNotesWorkspacePage />} />
        <Route path="/research-documents" element={<ResearchDocumentsWorkspacePage />} />
        <Route path="/research-notes/:noteId" element={<ResearchNotePage />} />
        <Route path="/research-notes/:noteId/edit" element={<ResearchNoteEditorPage />} />
        <Route path="/research-universes" element={<ResearchUniversesPage />} />
        <Route path="/research-brief" element={<MorningResearchBriefPage />} />
        <Route path="/watchlists" element={<WatchlistsPage />} />
        <Route path="/watchlists/:watchlistId" element={<WatchlistDetailPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
