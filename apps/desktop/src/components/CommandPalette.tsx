import { Button } from "@see/ui";
import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import { useDialogFocus } from "../hooks/useDialogFocus";

export interface PaletteAction {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

/**
 * Palette de commandes (`Ctrl/Cmd+K`).
 *
 * Les actions sont fournies par l'écran : la palette ne connaît ni le store ni
 * l'IPC. Le filtre est insensible aux accents et à la casse.
 */
export function CommandPalette({
  actions,
  onClose,
}: {
  actions: readonly PaletteAction[];
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useDialogFocus(ref, onClose);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const normalized = (value: string): string =>
    value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();

  const filtered = useMemo(() => {
    const needle = normalized(query.trim());
    if (!needle) return actions;
    return actions.filter((action) =>
      normalized(`${action.label} ${action.hint ?? ""}`).includes(needle),
    );
  }, [actions, query]);

  const run = (action: PaletteAction | undefined): void => {
    if (!action) return;
    onClose();
    action.run();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current) => Math.min(current + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      run(filtered[active]);
    }
  };

  return (
    <div className="cockpit-dialog-backdrop" onPointerDown={onClose}>
      <div
        ref={ref}
        className="cockpit-dialog cockpit-dialog--palette"
        role="dialog"
        aria-modal="true"
        aria-labelledby="palette-title"
        data-hotkeys-scope="true"
        onPointerDown={(event) => event.stopPropagation()}
      >
        <h2 id="palette-title" className="ui-visually-hidden">
          Palette de commandes
        </h2>
        <input
          className="cockpit-palette__input"
          type="search"
          autoComplete="off"
          placeholder="Rechercher une commande…"
          aria-label="Rechercher une commande"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
        />
        <ul className="cockpit-palette__list" role="listbox" aria-label="Commandes disponibles">
          {filtered.length === 0 ? (
            <li className="cockpit-palette__empty ui-muted">Aucune commande ne correspond.</li>
          ) : null}
          {filtered.map((action, index) => (
            <li key={action.id} role="option" aria-selected={index === active}>
              <button
                type="button"
                className={[
                  "cockpit-palette__item",
                  index === active && "cockpit-palette__item--active",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onMouseEnter={() => setActive(index)}
                onClick={() => run(action)}
              >
                <span>{action.label}</span>
                {action.hint ? <span className="ui-muted">{action.hint}</span> : null}
              </button>
            </li>
          ))}
        </ul>
        <div className="cockpit-dialog__actions">
          <span className="ui-muted">↑↓ naviguer · Entrée exécuter · Échap fermer</span>
          <Button variant="ghost" size="small" onClick={onClose}>
            Fermer
          </Button>
        </div>
      </div>
    </div>
  );
}
