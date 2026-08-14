"""
================================================================================
NORMALIZADOR DE CAPACITACION -> SQLITE (linea de comandos)
================================================================================
Uso manual/de respaldo — la forma normal de actualizar los datos es el boton
"Actualizar datos" del dashboard (sube los 2 Excel de dotacion desde el
navegador). Este script corre exactamente la misma logica de parsing (vive en
backend/dashboards/capacitacion/normalizar.py) por linea de comandos, para
cuando no se tiene acceso a la pagina (ver notas de "antivirus/EDR" del
proyecto).

USO:
    venv\\Scripts\\python.exe Capacitacion\\normalizar_capacitacion.py "ruta\\actual.xlsx" "ruta\\anterior.xlsx" <mes> <anio>

Donde:
    actual.xlsx   = dotacion del MES del reporte (la hoja "Detalle...")
    anterior.xlsx = dotacion del mes ANTERIOR (para detectar cambios de cargo)
    mes           = mes del reporte, numero 1-12
    anio          = anio del reporte, ej. 2026

EJEMPLO:
    venv\\Scripts\\python.exe Capacitacion\\normalizar_capacitacion.py "C:\\Users\\eoyarzun\\Desktop\\Detalle Julio.xlsx" "C:\\Users\\eoyarzun\\Desktop\\Detalle Junio.xlsx" 7 2026
================================================================================
"""

import sys
from pathlib import Path

# Import absoluto backend.xxx: hace falta la raiz del proyecto en sys.path,
# ya que este script se corre directo (no como modulo -m) desde Capacitacion/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.dashboards.capacitacion.db import DB_PATH  # noqa: E402
from backend.dashboards.capacitacion.normalizar import (  # noqa: E402
    procesar_archivos,
    sembrar_procedimientos_si_vacia,
)


def main(path_actual, path_anterior, mes, anio):
    sembrar_procedimientos_si_vacia()

    print(f"Dotacion actual:   {path_actual}")
    print(f"Dotacion anterior: {path_anterior}")
    print(f"Mes/Anio reporte:  {mes}/{anio}")

    resultado = procesar_archivos(path_actual, path_anterior, mes, anio)

    print(f"  Dotacion:        {resultado['dotacion']:,} filas")
    print(f"  Nuevos ingresos: {resultado['nuevos_ingresos']:,} filas")
    print(f"  Cambios de cargo:{resultado['cambios_cargo']:,} filas")
    if resultado["backup"]:
        print(f"Respaldo de la base anterior: {resultado['backup']}")
    print(f"Datos cargados en: {DB_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    _, actual, anterior, mes_arg, anio_arg = sys.argv
    main(actual, anterior, int(mes_arg), int(anio_arg))
