"""
================================================================================
GENERADOR DE REPORTE HTML DE SOBRETIEMPO (linea de comandos, sin servidor)
================================================================================
Genera el mismo HTML autocontenido que el boton "Descargar reporte (HTML)"
del dashboard, pero sin necesitar el backend corriendo — util cuando uvicorn
no se puede mantener levantado (ver notas de "antivirus/EDR" en el proyecto).
La logica vive en backend/dashboards/sobretiempo/reporte_html.py.

Requiere que frontend/dist ya este compilado:
    cd frontend; node ".\\node_modules\\vite\\bin\\vite.js" build

USO:
    venv\\Scripts\\python.exe Sobretiempo\\generar_reporte_sobretiempo.py
    venv\\Scripts\\python.exe Sobretiempo\\generar_reporte_sobretiempo.py "ruta\\salida.html"
================================================================================
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.dashboards.sobretiempo.reporte_html import generar_reporte_html  # noqa: E402


def main(output_path=None):
    destino = Path(output_path) if output_path else None
    ruta = generar_reporte_html(destino)
    print(f"Reporte generado: {ruta}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
