/**
 * Détection WebGL et mesure de fréquence d'images.
 *
 * Rien n'est supposé sur la machine : WebKitGTK peut exposer un contexte
 * logiciel lent, ou aucun contexte. Ces helpers restent sans dépendance à
 * Three.js pour être testables dans jsdom.
 */

export type WebGLFailureReason = "no_context" | "context_lost" | "slow";

export interface WebGLStatus {
  supported: boolean;
  reason?: WebGLFailureReason;
  fps?: number;
}

export interface DetectWebGLOptions {
  /** Injection de test : remplace `document.createElement("canvas")`. */
  createCanvas?: () => HTMLCanvasElement;
}

/**
 * Crée un canvas détaché et tente `webgl2` puis `webgl`. Le contexte est
 * relâché immédiatement après la détection pour ne pas consommer un slot GPU.
 */
export function detectWebGL(options: DetectWebGLOptions = {}): WebGLStatus {
  if (typeof document === "undefined" && !options.createCanvas) {
    return { supported: false, reason: "no_context" };
  }
  try {
    const canvas = options.createCanvas?.() ?? document.createElement("canvas");
    const context =
      canvas.getContext("webgl2") ?? canvas.getContext("webgl") ?? null;
    if (!context) return { supported: false, reason: "no_context" };
    const lose = context.getExtension("WEBGL_lose_context");
    lose?.loseContext();
    return { supported: true };
  } catch {
    return { supported: false, reason: "no_context" };
  }
}

export interface ContextLossTarget {
  addEventListener?: (type: string, listener: () => void) => void;
  removeEventListener?: (type: string, listener: () => void) => void;
}

/**
 * Branche un écouteur `webglcontextlost` et retourne la fonction de nettoyage.
 * Un contexte perdu n'est pas une erreur fatale : l'appelant bascule en 2D.
 */
export function observeContextLoss(
  target: ContextLossTarget | null,
  onLost: () => void,
): () => void {
  if (!target?.addEventListener) return () => undefined;
  target.addEventListener("webglcontextlost", onLost);
  return () => {
    target.removeEventListener?.("webglcontextlost", onLost);
  };
}

/** Médiane d'une liste de nombres finis (non destructive). */
export function median(values: number[]): number {
  const sorted = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (sorted.length === 0) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
}

/** Fréquence déduite des horodatages de frames (médiane des intervalles). */
export function medianFrameRate(timestamps: number[]): number {
  const deltas: number[] = [];
  for (let index = 1; index < timestamps.length; index += 1) {
    const delta = timestamps[index] - timestamps[index - 1];
    if (Number.isFinite(delta) && delta > 0) deltas.push(delta);
  }
  const interval = median(deltas);
  return interval > 0 ? 1000 / interval : 0;
}

export interface MeasureFrameRateOptions {
  durationMs?: number;
  now?: () => number;
  requestFrame?: (callback: (timestamp: number) => void) => number;
}

/**
 * Échantillonne les frames pendant `durationMs` puis retourne la médiane.
 * La promesse se résout à 0 si aucune frame n'a été observée (jsdom, onglet
 * masqué) : l'appelant ne doit jamais imposer le repli sur cette seule base.
 */
export function measureFrameRate(
  options: MeasureFrameRateOptions = {},
): Promise<number> {
  const durationMs = options.durationMs ?? 2000;
  const now =
    options.now ?? (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  const requestFrame =
    options.requestFrame ??
    ((callback: (timestamp: number) => void) =>
      typeof requestAnimationFrame === "function"
        ? requestAnimationFrame(callback)
        : 0);

  return new Promise((resolve) => {
    const started = now();
    const timestamps: number[] = [];
    let settled = false;

    const finish = (frames: number[]) => {
      if (settled) return;
      settled = true;
      resolve(medianFrameRate(frames));
    };

    const tick = (timestamp: number) => {
      if (settled) return;
      timestamps.push(Number.isFinite(timestamp) ? timestamp : now());
      if (now() - started >= durationMs) {
        finish(timestamps);
        return;
      }
      requestFrame(tick);
    };

    if (requestFrame(tick) === 0) finish([]);
  });
}

/** Seuil sous lequel la 3D devient inconfortable (phase 14). */
export const SLOW_FRAME_RATE = 30;

export function isSlow(frameRate: number): boolean {
  return frameRate > 0 && frameRate < SLOW_FRAME_RATE;
}
