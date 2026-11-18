export type LayoutPreset = "analyse" | "pilotage" | "presentation" | "custom";
export type PresetName = Exclude<LayoutPreset, "custom">;
export type LayoutFullscreen = "main" | "secondary" | null;

export interface LayoutFractions {
  left: number;
  main: number;
  right: number;
}

export interface LayoutState {
  preset: LayoutPreset;
  fractions: LayoutFractions;
  fullscreen: LayoutFullscreen;
}

export const LAYOUT_KEY_PREFIX = "sf-cockpit-layout:";
export const MIN_FRACTION = 0.15;
export const MAX_FRACTION = 0.7;
export const FRACTION_TOLERANCE = 0.01;

export const PRESET_FRACTIONS: Record<PresetName, LayoutFractions> = {
  analyse: { left: 0.22, main: 0.56, right: 0.22 },
  pilotage: { left: 0.3, main: 0.5, right: 0.2 },
  presentation: { left: 0.15, main: 0.7, right: 0.15 },
};

export const PRESET_LABELS: Record<PresetName, string> = {
  analyse: "Analyse",
  pilotage: "Pilotage",
  presentation: "Présentation",
};

export const PRESET_NAMES: PresetName[] = ["analyse", "pilotage", "presentation"];

export const DEFAULT_LAYOUT: LayoutState = {
  preset: "analyse",
  fractions: { ...PRESET_FRACTIONS.analyse },
  fullscreen: null,
};

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function cloneLayout(layout: LayoutState): LayoutState {
  return {
    preset: layout.preset,
    fractions: { ...layout.fractions },
    fullscreen: layout.fullscreen,
  };
}

export function layoutFromPreset(preset: PresetName): LayoutState {
  return {
    preset,
    fractions: { ...PRESET_FRACTIONS[preset] },
    fullscreen: null,
  };
}

export function fractionsAreValid(value: unknown): value is LayoutFractions {
  if (!isRecord(value)) return false;
  const numbers = [value.left, value.main, value.right].map(Number);
  if (numbers.some((item) => !Number.isFinite(item))) return false;
  if (numbers.some((item) => item < MIN_FRACTION || item > MAX_FRACTION)) return false;
  const total = numbers.reduce((sum, item) => sum + item, 0);
  return Math.abs(total - 1) <= FRACTION_TOLERANCE;
}

/** Ramène une fraction dans [MIN_FRACTION, MAX_FRACTION] sans casser la somme. */
export function clampFraction(value: number, other: number): number {
  const upper = Math.max(MIN_FRACTION, 1 - other - MIN_FRACTION);
  const clamped = Number.isFinite(value) ? value : MIN_FRACTION;
  return Math.min(Math.max(clamped, MIN_FRACTION), upper);
}

export function customLayout(fractions: LayoutFractions, fullscreen: LayoutFullscreen = null): LayoutState {
  return {
    preset: "custom",
    fractions: { ...fractions },
    fullscreen,
  };
}

export function parseLayout(value: unknown): LayoutState {
  if (!isRecord(value)) return cloneLayout(DEFAULT_LAYOUT);
  const fullscreen: LayoutFullscreen =
    value.fullscreen === "main" || value.fullscreen === "secondary" ? value.fullscreen : null;
  const preset = value.preset;
  if (preset === "analyse" || preset === "pilotage" || preset === "presentation") {
    return { preset, fractions: { ...PRESET_FRACTIONS[preset] }, fullscreen };
  }
  if (preset === "custom" && fractionsAreValid(value.fractions)) {
    return {
      preset: "custom",
      fractions: {
        left: Number(value.fractions.left),
        main: Number(value.fractions.main),
        right: Number(value.fractions.right),
      },
      fullscreen,
    };
  }
  return cloneLayout(DEFAULT_LAYOUT);
}

export function decodeLayout(raw: string | null): LayoutState {
  if (!raw) return cloneLayout(DEFAULT_LAYOUT);
  try {
    return parseLayout(JSON.parse(raw));
  } catch {
    return cloneLayout(DEFAULT_LAYOUT);
  }
}

export function layoutStorageKey(projectId: string): string {
  return `${LAYOUT_KEY_PREFIX}${projectId}`;
}

function defaultStorage(): StorageLike | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function loadLayout(
  projectId: string | null,
  storage: StorageLike | null = defaultStorage(),
): LayoutState {
  if (!projectId || !storage) return cloneLayout(DEFAULT_LAYOUT);
  try {
    return decodeLayout(storage.getItem(layoutStorageKey(projectId)));
  } catch {
    return cloneLayout(DEFAULT_LAYOUT);
  }
}

export function saveLayout(
  projectId: string | null,
  layout: LayoutState,
  storage: StorageLike | null = defaultStorage(),
): void {
  if (!projectId || !storage) return;
  try {
    storage.setItem(layoutStorageKey(projectId), JSON.stringify(layout));
  } catch {
    /* stockage indisponible : la disposition reste valable pour la session */
  }
}
