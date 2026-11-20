import { Button } from "@see/ui";
import { useRef } from "react";

import { useDialogFocus } from "../hooks/useDialogFocus";
import { SHORTCUTS } from "../lib/shortcuts";

/** Aide contextuelle des raccourcis (`?`). */
export function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useDialogFocus(ref, onClose);

  return (
    <div className="cockpit-dialog-backdrop" onPointerDown={onClose}>
      <div
        ref={ref}
        className="cockpit-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        data-hotkeys-scope="true"
        onPointerDown={(event) => event.stopPropagation()}
      >
        <div className="cockpit-dialog__head">
          <div>
            <h2 id="shortcuts-title">Raccourcis clavier</h2>
            <p className="ui-muted">
              Les champs de saisie et les curseurs gardent leurs flèches natives.
            </p>
          </div>
          <Button variant="ghost" size="small" onClick={onClose}>
            Fermer
          </Button>
        </div>
        <table className="cockpit-shortcuts">
          <caption className="ui-visually-hidden">Liste des raccourcis clavier</caption>
          <thead>
            <tr>
              <th scope="col">Touches</th>
              <th scope="col">Action</th>
              <th scope="col">Contexte</th>
            </tr>
          </thead>
          <tbody>
            {SHORTCUTS.map((shortcut) => (
              <tr key={`${shortcut.scope}:${shortcut.keys}`}>
                <td>
                  <kbd>{shortcut.keys}</kbd>
                </td>
                <td>{shortcut.label}</td>
                <td className="ui-muted">{shortcut.scope}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
