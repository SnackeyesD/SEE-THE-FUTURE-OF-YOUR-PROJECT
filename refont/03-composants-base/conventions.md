# Conventions — librairie de primitives « Ink & Signal » (phase 03)

Ce document est **opposable** : toute PR qui ajoute ou modifie un composant UI
doit le respecter. Il complète `refont/02-fondations-tokens/charte-couleurs.md`
(les 5 règles tokens) et `refont/03-composants-base/README.md` (DoD).

## 1. Où vit quoi

| Besoin | Fichier | Interdits |
|---|---|---|
| Valeur visuelle (couleur, taille, ombre…) | `packages/ui/src/tokens.css` — **source de vérité unique** | Tout autre fichier : zéro hex, zéro `rgb()` écrit à la main (sauf `Charts.tsx`, migré phase 04) |
| Style des primitives | `packages/ui/src/primitives.css` | `styles.css` : **interdiction d'y ajouter des classes à partir de la phase 03** |
| Composants React | `packages/ui/src/primitives/*.tsx` | Composants stylés inline sauf cas exceptionnel documenté (vitrine) |
| Logique écran | `apps/desktop/src/*` | Écrire du CSS ciblant une classe `ui-*` (voir §4) |

## 2. Ajouter un composant — procédure

1. **Besoin répété ≥ 2 fois** ou à sémantique forte → primitive. Sinon : composition
   de primitives existantes dans l'écran.
2. Créer `packages/ui/src/primitives/<Nom>.tsx` :
   - props typées, une prop `className` pour l'extension (fusion via `cx`) ;
   - aucune couleur en dur : uniquement `var(--token)` ;
   - les **chiffres** (valeur de mesure, cellule numérique, horodatage) passent par
     `--font-data` + `font-variant-numeric: tabular-nums` (règle R4) ;
   - l'accent `--accent` uniquement pour l'**interactif** (jamais décoration,
     jamais série de données).
3. Ajouter ses classes dans `primitives.css` (préfixe `ui-`, BEM léger :
   `ui-bloc__element--modificateur`), **section commentée** en tête de bloc.
4. Exporter depuis `primitives/` → barrel `components.tsx` → `index.ts`
   (valeurs **et** types `export type`).
5. Documenter tous les états dans la vitrine `apps/desktop/src/components/ComponentsShowcase.tsx`.
6. Recapturer la vitrine dans `refont/03-composants-base/captures/` si le rendu change.

## 3. Checklist a11y (obligatoire avant merge)

- [ ] **Focus visible** sur tout élément interactif : `outline: var(--focus)` +
      `outline-offset: var(--focus-offset)` — jamais `outline: none` seul.
- [ ] **Navigation clavier** : Tab atteint l'élément dans l'ordre de lecture ;
      pour les widgets composites (tabs, listes), flèches + Home/End comme `Tabs.tsx`.
- [ ] **Rôles/états ARIA** : `aria-selected`, `aria-invalid`, `aria-expanded`,
      `role="status"` pour les annonces non bloquantes, `role="progressbar"` avec
      `aria-valuenow` quand la valeur existe.
- [ ] **Label de champ relié** (`for`/`id`, cf. `Field.tsx` — `useId`).
- [ ] **La couleur ne porte jamais seule l'information** (WCAG 1.4.1) : un badge
      a toujours un texte, une erreur a toujours un message.
- [ ] **Messages actionnables** (principe Snyk) : titre obligatoire sur
      `InlineAlert`, l'état vide propose une action (`EmptyState`).
- [ ] **`prefers-reduced-motion`** respecté pour toute animation (cf.
      `ui-progress__track--indeterminate`).
- [ ] Contraste : texte sur encre ≥ 4.5:1 (corps) / 3:1 (grand texte, bordures).

## 4. Règle de séparation styles.css ↔ librairie

- `styles.css` = styles d'**écran** generation 1 (layout, grilles, widgets
  historiques). Purge progressive en phases 05/07.
- `primitives.css` = style des **primitives**. Du point de vue de la phase 03 :
  - interdiction d'**ajouter** une règle dans `styles.css` ciblant `ui-*` ;
  - les rattachements résiduels (ex. `.composer .ui-field`) sont tolérés en
    attendant la migration de l'écran hôte — les noter dans le README de phase
    concernée ;
  - un écran migré n'utilise que des primitives `@see/ui` + sa grille locale.

## 5. Leçon de cascade (bug trouvé et corrigé en phase 03)

Deux pièges à ne jamais réintroduire :

1. **Séquence `*/` dans un commentaire** : un libellé comme
   `--ink-*/--line-*` ferme le commentaire d'en-tête prématurément ; le parseur
   avale alors tout le bloc `:root` **sans erreur** (0 règles, page restylée
   par les héritages). Toujours espacer : `--ink-* / --line-*`.
2. **Doublon de token entre fichiers** : `styles.css` redéfinissait
   `:root { --accent: #4f8cff … }` et étant importé **après** `tokens.css`,
   ses valeurs écrasaient les tokens. Un nom de token n'est défini **qu'une
   seule fois**, dans `tokens.css`.

Vérification rapide à toute suspicion de cascade :
`NODE_PATH=~/.npm/_npx/e41f203b7505f1fb/node_modules node /tmp/opencode/cascade.cjs`
(doit montrer accent `rgb(34, 211, 238)`, polices Inter / JetBrains Mono).
