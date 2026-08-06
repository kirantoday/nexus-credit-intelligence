import type { ReactElement } from "react";
import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { CreditUniversePage } from "./pages/CreditUniversePage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App(): ReactElement {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<CreditUniversePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
