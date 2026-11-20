export interface ShortcutSpec {
  keys: string;
  label: string;
  scope: string;
}

/** Source unique de l'aide (`?`) et de la documentation des raccourcis. */
export const SHORTCUTS: readonly ShortcutSpec[] = [
  { keys: "Espace", label: "Lecture / pause du temps", scope: "Cockpit" },
  { keys: "← / →", label: "Mois précédent / suivant", scope: "Cockpit" },
  { keys: "Home / End", label: "Premier / dernier mois", scope: "Cockpit" },
  { keys: "F", label: "Plein écran du panneau principal", scope: "Cockpit" },
  { keys: "Ctrl/Cmd + K", label: "Palette de commandes", scope: "Global" },
  { keys: "Ctrl/Cmd + Z", label: "Annuler", scope: "Cockpit" },
  { keys: "Ctrl/Cmd + Shift + Z", label: "Rétablir", scope: "Cockpit" },
  { keys: "1 – 8", label: "Naviguer entre les vues", scope: "Global" },
  { keys: "?", label: "Afficher cette aide", scope: "Global" },
  { keys: "Échap", label: "Fermer un dialogue ou quitter le plein écran", scope: "Global" },
  { keys: "← / → (bloc)", label: "Déplacer un événement", scope: "Frise" },
  { keys: "Shift + ← / →", label: "Régler la durée", scope: "Frise" },
  { keys: "Alt + ← / →", label: "Régler le début", scope: "Frise" },
  { keys: "Entrée / Suppr", label: "Éditer / supprimer un événement", scope: "Frise" },
  { keys: "Ctrl/Cmd + S", label: "Enregistrer le scénario", scope: "Cockpit" },
];
