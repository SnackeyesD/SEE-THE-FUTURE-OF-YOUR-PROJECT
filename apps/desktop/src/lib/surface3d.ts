/**
 * Géométrie pure de la surface 3D.
 *
 * Ce module ne fait aucune simulation : il transforme la matrice `z`
 * (lignes = axe Y, colonnes = axe X) fournie par le moteur en sommets,
 * couleurs et index. L'ordre des rangées et des colonnes suit la heatmap 2D.
 */

export interface SurfaceGeometryInput {
  xValues: number[];
  yValues: number[];
  /** `z[ligneY][colonneX]`, `null` tant que le moteur n'a pas rempli la cellule. */
  z: Array<Array<number | null>>;
  lowerIsBetter?: boolean;
}

export const SURFACE_HEAT_STEPS = 5;
export const MISSING_CELL = 255;

export interface SurfaceGeometry {
  positions: Float32Array;
  /** Palier de couleur 0..4, ou `MISSING_CELL`. */
  heatSteps: Uint8Array;
  indices: Uint32Array;
  columns: number;
  rows: number;
  minimum: number;
  maximum: number;
  complete: boolean;
  cellCount: number;
  renderedCellCount: number;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

/** Position normalisée [-1, 1] d'un index de grille (1 = valeur maximale). */
export function normalizedAxis(index: number, length: number): number {
  if (length <= 1) return 0;
  const ratio = index / (length - 1);
  return clamp01(ratio) * 2 - 1;
}

/** Palier de couleur orienté selon le sens favorable de la métrique. */
export function heatStep(
  value: number,
  minimum: number,
  maximum: number,
  lowerIsBetter = false,
): number {
  if (!Number.isFinite(value)) return MISSING_CELL;
  const span = maximum - minimum;
  const ratio = span <= 0 ? 0.5 : clamp01((value - minimum) / span);
  const oriented = lowerIsBetter ? 1 - ratio : ratio;
  return Math.min(SURFACE_HEAT_STEPS - 1, Math.floor(oriented * SURFACE_HEAT_STEPS));
}

/** Hauteur normalisée dans [0, 1] : 0 = minimum, 1 = maximum. */
export function surfaceHeight(
  value: number,
  minimum: number,
  maximum: number,
): number {
  if (!Number.isFinite(value)) return 0;
  const span = maximum - minimum;
  return span <= 0 ? 0.5 : clamp01((value - minimum) / span);
}

export function buildSurfaceGeometry(input: SurfaceGeometryInput): SurfaceGeometry {
  const columns = input.xValues.length;
  const rows = input.z.length;
  const cellCount = rows * columns;
  const positions = new Float32Array(cellCount * 3);
  const heatSteps = new Uint8Array(cellCount);
  const indices: number[] = [];

  const finiteValues: number[] = [];
  for (let row = 0; row < rows; row += 1) {
    const line = input.z[row] ?? [];
    for (let column = 0; column < columns; column += 1) {
      const value = line[column];
      if (typeof value === "number" && Number.isFinite(value)) finiteValues.push(value);
    }
  }

  const minimum = finiteValues.length > 0 ? Math.min(...finiteValues) : 0;
  const maximum = finiteValues.length > 0 ? Math.max(...finiteValues) : 0;
  const complete = finiteValues.length === cellCount && cellCount > 0;

  for (let row = 0; row < rows; row += 1) {
    const line = input.z[row] ?? [];
    for (let column = 0; column < columns; column += 1) {
      const index = row * columns + column;
      const value = line[column];
      const readable = typeof value === "number" && Number.isFinite(value);
      positions[index * 3] = normalizedAxis(column, columns);
      positions[index * 3 + 1] = readable ? surfaceHeight(value, minimum, maximum) : 0;
      positions[index * 3 + 2] = normalizedAxis(row, rows);
      heatSteps[index] = readable
        ? heatStep(value, minimum, maximum, input.lowerIsBetter)
        : MISSING_CELL;
    }
  }

  let renderedCellCount = 0;
  for (let row = 0; row < rows - 1; row += 1) {
    for (let column = 0; column < columns - 1; column += 1) {
      const a = row * columns + column;
      const b = a + 1;
      const c = a + columns;
      const d = c + 1;
      if (
        heatSteps[a] === MISSING_CELL ||
        heatSteps[b] === MISSING_CELL ||
        heatSteps[c] === MISSING_CELL ||
        heatSteps[d] === MISSING_CELL
      ) {
        continue;
      }
      indices.push(a, c, b, b, c, d);
      renderedCellCount += 1;
    }
  }

  return {
    positions,
    heatSteps,
    indices: Uint32Array.from(indices),
    columns,
    rows,
    minimum,
    maximum,
    complete,
    cellCount,
    renderedCellCount,
  };
}

export interface SurfaceCell {
  column: number;
  row: number;
  x: number;
  y: number;
}

/**
 * Convertit un point d'intersection (coordonnées normalisées x, z) en cellule
 * de grille. Utilisé par le raycast du mesh et testable sans WebGL.
 */
export function pickSurfaceCell(
  point: { x: number; z: number },
  input: Pick<SurfaceGeometryInput, "xValues" | "yValues">,
): SurfaceCell | null {
  const columns = input.xValues.length;
  const rows = input.yValues.length;
  if (columns === 0 || rows === 0) return null;
  if (!Number.isFinite(point.x) || !Number.isFinite(point.z)) return null;
  if (point.x < -1 || point.x > 1 || point.z < -1 || point.z > 1) return null;
  const column = Math.round(((point.x + 1) / 2) * (columns - 1));
  const row = Math.round(((point.z + 1) / 2) * (rows - 1));
  return {
    column,
    row,
    x: input.xValues[column],
    y: input.yValues[row],
  };
}

export interface SurfaceMarker {
  position: [number, number, number];
  column: number;
  row: number;
  value: number;
}

/** Position 3D du point courant, ou `null` s'il est absent de la grille. */
export function surfaceMarker(
  current: [number, number] | null | undefined,
  input: SurfaceGeometryInput,
): SurfaceMarker | null {
  if (!current) return null;
  const column = input.xValues.findIndex((value) => value === current[0]);
  const row = input.yValues.findIndex((value) => value === current[1]);
  if (column < 0 || row < 0) return null;
  const value = input.z[row]?.[column];
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const geometry = buildSurfaceGeometry(input);
  const index = row * geometry.columns + column;
  return {
    position: [
      geometry.positions[index * 3],
      geometry.positions[index * 3 + 1],
      geometry.positions[index * 3 + 2],
    ],
    column,
    row,
    value,
  };
}

/** Coordonnées 3D d'une cellule, sans reconstruire toute la géométrie. */
export function surfaceCellPosition(
  value: number,
  minimum: number,
  maximum: number,
  column: number,
  row: number,
  columns: number,
  rows: number,
): [number, number, number] {
  return [
    normalizedAxis(column, columns),
    surfaceHeight(value, minimum, maximum),
    normalizedAxis(row, rows),
  ];
}
