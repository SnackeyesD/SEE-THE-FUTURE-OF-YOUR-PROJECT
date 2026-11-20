import { useEffect } from "react";

import {
  isInsideModal,
  isInteractiveTarget,
  isTextEntryTarget,
  ownsActivationKeys,
} from "../lib/keyboard";

/**
 * Raccourcis du cockpit. La garde est commune à tous les écrans : jamais de
 * capture dans un champ, un curseur ou un dialogue, ni dans la frise (qui gère
 * ses propres flèches et `Espace`).
 */
export function useCockpitHotkeys({
  enabled = true,
  onTogglePlayback,
  onMonthStep,
  onMonthEdge,
  onToggleFullscreen,
  onOpenPalette,
  onOpenHelp,
  onSave,
  onEscape,
}: {
  enabled?: boolean;
  onTogglePlayback: () => void;
  onMonthStep: (delta: number) => void;
  onMonthEdge: (edge: "first" | "last") => void;
  onToggleFullscreen: () => void;
  onOpenPalette: () => void;
  onOpenHelp: () => void;
  onSave: () => void;
  onEscape: () => void;
}): void {
  useEffect(() => {
    if (!enabled) return;

    const handle = (event: KeyboardEvent): void => {
      const target = event.target;
      // Un dialogue gère lui-même Échap et sa saisie : aucun raccourci de fond.
      if (isInsideModal(target)) return;
      const modifier = event.ctrlKey || event.metaKey;

      if (modifier && !event.altKey) {
        const key = event.key.toLowerCase();
        if (key === "k" || key === "s") {
          event.preventDefault();
          // La palette et l'enregistrement ne doivent pas voler une frappe.
          if (isTextEntryTarget(target)) return;
          if (key === "k") onOpenPalette();
          else onSave();
          return;
        }
        return;
      }

      if (isInteractiveTarget(target)) return;
      if (target instanceof HTMLElement && target.closest("[data-hotkeys-timeline]")) return;
      if (event.altKey) return;

      switch (event.key) {
        case " ":
          // `Espace` active déjà boutons, liens, onglets et cases.
          if (ownsActivationKeys(target)) return;
          event.preventDefault();
          onTogglePlayback();
          return;
        case "ArrowLeft":
          event.preventDefault();
          onMonthStep(-1);
          return;
        case "ArrowRight":
          event.preventDefault();
          onMonthStep(1);
          return;
        case "Home":
          event.preventDefault();
          onMonthEdge("first");
          return;
        case "End":
          event.preventDefault();
          onMonthEdge("last");
          return;
        case "f":
        case "F":
          event.preventDefault();
          onToggleFullscreen();
          return;
        case "?":
          event.preventDefault();
          onOpenHelp();
          return;
        case "Escape":
          onEscape();
          return;
        default:
          return;
      }
    };

    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [
    enabled,
    onEscape,
    onMonthEdge,
    onMonthStep,
    onOpenHelp,
    onOpenPalette,
    onSave,
    onToggleFullscreen,
    onTogglePlayback,
  ]);
}
