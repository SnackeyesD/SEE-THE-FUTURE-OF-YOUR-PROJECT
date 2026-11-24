import { scrubDiagnosticText } from "./diagnostic";

export interface CrashEntry {
  at: string;
  kind: "error" | "rejection";
  message: string;
}

const ENABLED_KEY = "seefuture.crashLog.enabled";
const ENTRIES_KEY = "seefuture.crashLog.entries";
const MAX_ENTRIES = 10;
const MAX_MESSAGE = 500;

/**
 * Journal local des erreurs, désactivé par défaut.
 *
 * Aucun envoi réseau n'existe dans cette version : activer l'option écrit
 * seulement un journal borné, nettoyé, lisible depuis l'export de diagnostic.
 */
export function isCrashLogEnabled(): boolean {
  try {
    return window.localStorage.getItem(ENABLED_KEY) === "on";
  } catch {
    return false;
  }
}

export function setCrashLogEnabled(enabled: boolean): boolean {
  try {
    window.localStorage.setItem(ENABLED_KEY, enabled ? "on" : "off");
    if (!enabled) {
      window.localStorage.removeItem(ENTRIES_KEY);
    }
    return true;
  } catch {
    return false;
  }
}

export function readCrashEntries(): CrashEntry[] {
  try {
    const raw = window.localStorage.getItem(ENTRIES_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isCrashEntry).slice(-MAX_ENTRIES);
  } catch {
    return [];
  }
}

export function clearCrashEntries(): void {
  try {
    window.localStorage.removeItem(ENTRIES_KEY);
  } catch {
    /* stockage indisponible : rien à effacer */
  }
}

export function recordCrash(
  kind: CrashEntry["kind"],
  reason: unknown,
  at = new Date().toISOString(),
): void {
  if (!isCrashLogEnabled()) return;
  const raw = reason instanceof Error ? reason.message : String(reason ?? "");
  const message = scrubDiagnosticText(raw).slice(0, MAX_MESSAGE);
  if (!message.trim()) return;
  try {
    const entries = [...readCrashEntries(), { at, kind, message }].slice(-MAX_ENTRIES);
    window.localStorage.setItem(ENTRIES_KEY, JSON.stringify(entries));
  } catch {
    /* quota ou stockage indisponible : le journal reste facultatif */
  }
}

/** Branche les gestionnaires d'erreurs globaux. Retourne la fonction de retrait. */
export function installCrashLogger(): () => void {
  const onError = (event: ErrorEvent) => {
    recordCrash("error", event.error ?? event.message);
  };
  const onRejection = (event: PromiseRejectionEvent) => {
    recordCrash("rejection", event.reason);
  };
  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onRejection);
  };
}

function isCrashEntry(value: unknown): value is CrashEntry {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as Record<string, unknown>;
  return (
    typeof entry.at === "string" &&
    (entry.kind === "error" || entry.kind === "rejection") &&
    typeof entry.message === "string"
  );
}
