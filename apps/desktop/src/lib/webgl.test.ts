import { describe, expect, it, vi } from "vitest";

import {
  detectWebGL,
  isSlow,
  measureFrameRate,
  median,
  medianFrameRate,
  observeContextLoss,
} from "./webgl";

function fakeContext() {
  return {
    getExtension: vi.fn(() => ({ loseContext: vi.fn() })),
  } as unknown as WebGLRenderingContext;
}

function fakeCanvas(getContext: (type: string) => unknown): HTMLCanvasElement {
  return { getContext } as unknown as HTMLCanvasElement;
}

describe("detectWebGL", () => {
  it("préfère webgl2 puis relâche le contexte détecté", () => {
    const loseContext = vi.fn();
    const getContext = vi.fn(() => ({
      getExtension: () => ({ loseContext }),
    }));
    const status = detectWebGL({
      createCanvas: () => fakeCanvas(getContext as unknown as (type: string) => unknown),
    });

    expect(status).toEqual({ supported: true });
    expect(getContext).toHaveBeenCalledWith("webgl2");
    expect(loseContext).toHaveBeenCalled();
  });

  it("retombe sur webgl quand webgl2 manque", () => {
    const getContext = vi.fn((type: string) => (type === "webgl" ? fakeContext() : null));
    const status = detectWebGL({
      createCanvas: () => fakeCanvas(getContext as unknown as (type: string) => unknown),
    });

    expect(status.supported).toBe(true);
    expect(getContext.mock.calls.map((call) => call[0])).toEqual(["webgl2", "webgl"]);
  });

  it("retourne no_context sans contexte disponible", () => {
    const status = detectWebGL({
      createCanvas: () => fakeCanvas(() => null),
    });
    expect(status).toEqual({ supported: false, reason: "no_context" });
  });

  it("ne lève jamais si le canvas est indisponible", () => {
    const status = detectWebGL({
      createCanvas: () => {
        throw new Error("canvas refusé");
      },
    });
    expect(status).toEqual({ supported: false, reason: "no_context" });
  });
});

describe("observeContextLoss", () => {
  it("branche et débranche l'écouteur", () => {
    const listeners = new Map<string, () => void>();
    const target = {
      addEventListener: vi.fn((type: string, listener: () => void) => {
        listeners.set(type, listener);
      }),
      removeEventListener: vi.fn((type: string) => {
        listeners.delete(type);
      }),
    };
    const onLost = vi.fn();

    const cleanup = observeContextLoss(target, onLost);
    listeners.get("webglcontextlost")?.();
    expect(onLost).toHaveBeenCalledTimes(1);

    cleanup();
    expect(target.removeEventListener).toHaveBeenCalledWith(
      "webglcontextlost",
      expect.any(Function),
    );
  });

  it("accepte une cible absente", () => {
    expect(() => observeContextLoss(null, vi.fn())()).not.toThrow();
  });
});

describe("médiane et fps", () => {
  it("calcule une médiane paire ou impaire", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 3, 2])).toBe(2.5);
    expect(median([])).toBe(0);
  });

  it("déduit la fréquence médiane des horodatages", () => {
    expect(medianFrameRate([0, 16, 32, 48, 64])).toBeCloseTo(62.5);
    expect(medianFrameRate([0, 40, 80])).toBeCloseTo(25);
    expect(medianFrameRate([0])).toBe(0);
  });

  it("mesure une fréquence avec un rAF injecté", async () => {
    let clock = 0;
    const fps = await measureFrameRate({
      durationMs: 64,
      now: () => clock,
      requestFrame: (callback) => {
        clock += 16;
        callback(clock);
        return 1;
      },
    });
    expect(fps).toBeCloseTo(62.5);
  });

  it("se résout à 0 si aucune frame n'est observée", async () => {
    await expect(
      measureFrameRate({ durationMs: 10, requestFrame: () => 0 }),
    ).resolves.toBe(0);
  });

  it("signale une machine lente sans condamner 0 fps", () => {
    expect(isSlow(24)).toBe(true);
    expect(isSlow(30)).toBe(false);
    expect(isSlow(0)).toBe(false);
  });
});
