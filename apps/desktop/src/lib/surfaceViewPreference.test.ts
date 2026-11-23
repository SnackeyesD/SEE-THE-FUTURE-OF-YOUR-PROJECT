import { describe, expect, it } from "vitest";

import {
  readSurfaceView,
  resolveSurfaceView,
  writeSurfaceView,
} from "./surfaceViewPreference";

function storage(): Storage {
  const entries = new Map<string, string>();
  return {
    get length() {
      return entries.size;
    },
    clear: () => entries.clear(),
    getItem: (key: string) => entries.get(key) ?? null,
    key: (index: number) => [...entries.keys()][index] ?? null,
    removeItem: (key: string) => {
      entries.delete(key);
    },
    setItem: (key: string, value: string) => {
      entries.set(key, value);
    },
  };
}

describe("préférence de vue 2D/3D", () => {
  it("vaut 2D par défaut et mémorise par projet", () => {
    const local = storage();
    expect(readSurfaceView("projet-a", local)).toBe("2d");
    writeSurfaceView("projet-a", "3d", local);
    expect(readSurfaceView("projet-a", local)).toBe("3d");
    expect(readSurfaceView("projet-b", local)).toBe("2d");
  });

  it("ignore une valeur inconnue ou un stockage absent", () => {
    const local = storage();
    local.setItem("see.surface.view.projet", "hologramme");
    expect(readSurfaceView("projet", local)).toBe("2d");
    expect(readSurfaceView("projet", null)).toBe("2d");
    expect(() => writeSurfaceView("projet", "3d", null)).not.toThrow();
  });
});

describe("resolveSurfaceView", () => {
  it("sert la 2D demandée sans avertissement", () => {
    expect(resolveSurfaceView("2d", { supported: false, reason: "no_context" })).toEqual({
      view: "2d",
      notice: null,
    });
  });

  it("sert la 3D quand WebGL est disponible", () => {
    expect(resolveSurfaceView("3d", { supported: true })).toEqual({
      view: "3d",
      notice: null,
    });
  });

  it("replie automatiquement et explique l'absence de WebGL", () => {
    const decision = resolveSurfaceView("3d", {
      supported: false,
      reason: "no_context",
    });
    expect(decision.view).toBe("2d");
    expect(decision.notice).toContain("WebGL");
  });

  it("explique la perte de contexte", () => {
    const decision = resolveSurfaceView("3d", {
      supported: false,
      reason: "context_lost",
    });
    expect(decision.view).toBe("2d");
    expect(decision.notice).toContain("contexte WebGL");
  });
});
