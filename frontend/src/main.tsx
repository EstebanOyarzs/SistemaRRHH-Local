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
      // No reusar la clase "app-content" acá: en AppLayout esa clase tiene
      // overflow-y:auto porque vive dentro de un contenedor flex con altura
      // fija (.app-main/.app-layout) y ESE es el que hace scroll interno.
      // Standalone no tiene ese contexto — el mismo overflow-y:auto, sin
      // una altura acotada, igual convierte a este div en "scroll
      // container" a ojos del navegador (aunque nunca llegue a scrollear
      // el solo), y eso rompe position:sticky del header de filtros (deja
      // de pegarse al hacer scroll de la pagina). Con solo el padding
      // alcanza; el scroll real queda a cargo de html/body, como siempre.
      <div style={{ padding: "1.75rem" }}>
        <SobretiempoDashboardPage />
      </div>
    ) : (
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )}
  </StrictMode>,
);
