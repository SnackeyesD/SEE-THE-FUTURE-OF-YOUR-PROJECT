import type { ScenarioEvent } from "@see/protocol";
import { EVENT_CATALOG } from "@see/protocol";
import { Button } from "@see/ui";
import { useRef } from "react";

import { useDialogFocus } from "../../hooks/useDialogFocus";

/**
 * Catalogue des imprévus, alimenté par le moteur (`EVENT_CATALOG` généré).
 * Aucun libellé ni cible n'est recopié ici : la sélection remonte le type au
 * parent, qui construit un événement valide avec la magnitude par défaut.
 */
export function EventCatalog({
  month,
  horizon,
  onPick,
  onClose,
}: {
  month: number;
  horizon: number;
  onPick: (type: ScenarioEvent["type"]) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useDialogFocus(ref, onClose);

  return (
    <div className="cockpit-dialog-backdrop" onPointerDown={onClose}>
      <div
        ref={ref}
        className="cockpit-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="event-catalog-title"
        data-hotkeys-scope="true"
        onPointerDown={(event) => event.stopPropagation()}
      >
        <div className="cockpit-dialog__head">
          <div>
            <h2 id="event-catalog-title">Catalogue d'événements</h2>
            <p className="ui-muted">
              Ajout au mois {month} sur {horizon} mois · durée par défaut 3 mois, probabilité
              100 %.
            </p>
          </div>
          <Button variant="ghost" size="small" onClick={onClose}>
            Fermer
          </Button>
        </div>

        <ul className="cockpit-catalog">
          {EVENT_CATALOG.map((entry) => (
            <li key={entry.type}>
              <button
                type="button"
                className="cockpit-catalog__item"
                onClick={() => onPick(entry.type)}
              >
                <span className="cockpit-catalog__label">{entry.label}</span>
                <span className="cockpit-catalog__description">{entry.description}</span>
                <span className="cockpit-catalog__meta">
                  cible : {entry.targetLabel} ·{" "}
                  {entry.mode === "multiplicative" ? "multiplicatif" : "additif"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
