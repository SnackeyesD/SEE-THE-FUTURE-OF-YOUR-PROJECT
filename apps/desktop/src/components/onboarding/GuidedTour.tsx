import { Button } from "@see/ui";
import { useCallback, useEffect, useState } from "react";

export const TOUR_STORAGE_PREFIX = "seefuture.tour.";

export interface TourStep {
  title: string;
  body: string;
  view: string;
}

export const TOUR_STEPS: TourStep[] = [
  {
    title: "Voici vos hypothèses",
    body: "Chaque valeur porte sa source et son incertitude. Celles marquées « estimation » sont à remplacer par vos relevés réels.",
    view: "hypotheses",
  },
  {
    title: "Lancez un calcul final",
    body: "Le moteur tire des milliers de scénarios avec la même graine. Aucun chiffre ne vient de l'IA.",
    view: "simulation",
  },
  {
    title: "Lisez le point mort",
    body: "La fourchette P10–P90 décrit l'incertitude, pas une promesse. La graine et la version du moteur restent visibles.",
    view: "results",
  },
  {
    title: "Bougez un prix",
    body: "Dans le cockpit, modifiez une hypothèse et relancez. Comparez ensuite la branche « Prix -10 % ».",
    view: "cockpit",
  },
  {
    title: "Exportez votre dossier",
    body: "Le dossier Markdown reprend les faits du run final, sans recalcul ni secret. Il se génère hors ligne.",
    view: "results",
  },
];

interface Props {
  projectId: string;
  onNavigate: (view: string) => void;
}

function readDismissed(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "done";
  } catch {
    return false;
  }
}

export function GuidedTour({ projectId, onNavigate }: Props) {
  const storageKey = `${TOUR_STORAGE_PREFIX}${projectId}`;
  const [open, setOpen] = useState(() => !readDismissed(storageKey));
  const [index, setIndex] = useState(0);

  const dismiss = useCallback(() => {
    setOpen(false);
    try {
      window.localStorage.setItem(storageKey, "done");
    } catch {
      /* stockage indisponible : le parcours reste fermé pour la session */
    }
  }, [storageKey]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [dismiss, open]);

  if (!open) return null;

  const step = TOUR_STEPS[index];
  const last = index === TOUR_STEPS.length - 1;

  const goNext = () => {
    if (last) {
      dismiss();
      return;
    }
    const next = index + 1;
    setIndex(next);
    onNavigate(TOUR_STEPS[next].view);
  };

  return (
    <aside
      className="guided-tour"
      role="dialog"
      aria-label="Parcours découverte"
      aria-live="polite"
    >
      <div className="guided-tour__head">
        <span className="ui-eyebrow">
          Découverte · étape {index + 1}/{TOUR_STEPS.length}
        </span>
        <button
          type="button"
          className="guided-tour__skip"
          onClick={dismiss}
          aria-label="Passer le parcours"
        >
          Passer
        </button>
      </div>
      <strong className="guided-tour__title">{step.title}</strong>
      <p>{step.body}</p>
      <div className="guided-tour__actions">
        <Button
          variant="ghost"
          onClick={() => setIndex((current) => Math.max(0, current - 1))}
          disabled={index === 0}
        >
          Précédent
        </Button>
        <Button onClick={goNext}>{last ? "Terminer" : "Suivant"}</Button>
      </div>
    </aside>
  );
}
