import { useEffect } from "react";

import { isInsideModal, isInteractiveTarget } from "../lib/keyboard";

/**
 * Raccourcis `1–8` des vues. Le tableau suit l'ordre de la navigation ; un
 * chiffre hors bornes est ignoré. Aucune capture dans un champ ou un dialogue.
 */
export function useViewHotkeys({
  views,
  onSelect,
  enabled = true,
}: {
  views: readonly string[];
  onSelect: (view: string) => void;
  enabled?: boolean;
}): void {
  useEffect(() => {
    if (!enabled) return;
    const handle = (event: KeyboardEvent): void => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (isInteractiveTarget(event.target) || isInsideModal(event.target)) return;
      if (!/^[1-9]$/.test(event.key)) return;
      const index = Number(event.key) - 1;
      const view = views[index];
      if (!view) return;
      event.preventDefault();
      onSelect(view);
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [enabled, onSelect, views]);
}
