import * as THREE from "three";

/**
 * Couleurs lues depuis les tokens CSS « Ink & Signal ». Aucun hex n'est écrit
 * ici : le `ui:check` reste la seule source de vérité, et la 3D utilise
 * exactement les paliers de la heatmap 2D.
 */
export function cssColor(name: string, fallback: [number, number, number]): THREE.Color {
  type DocumentLike = { documentElement?: Element };
  const documentLike = (globalThis as { document?: DocumentLike }).document;
  if (!documentLike?.documentElement) return new THREE.Color(...fallback);
  try {
    const raw = getComputedStyle(documentLike.documentElement as Element)
      .getPropertyValue(name)
      .trim();
    if (!raw) return new THREE.Color(...fallback);
    return new THREE.Color(raw);
  } catch {
    return new THREE.Color(...fallback);
  }
}

const HEAT_FALLBACK: Array<[number, number, number]> = [
  [0.12, 0.18, 0.26],
  [0.2, 0.3, 0.4],
  [0.3, 0.45, 0.55],
  [0.45, 0.6, 0.7],
  [0.6, 0.8, 0.9],
];

export function heatPalette(): THREE.Color[] {
  return HEAT_FALLBACK.map((fallback, index) =>
    cssColor(`--heat-${index}`, fallback),
  );
}

export function accentColor(): THREE.Color {
  return cssColor("--accent", [0.35, 0.85, 0.75]);
}

export function textColor(): THREE.Color {
  return cssColor("--text-1", [0.9, 0.93, 0.97]);
}
