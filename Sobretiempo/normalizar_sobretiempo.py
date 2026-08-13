"""
================================================================================
NORMALIZADOR DE SOBRETIEMPO -> SQLITE (linea de comandos)
================================================================================
Uso manual/de respaldo — desde la version 2 en adelante la forma normal de
actualizar los datos es el boton "Actualizar datos" del dashboard (sube el
Excel desde el navegador). Este script corre exactamente la misma logica de
parsing (vive en backend/dashboards/sobretiempo/normalizar.py) por linea de
comandos, para cuando no se tiene acceso a la pagina.

USO CADA MES:
    venv\\Scripts\\python.exe Sobretiempo\\normalizar_sobretiempo.py "ruta/al/nuevo_archivo.xlsx"

Si no se indica ruta, usa el archivo de ejemplo en "Archivos ejemplo/" (solo
para pruebas locales).
================================================================================
"""

import sys
from pathlib import Path

# Import absoluto backend.xxx: hace falta la raiz del proyecto en sys.path,
# ya que este script se corre directo (no como modulo -m) desde Sobretiempo/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.dashboards.sobretiempo.db import DB_PATH  # noqa: E402
from backend.dashboards.sobretiempo.normalizar import procesar_archivo  # noqa: E402

INPUT_PATH = Path(__file__).resolve().parent / "Archivos ejemplo" / "Control de Sobretiempo 2026.xlsx"


def main(input_path=INPUT_PATH):
    print(f"Leyendo: {input_path}")
    resultado = procesar_archivo(input_path)

    print(f"  Detalle:            {resultado['detalle']:,} filas")
    print(f"  Presupuesto:        {resultado['presupuesto']:,} filas")
    print(f"  Resumen:            {resultado['resumen']:,} filas")
    print(f"  Resumen_Gerencia:   {resultado['resumen_gerencia']:,} filas")
    if resultado["backup"]:
        print(f"Respaldo de la base anterior: {resultado['backup']}")
    print(f"Datos cargados en: {DB_PATH}")


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else INPUT_PATH
    main(inp)
