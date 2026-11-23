import type { ScenarioVersionRef } from "@see/protocol";
import { Badge, Button, EmptyState, InlineAlert } from "@see/ui";
import { useState } from "react";

import { formatDateTime, formatNumber } from "../../lib/format";

export interface VersionListProps {
  versions: readonly ScenarioVersionRef[];
  busy?: boolean;
  /** Libellé prérempli proposé par l'écran (branche courante + date). */
  suggestedLabel?: string;
  onCreate: (label: string) => void;
  onRestore: (version: ScenarioVersionRef) => void;
  onDelete: (version: ScenarioVersionRef) => void;
}

/**
 * Versions nommées : snapshots immuables. Restaurer crée toujours une
 * nouvelle branche ; supprimer une version est explicite et hors historique.
 */
export function VersionList({
  versions,
  busy = false,
  suggestedLabel = "",
  onCreate,
  onRestore,
  onDelete,
}: VersionListProps) {
  const [label, setLabel] = useState(suggestedLabel);
  const [deleting, setDeleting] = useState<string | null>(null);

  return (
    <div className="version-list">
      <form
        className="version-list__create"
        onSubmit={(event) => {
          event.preventDefault();
          const clean = label.trim();
          if (!clean) return;
          onCreate(clean);
          setLabel("");
        }}
      >
        <label className="ui-field">
          <span>Enregistrer une version</span>
          <input
            value={label}
            placeholder={suggestedLabel || "Ex. Avant hausse du prix"}
            onChange={(event) => setLabel(event.target.value)}
            aria-label="Libellé de la nouvelle version"
          />
        </label>
        <Button type="submit" size="small" disabled={busy || !label.trim()}>
          Enregistrer
        </Button>
      </form>

      {versions.length === 0 ? (
        <EmptyState
          title="Aucune version enregistrée"
          description="Une version fige les hypothèses et une graine. Elle ne sera jamais modifiée."
        />
      ) : (
        <ul className="version-list__items">
          {versions.map((version) => (
            <li key={version.id} className="version-list__item">
              <div>
                <strong>{version.label}</strong>
                <Badge tone="neutral">immuable</Badge>
                <div className="ui-muted">
                  {formatDateTime(version.createdAt)} ·{" "}
                  {version.seed === null
                    ? "graine non figée"
                    : `graine ${formatNumber(version.seed)}`}
                  {version.engineVersion ? ` · moteur ${version.engineVersion}` : ""}
                </div>
              </div>
              <div className="ui-actions">
                <Button
                  variant="secondary"
                  size="small"
                  disabled={busy}
                  onClick={() => onRestore(version)}
                >
                  Restaurer en branche
                </Button>
                <Button
                  variant="danger"
                  size="small"
                  disabled={busy}
                  onClick={() => setDeleting(version.id)}
                >
                  Supprimer
                </Button>
              </div>
              {deleting === version.id ? (
                <InlineAlert tone="warn" title="Supprimer cette version ?">
                  Cette action est définitive et ne peut pas être annulée.
                  <div className="ui-actions">
                    <Button
                      variant="danger"
                      size="small"
                      disabled={busy}
                      onClick={() => {
                        onDelete(version);
                        setDeleting(null);
                      }}
                    >
                      Confirmer la suppression
                    </Button>
                    <Button
                      variant="ghost"
                      size="small"
                      onClick={() => setDeleting(null)}
                    >
                      Annuler
                    </Button>
                  </div>
                </InlineAlert>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
