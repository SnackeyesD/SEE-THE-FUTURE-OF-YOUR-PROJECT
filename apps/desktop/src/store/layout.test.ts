import { describe, expect, it } from "vitest";

import {
  DEFAULT_LAYOUT,
  MAX_FRACTION,
  MIN_FRACTION,
  PRESET_FRACTIONS,
  clampFraction,
  decodeLayout,
  layoutFromPreset,
  layoutStorageKey,
  loadLayout,
  parseLayout,
  saveLayout,
  type LayoutState,
  type StorageLike,
} from "./layout";

function memoryStorage(): StorageLike & { entries: Map<string, string> } {
  const entries = new Map<string, string>();
  return {
    entries,
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => {
      entries.set(key, value);
    },
  };
}

describe("layout", () => {
  it("charge le preset par défaut sans valeur stockée", () => {
    const storage = memoryStorage();
    expect(loadLayout("p1", storage)).toEqual(DEFAULT_LAYOUT);
    expect(storage.entries.size).toBe(0);
  });

  it("persiste et restaure une disposition par projet", () => {
    const storage = memoryStorage();
    const layout = layoutFromPreset("pilotage");
    saveLayout("p1", layout, storage);

    expect(storage.entries.has(layoutStorageKey("p1"))).toBe(true);
    expect(loadLayout("p1", storage)).toEqual(layout);
    expect(loadLayout("p2", storage)).toEqual(DEFAULT_LAYOUT);
  });

  it("retombe sur le preset par défaut si le JSON est corrompu", () => {
    expect(decodeLayout("{pas du json")).toEqual(DEFAULT_LAYOUT);
    expect(decodeLayout(null)).toEqual(DEFAULT_LAYOUT);
  });

  it("rejette les fractions hors bornes ou dont la somme est fausse", () => {
    const outOfBounds: LayoutState = {
      preset: "custom",
      fractions: { left: 0.05, main: 0.75, right: 0.2 },
      fullscreen: null,
    };
    expect(parseLayout(outOfBounds)).toEqual(DEFAULT_LAYOUT);

    const badSum: LayoutState = {
      preset: "custom",
      fractions: { left: 0.3, main: 0.3, right: 0.3 },
      fullscreen: null,
    };
    expect(parseLayout(badSum)).toEqual(DEFAULT_LAYOUT);
  });

  it("accepte une disposition personnalisée valide et le plein écran", () => {
    const custom: LayoutState = {
      preset: "custom",
      fractions: { left: 0.3, main: 0.4, right: 0.3 },
      fullscreen: "secondary",
    };
    expect(parseLayout(custom)).toEqual(custom);
  });

  it("impose les fractions du preset même si le stockage en contient d'autres", () => {
    const stored = {
      preset: "pilotage",
      fractions: { left: 0.5, main: 0.3, right: 0.2 },
      fullscreen: null,
    };
    expect(parseLayout(stored)).toEqual({
      preset: "pilotage",
      fractions: PRESET_FRACTIONS.pilotage,
      fullscreen: null,
    });
  });

  it("borne une fraction manipulée sans casser la place du panneau principal", () => {
    expect(clampFraction(0.01, 0.2)).toBe(MIN_FRACTION);
    expect(clampFraction(0.9, 0.2)).toBeCloseTo(1 - 0.2 - MIN_FRACTION);
    expect(clampFraction(Number.NaN, 0.2)).toBe(MIN_FRACTION);
    expect(clampFraction(0.5, MAX_FRACTION)).toBeCloseTo(MIN_FRACTION);
  });
});
