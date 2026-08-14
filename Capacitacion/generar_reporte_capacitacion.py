"""
================================================================================
GENERADOR DE REPORTE EXCEL DE CAPACITACION (linea de comandos, sin servidor)
================================================================================
Genera el mismo Excel de 3 hojas (Resumen, Dotacion CHTA, Procedimientos) que
el boton "Descargar" del dashboard, pero sin necesitar el backend corriendo.
La logica vive en backend/dashboards/capacitacion/reporte_excel.py.

USO:
    venv\\Scripts\\python.exe Capacitacion\\generar_reporte_capacitacion.py
    venv\\Scripts\\python.exe Capacitacion\\generar_reporte_capacitacion.py "ruta\\salida.xlsx"
================================================================================
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.dashboards.capacitacion.reporte_excel import generar_reporte_excel  # noqa: E402


def main(output_path=None):
    destino = Path(output_path) if output_path else None
    ruta = generar_reporte_excel(destino)
    print(f"Reporte generado: {ruta}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
