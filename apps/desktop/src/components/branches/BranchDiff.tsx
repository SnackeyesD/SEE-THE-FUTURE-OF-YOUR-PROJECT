import { Badge } from "@see/ui";

import { formatNumber } from "../../lib/format";
import type { DiffEntry, DiffEntryKind } from "../../lib/scenarioDiff";

const KIND_LABELS: Record<DiffEntryKind, string> = {
  added: "ajouté",
  removed: "supprimé",
  changed: "modifié",
  "event-added": "événement ajouté",
  "event-removed": "événement supprimé",
  "event-changed": "événement modifié",
};

const KIND_TONES: Record<DiffEntryKind, "neutral" | "ok" | "warn" | "danger"> = {
  added: "ok",
  removed: "danger",
  changed: "warn",
  "event-added": "ok",
  "event-removed": "danger",
  "event-changed": "warn",
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? formatNumber(value) : formatNumber(value, 2);
  }
  if (typeof value === "boolean") return value ? "actif" : "inactif";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value.every((item) => typeof item === "number")
      ? value.map((item) => formatNumber(item as number, 2)).join(", ")
      : JSON.stringify(value);
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function groupOf(entry: DiffEntry): "headers" | "assumptions" | "events" {
  if (entry.path.startsWith("assumptions.")) return "assumptions";
  if (entry.path.startsWith("events[")) return "events";
  return "headers";
}

const GROUPS: Array<{ id: "headers" | "assumptions" | "events"; title: string }> = [
  { id: "headers", title: "En-tête du scénario" },
  { id: "assumptions", title: "Hypothèses" },
  { id: "events", title: "Événements" },
];

/**
 * Diff lisible des hypothèses, événements et champs d'en-tête. Les valeurs
 * sont formatées à l'affichage ; le diff lui-même reste brut et testable.
 */
export function BranchDiff({
  entries,
  leftLabel = "Branche A",
  rightLabel = "Branche B",
}: {
  entries: readonly DiffEntry[];
  leftLabel?: string;
  rightLabel?: string;
}) {
  if (entries.length === 0) {
    return (
      <p className="ui-muted" role="status">
        Aucune différence entre les deux branches.
      </p>
    );
  }

  return (
    <div className="branch-diff">
      {GROUPS.map((group) => {
        const rows = entries.filter((entry) => groupOf(entry) === group.id);
        if (rows.length === 0) return null;
        return (
          <section key={group.id} aria-labelledby={`diff-${group.id}`}>
            <h3 id={`diff-${group.id}`}>{group.title}</h3>
            <div className="branch-diff__table">
              <table>
                <caption className="ui-visually-hidden">
                  {group.title} — différences entre {leftLabel} et {rightLabel}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Élément</th>
                    <th scope="col">{leftLabel}</th>
                    <th scope="col">{rightLabel}</th>
                    <th scope="col">Changement</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.path}>
                      <th scope="row">
                        {row.label}
                        <span className="ui-muted branch-diff__path">{row.path}</span>
                      </th>
                      <td>{formatValue(row.before)}</td>
                      <td>{formatValue(row.after)}</td>
                      <td>
                        <Badge tone={KIND_TONES[row.kind]}>{KIND_LABELS[row.kind]}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
