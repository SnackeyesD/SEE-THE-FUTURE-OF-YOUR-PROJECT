import { useEffect } from "react";

import { isInsideModal, isTextEntryTarget } from "../lib/keyboard";
import type { CommandStack } from "../store/commands";

/**
 * Ctrl+Z / Ctrl+Y (et Cmd sur macOS) sur les commandes d'entrée.
 * Les champs de saisie et les curseurs gardent leur comportement natif ;
 * un dialogue ouvert suspend l'historique du scénario.
 */
export function useUndoRedoHotkeys(stack: CommandStack, enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    const handle = (event: KeyboardEvent): void => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      if (isTextEntryTarget(event.target) || isInsideModal(event.target)) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey) {
        if (stack.undo()) event.preventDefault();
        return;
      }
      if (key === "y" || (key === "z" && event.shiftKey)) {
        if (stack.redo()) event.preventDefault();
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [enabled, stack]);
}
