import { getDetalle, type Detalle, type Resumen } from "../api/sobretiempo";

export interface ExportPayload {
  resumenCompleto: Resumen[];
  detalleCompleto: Detalle[];
  generadoEl: string;
  generadoPor?: string;
}

// Cuando el HTML exportado se abre standalone, main.tsx revisa esta variable
// global antes de decidir si arranca la app normal (login + API) o solo el
// dashboard de Sobretiempo alimentado con los datos embebidos.
declare global {
  interface Window {
    __PDA_EXPORT__?: ExportPayload;
  }
}

async function leerTexto(url: string): Promise<string> {
  const respuesta = await fetch(url);
  if (!respuesta.ok) {
    throw new Error(`No se pudo leer ${url} (status ${respuesta.status})`);
  }
  return respuesta.text();
}

// Evita que datos de negocio con la secuencia literal "</script" corten el
// tag antes de tiempo al insertarlos como texto dentro de un <script>.
function escaparCierreDeScript(texto: string): string {
  return texto.replace(/<\/script/gi, "<\\/script");
}

/**
 * Genera un HTML autocontenido (mismo bundle JS/CSS que la app en vivo, mas
 * los datos completos embebidos) y dispara la descarga en el navegador.
 * Solo funciona sirviendo el build de produccion (frontend/dist) — en el dev
 * server de Vite no hay un unico archivo JS/CSS para inlinear.
 */
export async function exportarDashboardHtml(resumenCompleto: Resumen[], generadoPor?: string): Promise<void> {
  const scriptEl = document.querySelector<HTMLScriptElement>('script[type="module"][src*="/assets/"]');
  const linkEl = document.querySelector<HTMLLinkElement>('link[rel="stylesheet"][href*="/assets/"]');
  if (!scriptEl?.src || !linkEl?.href) {
    throw new Error(
      "No se encontro el build de produccion del frontend. La exportacion solo funciona sirviendo " +
        "frontend/dist (el modo que usan los demas usuarios en la red), no el servidor de desarrollo.",
    );
  }

  const [js, css, detalleCompleto] = await Promise.all([
    leerTexto(scriptEl.src),
    leerTexto(linkEl.href),
    getDetalle({}),
  ]);

  const payload: ExportPayload = {
    resumenCompleto,
    detalleCompleto,
    generadoEl: new Date().toLocaleString("es-CL"),
    generadoPor,
  };

  const datosEmbebidos = escaparCierreDeScript(JSON.stringify(payload));
  const jsSeguro = escaparCierreDeScript(js);
  const cssSeguro = css.replace(/<\/style/gi, "<\\/style");

  const html = `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Sobretiempo - reporte exportado</title>
<style>${cssSeguro}</style>
</head>
<body>
<div id="root"></div>
<script>window.__PDA_EXPORT__ = ${datosEmbebidos};</script>
<script type="module">${jsSeguro}</script>
</body>
</html>
`;

  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  const fecha = new Date().toISOString().slice(0, 10);
  enlace.href = url;
  enlace.download = `sobretiempo-${fecha}.html`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}
