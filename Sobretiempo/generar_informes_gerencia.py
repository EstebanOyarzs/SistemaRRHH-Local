"""
================================================================================
GENERADOR DE INFORMES EJECUTIVOS PDF DE SOBRETIEMPO, POR GERENCIA
================================================================================
Genera un PDF por Gerencia, con solo los indicadores de esa Gerencia (para
mandarselo a cada gerente) — sin necesitar el backend corriendo. La logica
vive en backend/dashboards/sobretiempo/reporte_pdf.py.

USO:
    venv\\Scripts\\python.exe Sobretiempo\\generar_informes_gerencia.py
    venv\\Scripts\\python.exe Sobretiempo\\generar_informes_gerencia.py "ruta\\carpeta_salida"
================================================================================
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.dashboards.sobretiempo.reporte_pdf import generar_informes_gerencia  # noqa: E402


def main(output_dir=None):
    destino = Path(output_dir) if output_dir else None
    rutas = generar_informes_gerencia(destino)
    if not rutas:
        print("No se genero ningun informe — la base no tiene Gerencias con datos cargados.")
        return
    print(f"Se generaron {len(rutas)} informes:")
    for ruta in rutas:
        print(f"  {ruta}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
