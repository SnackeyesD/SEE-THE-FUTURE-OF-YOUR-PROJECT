import type { WebGLStatus } from "./webgl";

export type SurfaceViewMode = "2d" | "3d";

const STORAGE_PREFIX = "see.surface.view.";

function safeStorage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Préférence 2D/3D par projet ; défaut 2D si le stockage est absent. */
export function readSurfaceView(
  projectId: string,
  storage: Storage | null = safeStorage(),
): SurfaceViewMode {
  try {
    return storage?.getItem(`${STORAGE_PREFIX}${projectId}`) === "3d" ? "3d" : "2d";
  } catch {
    return "2d";
  }
}

export function writeSurfaceView(
  projectId: string,
  mode: SurfaceViewMode,
  storage: Storage | null = safeStorage(),
): void {
  try {
    storage?.setItem(`${STORAGE_PREFIX}${projectId}`, mode);
  } catch {
    // Un stockage plein ou bloqué ne doit jamais casser le cockpit.
  }
}

export interface SurfaceViewDecision {
  view: SurfaceViewMode;
  /** Message de repli à afficher, ou `null` quand la vue demandée est servie. */
  notice: string | null;
}

/**
 * Le repli WebGL est automatique et expliqué. Une machine lente reste en 3D :
 * l'avertissement est seulement proposé, jamais imposé.
 */
export function resolveSurfaceView(
  requested: SurfaceViewMode,
  status: WebGLStatus,
): SurfaceViewDecision {
  if (requested !== "3d") return { view: "2d", notice: null };
  if (status.supported) return { view: "3d", notice: null };
  return {
    view: "2d",
    notice:
      status.reason === "context_lost"
        ? "Le contexte WebGL a été perdu : retour automatique à la carte 2D."
        : "WebGL n'est pas disponible sur cette machine : la carte 2D reste la référence.",
  };
}
