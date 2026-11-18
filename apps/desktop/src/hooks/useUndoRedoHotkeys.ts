import { useEffect } from "react";

import type { CommandStack } from "../store/commands";

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * Ctrl+Z / Ctrl+Y (et Cmd sur macOS) sur les commandes d'entrée.
 * Les champs de saisie gardent leur undo natif.
 */
export function useUndoRedoHotkeys(stack: CommandStack, enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    const handle = (event: KeyboardEvent): void => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      if (isEditable(event.target)) return;
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
