import type { HealthResult, SidecarStatus } from "@see/protocol";

export interface DiagnosticLog {
  at: string;
  level: string;
  message: string;
}

export interface DiagnosticCrash {
  at: string;
  kind: string;
  message: string;
}

export interface DiagnosticInput {
  appVersion: string;
  locale: string;
  userAgent: string;
  status: SidecarStatus | null;
  health: HealthResult | null;
  logs: DiagnosticLog[];
  crashes?: DiagnosticCrash[];
  /** Noms à masquer : un diagnostic ne doit jamais contenir un projet. */
  projectNames?: string[];
  /** Injecté par les tests pour rendre la sortie déterministe. */
  generatedAt?: string;
}

const KEY_PATTERNS: Array<[RegExp, string]> = [
  [/sk-[A-Za-z0-9_-]{8,}/g, "sk-[clé masquée]"],
  [/AIza[0-9A-Za-z_-]{20,}/g, "AIza[clé masquée]"],
  [/gh[pousr]_[A-Za-z0-9]{20,}/g, "gh[clé masquée]"],
  [/xox[baprs]-[A-Za-z0-9-]{10,}/g, "xox[clé masquée]"],
  [/(?<=Bearer\s)[A-Za-z0-9._~+/=-]{8,}/gi, "[jeton masqué]"],
];

const ASSIGNMENT_PATTERN =
  /\b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret|password)\b(\s*[:=]\s*)([^\s,;]+)/gi;

const WINDOWS_PATH = /[A-Za-z]:\\[^\s"'<>|]*/g;
const UNC_PATH = /\\\\[^\s"'<>|]*/g;
const POSIX_PATH = /\/(?:home|Users|tmp|var|etc|opt|private)\/[^\s"'<>|]*/g;
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Retire clés, chemins, courriels et noms de projets d'un texte de journal. */
export function scrubDiagnosticText(text: string, projectNames: string[] = []): string {
  let cleaned = text;
  for (const [pattern, replacement] of KEY_PATTERNS) {
    cleaned = cleaned.replace(pattern, replacement);
  }
  cleaned = cleaned.replace(
    ASSIGNMENT_PATTERN,
    (_match: string, key: string, separator: string) => `${key}${separator}[masqué]`,
  );
  cleaned = cleaned.replace(WINDOWS_PATH, "[chemin masqué]");
  cleaned = cleaned.replace(UNC_PATH, "[chemin masqué]");
  cleaned = cleaned.replace(POSIX_PATH, "[chemin masqué]");
  cleaned = cleaned.replace(EMAIL, "[courriel masqué]");
  for (const name of projectNames) {
    if (!name.trim()) continue;
    cleaned = cleaned.replace(new RegExp(escapeRegExp(name.trim()), "gi"), "[projet masqué]");
  }
  return cleaned;
}

/**
 * Construit un diagnostic local, sans réseau.
 *
 * Le contenu est volontairement borné : versions, état du sidecar et derniers
 * événements. Aucun projet, aucune clé, aucun chemin ne doit en sortir.
 */
export function buildDiagnostic(input: DiagnosticInput): string {
  const names = input.projectNames ?? [];
  const scrub = (value: string) => scrubDiagnosticText(value, names);
  const payload = {
    formatVersion: "1",
    generatedAt: input.generatedAt ?? new Date().toISOString(),
    application: {
      version: input.appVersion,
      locale: input.locale,
      userAgent: input.userAgent,
    },
    sidecar: input.status
      ? {
          running: input.status.running,
          pid: input.status.pid ?? null,
          error: input.status.error ? scrub(input.status.error) : null,
        }
      : null,
    health: input.health
      ? {
          status: input.health.status,
          sidecarVersion: input.health.sidecarVersion,
          protocolVersion: input.health.protocolVersion,
          python: input.health.python,
        }
      : null,
    logs: input.logs.slice(-50).map((entry) => ({
      at: entry.at,
      level: entry.level,
      message: scrub(entry.message),
    })),
    crashes: (input.crashes ?? []).slice(-10).map((entry) => ({
      at: entry.at,
      kind: entry.kind,
      message: scrub(entry.message),
    })),
  };
  return JSON.stringify(payload, null, 2);
}

export function diagnosticFilename(now = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}`;
  return `diagnostic-seetfuture-${date}-${time}.json`;
}
