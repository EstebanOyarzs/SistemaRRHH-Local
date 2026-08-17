import type { ReactNode } from "react";

export interface Columna<T> {
  id: string;
  label: string;
  valor: (row: T) => string | number;
  render: (row: T) => ReactNode;
  // Texto completo para el atributo title del header, cuando el label se
  // acorta para no ensanchar la columna (ver COLUMNAS_TRANSACCIONES en
  // SobretiempoDashboardPage.tsx). Si no se pasa, se usa el label tal cual.
  titulo?: string;
}

export function ordenarFilas<T>(rows: T[], columnas: Columna<T>[], columnaId: string, asc: boolean): T[] {
  const columna = columnas.find((c) => c.id === columnaId) ?? columnas[0];
  const factor = asc ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = columna.valor(a);
    const vb = columna.valor(b);
    if (va < vb) return -factor;
    if (va > vb) return factor;
    return 0;
  });
}
