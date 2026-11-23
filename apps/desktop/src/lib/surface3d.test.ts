import { describe, expect, it } from "vitest";

import {
  MISSING_CELL,
  buildSurfaceGeometry,
  heatStep,
  normalizedAxis,
  pickSurfaceCell,
  surfaceCellPosition,
  surfaceHeight,
  surfaceMarker,
} from "./surface3d";

const grid = {
  xValues: [10, 20, 30],
  yValues: [100, 200],
  z: [
    [1, 2, 3],
    [4, 5, null],
  ],
};

describe("normalizedAxis", () => {
  it("projette les index de grille dans [-1, 1]", () => {
    expect(normalizedAxis(0, 3)).toBe(-1);
    expect(normalizedAxis(1, 3)).toBe(0);
    expect(normalizedAxis(2, 3)).toBe(1);
    expect(normalizedAxis(4, 1)).toBe(0);
  });
});

describe("heatStep et surfaceHeight", () => {
  it("oriente les paliers selon le sens favorable", () => {
    expect(heatStep(10, 0, 10)).toBe(4);
    expect(heatStep(0, 0, 10)).toBe(0);
    expect(heatStep(10, 0, 10, true)).toBe(0);
    expect(heatStep(Number.NaN, 0, 10)).toBe(MISSING_CELL);
  });

  it("normalise la hauteur sans diviser par zéro", () => {
    expect(surfaceHeight(5, 0, 10)).toBe(0.5);
    expect(surfaceHeight(10, 0, 10)).toBe(1);
    expect(surfaceHeight(3, 3, 3)).toBe(0.5);
    expect(surfaceHeight(Number.NaN, 0, 1)).toBe(0);
  });
});

describe("buildSurfaceGeometry", () => {
  it("mappe la grille en sommets et ignore les triangles incomplets", () => {
    const geometry = buildSurfaceGeometry(grid);

    expect(geometry.columns).toBe(3);
    expect(geometry.rows).toBe(2);
    expect(geometry.cellCount).toBe(6);
    expect(geometry.complete).toBe(false);
    expect(geometry.minimum).toBe(1);
    expect(geometry.maximum).toBe(5);
    expect(geometry.positions).toHaveLength(18);
    expect(geometry.heatSteps).toHaveLength(6);
    expect(geometry.heatSteps[5]).toBe(MISSING_CELL);
    expect(geometry.renderedCellCount).toBe(1);
    expect(geometry.indices).toHaveLength(6);

    expect(Array.from(geometry.positions.slice(0, 3))).toEqual([-1, 0, -1]);
    expect(Array.from(geometry.positions.slice(3, 6))).toEqual([0, 0.25, -1]);
  });

  it("produit une géométrie complète quand toutes les cellules sont remplies", () => {
    const geometry = buildSurfaceGeometry({
      xValues: [0, 1],
      yValues: [0, 1],
      z: [
        [0, 1],
        [2, 3],
      ],
    });

    expect(geometry.complete).toBe(true);
    expect(geometry.renderedCellCount).toBe(1);
    expect(geometry.indices).toHaveLength(6);
  });

  it("ne plante pas sur une grille vide", () => {
    const geometry = buildSurfaceGeometry({ xValues: [], yValues: [], z: [] });
    expect(geometry.cellCount).toBe(0);
    expect(geometry.complete).toBe(false);
    expect(geometry.indices).toHaveLength(0);
  });
});

describe("pickSurfaceCell", () => {
  it("convertit un point normalisé en cellule", () => {
    expect(pickSurfaceCell({ x: -1, z: -1 }, grid)).toEqual({
      column: 0,
      row: 0,
      x: 10,
      y: 100,
    });
    expect(pickSurfaceCell({ x: 1, z: 1 }, grid)).toEqual({
      column: 2,
      row: 1,
      x: 30,
      y: 200,
    });
    expect(pickSurfaceCell({ x: 0.9, z: 0.6 }, grid)).toMatchObject({
      column: 2,
      row: 1,
    });
  });

  it("refuse un point hors de la surface", () => {
    expect(pickSurfaceCell({ x: 1.4, z: 0 }, grid)).toBeNull();
    expect(pickSurfaceCell({ x: Number.NaN, z: 0 }, grid)).toBeNull();
    expect(pickSurfaceCell({ x: 0, z: 0 }, { xValues: [], yValues: [] })).toBeNull();
  });
});

describe("marqueur du point courant", () => {
  it("retrouve la position du point courant dans la grille", () => {
    const marker = surfaceMarker([20, 100], grid);
    expect(marker).not.toBeNull();
    expect(marker?.column).toBe(1);
    expect(marker?.row).toBe(0);
    expect(marker?.value).toBe(2);
    expect(marker?.position[0]).toBe(0);
    expect(marker?.position[2]).toBe(-1);
  });

  it("retourne null si le point est absent ou vide", () => {
    expect(surfaceMarker([25, 100], grid)).toBeNull();
    expect(surfaceMarker([30, 200], grid)).toBeNull();
    expect(surfaceMarker(null, grid)).toBeNull();
  });

  it("calcule la position d'une cellule sans géométrie complète", () => {
    expect(surfaceCellPosition(5, 0, 10, 1, 0, 3, 2)).toEqual([0, 0.5, -1]);
  });
});
