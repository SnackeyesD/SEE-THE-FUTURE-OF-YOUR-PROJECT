/**
 * Garde commune des raccourcis clavier.
 *
 * Un raccourci global ne doit jamais voler une frappe destinée à un champ, ni
 * une flèche destinée à un curseur (`slider`, `separator`, `spinbutton`).
 * Les dialogues de la palette et de l'aide posent en plus `data-hotkeys-scope`
 * sur leur racine pour suspendre les raccourcis de fond.
 */
export function isTextEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return true;
  return Boolean(target.closest('[contenteditable="true"], [role="textbox"]'));
}

export function isInteractiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (isTextEntryTarget(target)) return true;
  return Boolean(
    target.closest(
      '[contenteditable="true"], [role="slider"], [role="separator"], [role="spinbutton"], [role="textbox"]',
    ),
  );
}

/**
 * Éléments dont `Espace` et `Entrée` déclenchent déjà l'action native.
 * Sans cette garde, `Espace` sur « Enregistrer » lancerait la lecture.
 */
export function ownsActivationKeys(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return Boolean(
    target.closest(
      'button, a[href], summary, [role="button"], [role="menuitem"], [role="option"], [role="tab"], [role="checkbox"], [role="switch"]',
    ),
  );
}

/** Vrai si un dialogue modal gère déjà le clavier (palette, aide, éditeur). */
export function isInsideModal(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest("[data-hotkeys-scope]"));
}

export function isPlainKey(event: KeyboardEvent): boolean {
  return !event.ctrlKey && !event.metaKey && !event.altKey;
}
