import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles/theme.css";
import { App } from "./App";
import { SobretiempoDashboardPage } from "./pages/SobretiempoDashboardPage";

// Un HTML exportado (ver src/utils/exportarHtml.ts) define esta variable
// global antes de cargar este bundle. En ese caso se salta login/routing y
// se muestra directamente el dashboard, alimentado con los datos embebidos.
const exportado = typeof window !== "undefined" ? window.__PDA_EXPORT__ : undefined;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {exportado ? (
      <div className="app-content">
        <SobretiempoDashboardPage />
      </div>
    ) : (
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )}
  </StrictMode>,
);
