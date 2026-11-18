import { serieStyle } from "@see/ui";

export interface GhostItem {
  runId: string;
  label: string;
  seed: number;
  stale?: boolean;
}

/**
 * Légende des fantômes (maximum 3) : libellé, graine visible et état périmé.
 * Les fantômes viennent des runs épinglés du store.
 */
export function GhostLegend({
  ghosts,
  onUnpin,
}: {
  ghosts: readonly GhostItem[];
  onUnpin?: (runId: string) => void;
}) {
  if (ghosts.length === 0) {
    return (
      <p className="cockpit-ghosts__empty ui-muted">
        Épinglez un run pour le comparer en fantôme (maximum 3).
      </p>
    );
  }

  return (
    <ul className="cockpit-ghosts" aria-label="Runs épinglés">
      {ghosts.map((ghost, index) => (
        <li key={ghost.runId} className="cockpit-ghosts__item">
          <span
            className="viz__legend__chip"
            style={serieStyle(index + 1)}
            aria-hidden="true"
          />
          <span className="cockpit-ghosts__label">{ghost.label}</span>
          <span className="cockpit-ghosts__seed">graine {ghost.seed}</span>
          {ghost.stale ? <span className="cockpit-ghosts__stale">périmé</span> : null}
          {onUnpin ? (
            <button
              type="button"
              className="cockpit-ghosts__unpin"
              aria-label={`Désépingler ${ghost.label}`}
              onClick={() => onUnpin(ghost.runId)}
            >
              Retirer
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
